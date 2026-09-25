"""Fallback agent.

Handles travel-related requests that do not clearly belong to one of the
specialized agents. It uses the web search tool for general travel research,
events, festivals, advisories, customs, visa information, and niche requests.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from config import get_llm
from graph.state import TravelState
from schemas.travel import TravelRequest
from utils.helpers import load_prompt

_PROMPT = load_prompt("fallback")


class FallbackResult(BaseModel):
    results: list[dict] = Field(default_factory=list)
    reasoning: str = ""


def _fallback() -> list[dict]:
    """Deterministic fallback when general research fails."""
    return [
        {
            "status": "no_results",
            "reason": "No additional travel information was available.",
        }
    ]


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        return {
            "agent_results": {"fallback": _fallback()},
            "errors": [
                {
                    "node": "fallback",
                    "message": "No structured travel request available.",
                    "retry_count": 0,
                }
            ],
        }

    try:
        from tools.web_search import search

        query = (
            f"Travel information for {travel_request.destination}. "
            f"Interests: {travel_request.preferences.interests}. "
            f"Must visit: {travel_request.preferences.must_visit}. "
            f"Avoid: {travel_request.preferences.avoid}."
        )

        # Assumed tool interface based on tools/web_search.py:
        # search(query) -> list[dict]
        search_data = search(query)

        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(FallbackResult)

        result: FallbackResult = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Travel request:\n"
                        f"{travel_request.model_dump_json()}\n\n"
                        f"Web research results:\n"
                        f"{search_data}\n\n"
                        "Extract only useful travel information from the "
                        "provided research. Do not invent facts. Preserve "
                        "source information where available."
                    ),
                },
            ]
        )

        results = result.results

        if not results:
            results = search_data if search_data else _fallback()

        return {
            "agent_results": {
                "fallback": results,
            }
        }

    except Exception as exc:
        errors = state.get("errors", []) + [
            {
                "node": "fallback",
                "message": str(exc),
                "retry_count": 0,
            }
        ]

        return {
            "agent_results": {
                **(state.get("agent_results", {}) or {}),
                "fallback": _fallback(),
            },
            "errors": errors,
        }