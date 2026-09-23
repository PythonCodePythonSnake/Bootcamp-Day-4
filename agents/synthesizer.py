"""Itinerary synthesizer.

Combines the outputs of the specialized travel agents into a coherent
day-by-day itinerary. It does not independently search for travel data.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from config import get_llm
from graph.state import TravelState
from schemas.travel import TravelRequest
from schemas.itinerary import Itinerary
from utils.helpers import load_prompt

_PROMPT = load_prompt("synthesizer")


class SynthesisResult(BaseModel):
    itinerary: Itinerary | None = None
    reasoning: str = ""


def _fallback() -> dict:
    """Deterministic fallback when synthesis fails."""
    return {
        "status": "synthesis_failed",
        "message": (
            "The itinerary could not be generated from the available "
            "travel data."
        ),
    }


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        return {
            "itinerary": _fallback(),
            "errors": [
                {
                    "node": "synthesizer",
                    "message": "No structured travel request available.",
                    "retry_count": 0,
                }
            ],
        }

    try:
        llm = get_llm(temperature=0.2)
        structured_llm = llm.with_structured_output(SynthesisResult)

        agent_results = {
            "sightseeing": state.get("sightseeing_results", []),
            "restaurants": state.get("restaurant_results", []),
            "hotels": state.get("hotel_results", []),
            "transport": state.get("transport_results", []),
            "fallback": state.get("fallback_results", []),
            "routes": state.get("routes", []),
        }

        result: SynthesisResult = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Travel request:\n"
                        f"{travel_request.model_dump_json()}\n\n"
                        f"Available agent results:\n"
                        f"{agent_results}\n\n"
                        "Create a practical day-by-day itinerary using "
                        "only the available information. Respect the "
                        "requested dates, duration, preferences, budget, "
                        "and must-visit locations. Do not invent live "
                        "travel information."
                    ),
                },
            ]
        )

        if result.itinerary is None:
            return {
                "itinerary": _fallback(),
                "synthesis_reasoning": (
                    result.reasoning or "No itinerary was produced."
                ),
            }

        return {
            "itinerary": result.itinerary,
            "synthesis_reasoning": result.reasoning,
        }

    except Exception as exc:
        errors = state.get("errors", []) + [
            {
                "node": "synthesizer",
                "message": str(exc),
                "retry_count": 0,
            }
        ]

        return {
            "itinerary": _fallback(),
            "synthesis_reasoning": "Itinerary synthesis failed.",
            "errors": errors,
        }