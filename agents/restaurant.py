"""Restaurant agent.

Reads the structured TravelRequest, resolves the destination to coordinates,
searches for nearby restaurants, and organizes the results according to the
user's cuisine, dietary, budget, and location preferences.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from config import get_llm
from graph.state import TravelState
from schemas.travel import TravelRequest
from utils.helpers import load_prompt

_PROMPT = load_prompt("restaurant")


class RestaurantSelection(BaseModel):
    restaurants: list[dict] = Field(default_factory=list)
    reasoning: str = ""


def _fallback(travel_request: TravelRequest) -> list[dict]:
    """Deterministic fallback when restaurant search fails."""
    return [
        {
            "name": "Restaurant search required",
            "location": travel_request.destination,
            "reason": "No live restaurant results were available from the places tool.",
        }
    ]


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "restaurant": [],
            },
            "errors": [
                {
                    "node": "restaurant",
                    "message": "No structured travel request available.",
                    "retry_count": 0,
                }
            ],
        }

    try:
        from tools.maps import geocode
        from tools.places import get_restaurants

        # Resolve destination into coordinates.
        location = geocode(travel_request.destination)

        if not location:
            raise ValueError(
                f"Could not geocode destination: {travel_request.destination}"
            )

        latitude = location["lat"]
        longitude = location["lon"]

        # Assumed tool interface based on tools/places.py:
        # get_restaurants(latitude, longitude) -> list[dict]
        restaurant_data = get_restaurants(
            latitude=latitude,
            longitude=longitude,
        )

        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(RestaurantSelection)

        selection: RestaurantSelection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Travel request:\n"
                        f"{travel_request.model_dump_json()}\n\n"
                        f"Available restaurant data:\n"
                        f"{restaurant_data}\n\n"
                        "Select and organize the most relevant restaurants "
                        "according to the user's interests, dietary "
                        "requirements, budget, and preferences. Do not "
                        "invent information that is not present in the "
                        "provided restaurant data."
                    ),
                },
            ]
        )

        restaurants = selection.restaurants

        if not restaurants:
            restaurants = (
                restaurant_data
                if restaurant_data
                else _fallback(travel_request)
            )

        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "restaurant": restaurants,
            }
        }

    except Exception as exc:
        errors = state.get("errors", []) + [
            {
                "node": "restaurant",
                "message": str(exc),
                "retry_count": 0,
            }
        ]

        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "restaurant": _fallback(travel_request),
            },
            "errors": errors,
        }