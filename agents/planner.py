"""Planner agent.

Reads the structured TravelRequest and decides which specialized agents are
actually needed for this trip. It routes only to agents relevant to the
request and considers human feedback when regenerating an itinerary.
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
    """Deterministic backup used if the LLM call fails."""
    interests = [
        interest.lower()
        for interest in travel_request.preferences.interests
    ]

    agents: set[str] = set()

    if any(
        keyword in interests
        for keyword in (
            "food",
            "cuisine",
            "restaurant",
            "restaurants",
            "dining",
        )
    ):
        agents.add("restaurant")

    if any(
        keyword in interests
        for keyword in (
            "history",
            "historical",
            "culture",
            "cultural",
            "museum",
            "sightseeing",
            "landmark",
            "attraction",
        )
    ):
        agents.add("sightseeing")

    if not agents:
        agents.update({"sightseeing", "restaurant"})

    # Accommodation is generally relevant for multi-day trips.
    if (
        travel_request.dates.duration_days is None
        or travel_request.dates.duration_days > 1
    ):
        agents.add("hotel")

    # Transport requires both endpoints.
    if travel_request.origin and travel_request.destination:
        agents.add("transport")

    return sorted(agents)


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        return {
            "planned_agents": ["fallback"],
            "planner_reasoning": (
                "No structured travel request available; "
                "routing to fallback."
            ),
        }

    try:
        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(AgentSelection)

        human_feedback = state.get("human_feedback")

        user_content = (
            f"Travel request:\n"
            f"{travel_request.model_dump_json()}\n\n"
            f"Available agents: {sorted(VALID_AGENTS)}\n"
            "Select only the agents genuinely needed for this trip."
        )

        if human_feedback:
            user_content += (
                f"\n\nHuman feedback from the previous itinerary review:\n"
                f"{human_feedback}\n\n"
                "Use this feedback to determine which agents need to be "
                "rerun or added for the revised itinerary."
            )

        selection: AgentSelection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": user_content,
                },
            ]
        )

        agents = [
            agent
            for agent in selection.agents
            if agent in VALID_AGENTS
        ]

        reasoning = selection.reasoning

        if not agents:
            agents = _rule_based_fallback(travel_request)
            reasoning = (
                reasoning
                or "LLM returned no valid agents; "
                "used rule-based fallback."
            )

        return {
            "planned_agents": agents,
            "planner_reasoning": reasoning,
        }

    except Exception as exc:
        errors = state.get("errors", []) + [
            {
                "node": "planner",
                "message": str(exc),
                "retry_count": 0,
            }
        ]

        agents = _rule_based_fallback(travel_request)

        return {
            "planned_agents": agents,
            "planner_reasoning": (
                "LLM planning failed; used rule-based fallback."
            ),
            "errors": errors,
        }