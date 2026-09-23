"""Itinerary synthesizer.

Combines the outputs of the specialized travel agents and route tools into
a coherent day-by-day itinerary. It does not independently search for
travel data.
"""

from __future__ import annotations

from pydantic import BaseModel

from config import get_llm
from graph.state import TravelState
from schemas.itinerary import Itinerary
from schemas.travel import TravelRequest
from utils.helpers import load_prompt

_PROMPT = load_prompt("synthesizer")


class SynthesisResult(BaseModel):
    itinerary: Itinerary | None = None
    reasoning: str = ""


def _fallback(travel_request: TravelRequest) -> dict:
    """Deterministic fallback when synthesis fails."""
    return {
        "status": "synthesis_failed",
        "destination": travel_request.destination,
        "message": (
            "The itinerary could not be generated from the available "
            "travel data."
        ),
    }


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        return {
            "itinerary": None,
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

        # All specialized agent outputs are stored centrally.
        agent_results = state.get("agent_results", {}) or {}

        # Routes are stored separately because they have their own schema.
        routes = state.get("routes", []) or []

        available_data = {
            "sightseeing": agent_results.get("sightseeing", []),
            "restaurant": agent_results.get("restaurant", []),
            "hotel": agent_results.get("hotel", []),
            "transport": agent_results.get("transport", []),
            "fallback": agent_results.get("fallback", []),
            "routes": routes,
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
                        f"{available_data}\n\n"
                        "Create a practical day-by-day itinerary using "
                        "only the available information. Respect the "
                        "requested dates, duration, preferences, budget, "
                        "and must-visit locations. Use route information "
                        "when available. Do not invent live travel "
                        "information, prices, opening hours, availability, "
                        "or other facts that are not present in the "
                        "provided data."
                    ),
                },
            ]
        )

        if result.itinerary is None:
            return {
                "itinerary": None,
                "errors": state.get("errors", []) + [
                    {
                        "node": "synthesizer",
                        "message": (
                            result.reasoning or "No itinerary was produced."
                        ),
                        "retry_count": 0,
                    }
                ],
            }

        return {
            "itinerary": result.itinerary,
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
            "itinerary": None,
            "errors": errors,
        }