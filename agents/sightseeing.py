"""Sightseeing agent.

Finds attractions, museums, activities, and (where available) events for the
destination, then uses the LLM to rank/select the ones best matched to the
user's interests. Never invents places — only reorders/trims real tool
results.
"""

from __future__ import annotations

from pydantic import BaseModel

from config import get_llm
from graph.state import TravelState
from schemas.itinerary import Coordinates, Place, SourceInfo
from tools.places import search_places
from utils.helpers import load_prompt

_PROMPT = load_prompt("sightseeing")

_CATEGORY = "tourist_attraction"
_MAX_RESULTS = 8


class _Selection(BaseModel):
    selected_names: list[str]


def _to_place(raw: dict) -> Place:
    lat = raw.get("lat")
    lng = raw.get("lng")
    coordinates = Coordinates(lat=lat, lng=lng) if lat is not None and lng is not None else None

    return Place(
        name=raw.get("name", "Unknown"),
        category=raw.get("category"),
        description=raw.get("description"),
        address=raw.get("address"),
        coordinates=coordinates,
        opening_hours=raw.get("opening_hours"),
        price=raw.get("price"),
        currency=raw.get("currency", "INR"),
        rating=raw.get("rating"),
        tags=raw.get("tags", []) or [],
        source_info=SourceInfo(
            source=raw.get("source", "google_places"),
            url=raw.get("url"),
            is_verified=True,
        ),
    )


def _rank_and_filter(places: list[Place], interests: list[str]) -> list[Place]:
    """LLM reasons over the real tool results to pick/order the best matches.
    Falls back to a naive rating sort if the LLM call fails."""
    if not places:
        return []

    fallback_order = sorted(places, key=lambda p: (p.rating or 0), reverse=True)[:_MAX_RESULTS]

    try:
        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(_Selection)
        candidates_text = "\n".join(
            f"- {p.name}: {p.description or 'no description'} (tags: {', '.join(p.tags) or 'none'})"
            for p in places
        )
        selection: _Selection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User interests: {', '.join(interests) or 'general sightseeing'}\n\n"
                        f"Candidate places:\n{candidates_text}\n\n"
                        f"Select up to {_MAX_RESULTS} names, best-matched first. "
                        "Only use names exactly as given above."
                    ),
                },
            ]
        )
        by_name = {p.name: p for p in places}
        selected = [by_name[name] for name in selection.selected_names if name in by_name]
        return selected[:_MAX_RESULTS] if selected else fallback_order
    except Exception:
        return fallback_order


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")
    agent_results = state.get("agent_results", {}) or {}

    if travel_request is None or not travel_request.destination:
        errors = state.get("errors", []) + [
            {"node": "sightseeing", "message": "Missing destination in travel request.", "retry_count": 0}
        ]
        return {"errors": errors}

    interests = travel_request.preferences.interests

    try:
        raw_places = search_places(
            destination=travel_request.destination,
            category=_CATEGORY,
            keywords=interests,
            max_results=15,
        )
    except Exception as exc:
        errors = state.get("errors", []) + [
            {"node": "sightseeing", "message": str(exc), "retry_count": 0}
        ]
        return {"errors": errors}

    places = [_to_place(raw) for raw in raw_places]
    selected = _rank_and_filter(places, interests)

    agent_results["sightseeing"] = [p.model_dump() for p in selected]
    return {"agent_results": agent_results}