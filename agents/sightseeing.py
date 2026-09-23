"""Sightseeing agent.

Reads the structured TravelRequest, resolves the destination to coordinates,
searches for relevant attractions and points of interest, and organizes the
results according to the user's interests, must-visit places, and preferences.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from config import get_llm
from graph.state import TravelState
from schemas.travel import TravelRequest
from utils.helpers import load_prompt

_PROMPT = load_prompt("sightseeing")


class SightseeingSelection(BaseModel):
    places: list[dict] = Field(default_factory=list)
    reasoning: str = ""


def _fallback(travel_request: TravelRequest) -> list[dict]:
    """Deterministic fallback when sightseeing search fails."""
    return [
        {
            "name": "Sightseeing search required",
            "location": travel_request.destination,
            "reason": "No live sightseeing results were available from the places tool.",
        }
    ]


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "sightseeing": [],
            },
            "errors": [
                {
                    "node": "sightseeing",
                    "message": "No structured travel request available.",
                    "retry_count": 0,
                }
            ],
        }

    try:
        from tools.maps import geocode
        from tools.places import get_attractions, get_museums, get_parks

        # Resolve destination into coordinates.
        location = geocode(travel_request.destination)

        if not location:
            raise ValueError(
                f"Could not geocode destination: {travel_request.destination}"
            )

        latitude = location["lat"]
        longitude = location["lon"]

        # Search the main sightseeing categories.
        attractions = get_attractions(
            latitude=latitude,
            longitude=longitude,
        )

        museums = get_museums(
            latitude=latitude,
            longitude=longitude,
        )

        parks = get_parks(
            latitude=latitude,
            longitude=longitude,
        )

        sightseeing_data = (
            (attractions or [])
            + (museums or [])
            + (parks or [])
        )

        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(SightseeingSelection)

        selection: SightseeingSelection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Travel request:\n"
                        f"{travel_request.model_dump_json()}\n\n"
                        f"Available sightseeing data:\n"
                        f"{sightseeing_data}\n\n"
                        "Select and organize the most relevant sightseeing "
                        "places according to the user's interests, trip "
                        "intent, must-visit places, and avoid preferences. "
                        "Do not invent information that is not present in "
                        "the provided sightseeing data."
                    ),
                },
            ]
        )

        places = selection.places

        if not places:
            places = (
                sightseeing_data
                if sightseeing_data
                else _fallback(travel_request)
            )

        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "sightseeing": places,
            }
        }

    except Exception as exc:
        errors = state.get("errors", []) + [
            {
                "node": "sightseeing",
                "message": str(exc),
                "retry_count": 0,
            }
        ]

        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "sightseeing": _fallback(travel_request),
            },
            "errors": errors,
        }