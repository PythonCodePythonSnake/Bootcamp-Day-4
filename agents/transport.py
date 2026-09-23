"""Transport agent.

Reads the structured TravelRequest and finds relevant transportation
options between the origin and destination, while also considering
transport preferences.
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
                "reason": "Origin and destination are required for transport planning.",
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
            "transport_results": [],
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
            "transport_results": _fallback(travel_request),
            "transport_reasoning": (
                "Transport planning skipped because origin or destination "
                "is missing."
            ),
        }

    try:
        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(TransportSelection)

        # Assumed tool interface:
        # search_transport(travel_request) -> list[dict]
        #
        # The actual tool implementation is owned by the tools/ team.
        from tools.flights import search_transport

        transport_data = search_transport(travel_request)

        selection: TransportSelection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Travel request:\n{travel_request.model_dump_json()}\n\n"
                        f"Available transport data:\n{transport_data}\n\n"
                        "Select and organize the most relevant transport "
                        "options. Do not invent information that is not "
                        "present in the provided transport data."
                    ),
                },
            ]
        )

        options = selection.options

        if not options:
            options = (
                transport_data
                if transport_data
                else _fallback(travel_request)
            )

        return {
            "transport_results": options,
            "transport_reasoning": selection.reasoning,
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
            "transport_results": _fallback(travel_request),
            "transport_reasoning": (
                "Transport search failed; used fallback result."
            ),
            "errors": errors,
        }