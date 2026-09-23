"""Restaurant agent.

Finds restaurant candidates for the destination via the places tool, then
uses the LLM to rank/select the ones best matched to cuisine, price range,
and dietary preferences. Never invents restaurants — only reorders/trims
real tool results.
"""

from __future__ import annotations

from pydantic import BaseModel

from config import get_llm
from graph.state import TravelState
from schemas.itinerary import Coordinates, Restaurant, SourceInfo
from tools.places import search_places
from utils.helpers import load_prompt

_PROMPT = load_prompt("restaurant")

_CATEGORY = "restaurant"
_MAX_RESULTS = 8


class _Selection(BaseModel):
    selected_names: list[str]


def _to_restaurant(raw: dict) -> Restaurant:
    lat = raw.get("lat")
    lng = raw.get("lng")
    coordinates = Coordinates(lat=lat, lng=lng) if lat is not None and lng is not None else None

    return Restaurant(
        name=raw.get("name", "Unknown"),
        cuisine=raw.get("cuisine", []) or raw.get("tags", []) or [],
        price_range=raw.get("price_range"),
        address=raw.get("address"),
        coordinates=coordinates,
        opening_hours=raw.get("opening_hours"),
        rating=raw.get("rating"),
        dietary_options=raw.get("dietary_options", []) or [],
        source_info=SourceInfo(
            source=raw.get("source", "google_places"),
            url=raw.get("url"),
            is_verified=True,
        ),
    )


def _rank_and_filter(
    restaurants: list[Restaurant], interests: list[str], dietary_requirements: list[str]
) -> list[Restaurant]:
    """LLM reasons over real tool results to pick/order the best matches.
    Falls back to a naive rating sort if the LLM call fails."""
    if not restaurants:
        return []

    fallback_order = sorted(restaurants, key=lambda r: (r.rating or 0), reverse=True)[:_MAX_RESULTS]

    try:
        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(_Selection)
        candidates_text = "\n".join(
            f"- {r.name}: cuisine={', '.join(r.cuisine) or 'unknown'}, "
            f"price={r.price_range or 'unknown'}, rating={r.rating or 'n/a'}"
            for r in restaurants
        )
        selection: _Selection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User interests: {', '.join(interests) or 'general dining'}\n"
                        f"Dietary requirements: {', '.join(dietary_requirements) or 'none specified'}\n\n"
                        f"Candidate restaurants:\n{candidates_text}\n\n"
                        f"Select up to {_MAX_RESULTS} names, best-matched first. "
                        "Only use names exactly as given above. Prioritize restaurants "
                        "that satisfy any stated dietary requirements."
                    ),
                },
            ]
        )
        by_name = {r.name: r for r in restaurants}
        selected = [by_name[name] for name in selection.selected_names if name in by_name]
        return selected[:_MAX_RESULTS] if selected else fallback_order
    except Exception:
        return fallback_order


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")
    agent_results = state.get("agent_results", {}) or {}

    if travel_request is None or not travel_request.destination:
        errors = state.get("errors", []) + [
            {"node": "restaurant", "message": "Missing destination in travel request.", "retry_count": 0}
        ]
        return {"errors": errors}

    interests = travel_request.preferences.interests
    dietary_requirements = travel_request.preferences.dietary_requirements

    try:
        raw_restaurants = search_places(
            destination=travel_request.destination,
            category=_CATEGORY,
            keywords=interests + dietary_requirements,
            max_results=15,
        )
    except Exception as exc:
        errors = state.get("errors", []) + [
            {"node": "restaurant", "message": str(exc), "retry_count": 0}
        ]
        return {"errors": errors}

    restaurants = [_to_restaurant(raw) for raw in raw_restaurants]
    selected = _rank_and_filter(restaurants, interests, dietary_requirements)

    agent_results["restaurant"] = [r.model_dump() for r in selected]
    return {"agent_results": agent_results}