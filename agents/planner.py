"""Planner agent.

Reads the structured TravelRequest and decides which specialized agents are
actually needed for this trip — it does not invent travel data itself, and
it avoids invoking agents that aren't relevant (e.g. skip Transport if
origin/destination transit isn't in scope).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from config import get_llm
from graph.state import TravelState
from schemas.travel import TravelRequest
from utils.helpers import load_prompt

_PROMPT = load_prompt("planner")

VALID_AGENTS = {"sightseeing", "restaurant", "hotel", "transport", "fallback"}


class AgentSelection(BaseModel):
    agents: list[str] = Field(default_factory=list)
    reasoning: str = ""


def _rule_based_fallback(travel_request: TravelRequest) -> list[str]:
    """Deterministic backup used if the LLM call fails, so planning never blocks the graph."""
    interests = [i.lower() for i in travel_request.preferences.interests]
    agents: set[str] = set()

    if any(k in interests for k in ("food", "cuisine", "restaurants", "dining")):
        agents.add("restaurant")
    if any(k in interests for k in ("history", "historical", "culture", "museum", "sightseeing")):
        agents.add("sightseeing")

    if not agents:
        # Default to a reasonably complete trip when interests are unclear.
        agents.update({"sightseeing", "restaurant"})

    agents.add("hotel")

    if travel_request.origin and travel_request.destination:
        agents.add("transport")

    return sorted(agents)


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        return {
            "planned_agents": ["fallback"],
            "planner_reasoning": "No structured travel request available; routing to fallback.",
        }

    try:
        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(AgentSelection)
        selection: AgentSelection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Travel request:\n{travel_request.model_dump_json()}\n\n"
                        f"Available agents: {sorted(VALID_AGENTS)}\n"
                        "Select only the agents genuinely needed for this trip."
                    ),
                },
            ]
        )
        agents = [a for a in selection.agents if a in VALID_AGENTS]
        reasoning = selection.reasoning

        if not agents:
            agents = _rule_based_fallback(travel_request)
            reasoning = reasoning or "LLM returned no valid agents; used rule-based fallback."

    except Exception as exc:
        errors = state.get("errors", []) + [
            {"node": "planner", "message": str(exc), "retry_count": 0}
        ]
        agents = _rule_based_fallback(travel_request)
        return {
            "planned_agents": agents,
            "planner_reasoning": "LLM planning failed; used rule-based fallback.",
            "errors": errors,
        }

    return {"planned_agents": agents, "planner_reasoning": reasoning}