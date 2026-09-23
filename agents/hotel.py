"""Hotel agent.

Reads the structured TravelRequest and searches for accommodation options
matching the user's destination, dates, budget, and preferences.
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
    """Deterministic fallback when the hotel search/LLM call fails."""
    destination = travel_request.destination

    return [
        {
            "name": "Hotel search required",
            "location": destination,
            "reason": "No live hotel results were available from the hotel tool.",
        }
    ]


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        return {
            "hotel_results": [],
            "errors": [
                {
                    "node": "hotel",
                    "message": "No structured travel request available.",
                    "retry_count": 0,
                }
            ],
        }

    try:
        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(HotelSelection)

        # Assumed tool interface:
        # search_hotels(travel_request) -> list[dict]
        #
        # The actual tool implementation is owned by the tools/ team.
        from tools.hotels import search_hotels

        hotel_data = search_hotels(travel_request)

        selection: HotelSelection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Travel request:\n{travel_request.model_dump_json()}\n\n"
                        f"Available hotel data:\n{hotel_data}\n\n"
                        "Select and organize the most relevant hotel options. "
                        "Do not invent information that is not present in the "
                        "provided hotel data."
                    ),
                },
            ]
        )

        hotels = selection.hotels

        if not hotels:
            hotels = hotel_data if hotel_data else _fallback(travel_request)

        return {
            "hotel_results": hotels,
            "hotel_reasoning": selection.reasoning,
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
            "hotel_results": _fallback(travel_request),
            "hotel_reasoning": "Hotel search failed; used fallback result.",
            "errors": errors,
        }