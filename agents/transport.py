"""Transport agent.

Reads the structured TravelRequest and finds flight options when origin and
destination are both provided, or local destination transit options when
traveling within the destination city.
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


def _local_transit_fallback(travel_request: TravelRequest) -> list[dict]:
    """Provide structured local transit recommendations when inter-city origin is omitted."""
    destination = travel_request.destination or "Destination"
    return [
        {
            "mode": "local",
            "provider": f"{destination} Public Transit (Metro / Rail / Bus)",
            "origin": destination,
            "destination": f"{destination} City Center & Attractions",
            "notes": f"Recommended to use regional travel cards / transit passes for unlimited intra-city travel in {destination}.",
            "status": "recommended",
        }
    ]


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        return {
            "agent_results": {"transport": []},
            "errors": [
                {
                    "node": "transport",
                    "message": "No structured travel request available.",
                    "retry_count": 0,
                }
            ],
        }

    # If origin is not provided, provide destination local transit recommendations
    if not travel_request.origin or not travel_request.destination:
        return {
            "agent_results": {
                "transport": _local_transit_fallback(travel_request),
            }
        }

    try:
        from tools.flights import search_flights

        start_date = travel_request.dates.start_date
        flight_data = []

        if start_date:
            try:
                flight_data = search_flights(
                    origin=travel_request.origin,
                    destination=travel_request.destination,
                    departure_date=str(start_date),
                )
            except Exception:
                flight_data = []

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
                        "options (including flights if available, and local transit). "
                        "Respect the user's transport preference when possible."
                    ),
                },
            ]
        )

        options = selection.options or flight_data or _local_transit_fallback(travel_request)

        return {
            "agent_results": {
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
                "transport": _local_transit_fallback(travel_request),
            },
            "errors": errors,
        }