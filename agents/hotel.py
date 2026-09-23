"""Hotel agent.

Reads the structured TravelRequest, resolves the destination to coordinates,
searches for nearby hotels, and organizes the results according to the user's
accommodation preferences and budget.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from config import get_llm
from graph.state import TravelState
from schemas.travel import TravelRequest
from utils.helpers import load_prompt

_PROMPT = load_prompt("hotel")


class HotelSelection(BaseModel):
    hotels: list[dict] = Field(default_factory=list)
    reasoning: str = ""


def _fallback(travel_request: TravelRequest) -> list[dict]:
    """Deterministic fallback when the hotel search fails."""
    return [
        {
            "name": "Hotel search required",
            "location": travel_request.destination,
            "reason": "No live hotel results were available from the hotel tool.",
        }
    ]


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "hotel": [],
            },
            "errors": [
                {
                    "node": "hotel",
                    "message": "No structured travel request available.",
                    "retry_count": 0,
                }
            ],
        }

    try:
        from tools.maps import geocode
        from tools.hotels import search_hotels

        # Resolve destination into coordinates.
        location = geocode(travel_request.destination)

        if not location:
            raise ValueError(
                f"Could not geocode destination: {travel_request.destination}"
            )

        latitude = location["lat"]
        longitude = location["lon"]

        # Assumed tool interface based on tools/hotels.py:
        # search_hotels(latitude, longitude) -> list[dict]
        hotel_data = search_hotels(
            latitude=latitude,
            longitude=longitude,
        )

        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(HotelSelection)

        selection: HotelSelection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Travel request:\n"
                        f"{travel_request.model_dump_json()}\n\n"
                        f"Available hotel data:\n"
                        f"{hotel_data}\n\n"
                        "Select and organize the most relevant hotel "
                        "options according to the user's accommodation "
                        "preference and budget. Do not invent information "
                        "that is not present in the provided hotel data."
                    ),
                },
            ]
        )

        hotels = selection.hotels

        if not hotels:
            hotels = hotel_data if hotel_data else _fallback(travel_request)

        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "hotel": hotels,
            }
        }

    except Exception as exc:
        errors = state.get("errors", []) + [
            {
                "node": "hotel",
                "message": str(exc),
                "retry_count": 0,
            }
        ]

        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "hotel": _fallback(travel_request),
            },
            "errors": errors,
        }