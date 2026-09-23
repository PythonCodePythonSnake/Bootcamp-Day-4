"""Transport agent.

Reads the structured TravelRequest and finds relevant flight options between
the origin and destination while considering the user's transport preference.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from config import get_llm
from graph.state import TravelState
from schemas.travel import TravelRequest
from utils.helpers import load_prompt

_PROMPT = load_prompt("transport")


class TransportSelection(BaseModel):
    options: list[dict] = Field(default_factory=list)
    reasoning: str = ""


def _fallback(travel_request: TravelRequest) -> list[dict]:
    """Deterministic fallback when transport search fails."""
    origin = travel_request.origin
    destination = travel_request.destination

    if not origin or not destination:
        return [
            {
                "status": "insufficient_information",
                "reason": (
                    "Origin and destination are required for transport "
                    "planning."
                ),
            }
        ]

    return [
        {
            "origin": origin,
            "destination": destination,
            "status": "search_required",
            "reason": "No live transport results were available.",
        }
    ]


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "transport": [],
            },
            "errors": [
                {
                    "node": "transport",
                    "message": "No structured travel request available.",
                    "retry_count": 0,
                }
            ],
        }

    if not travel_request.origin or not travel_request.destination:
        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "transport": _fallback(travel_request),
            }
        }

    try:
        from tools.flights import search_flights

        # Assumed tool interface based on tools/flights.py:
        # search_flights(origin, destination, travel_date) -> list[dict]
        #
        # Exact airport-code resolution can be added to the tool layer later.
        start_date = travel_request.dates.start_date

        if start_date is None:
            raise ValueError(
                "A travel start date is required for flight search."
            )

        flight_data = search_flights(
            origin=travel_request.origin,
            destination=travel_request.destination,
            travel_date=start_date,
        )

        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(TransportSelection)

        selection: TransportSelection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Travel request:\n"
                        f"{travel_request.model_dump_json()}\n\n"
                        f"Available flight data:\n"
                        f"{flight_data}\n\n"
                        "Select and organize the most relevant transport "
                        "options. Respect the user's transport preference "
                        "when possible. Do not invent information that is "
                        "not present in the provided flight data."
                    ),
                },
            ]
        )

        options = selection.options

        if not options:
            options = (
                flight_data
                if flight_data
                else _fallback(travel_request)
            )

        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "transport": options,
            }
        }

    except Exception as exc:
        errors = state.get("errors", []) + [
            {
                "node": "transport",
                "message": str(exc),
                "retry_count": 0,
            }
        ]

        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "transport": _fallback(travel_request),
            },
            "errors": errors,
        }