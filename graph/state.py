"""Central LangGraph state for the travel itinerary workflow."""

from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict


from schemas.itinerary import Itinerary, Route
from schemas.travel import MissingInfo, TravelRequest


class AgentResults(TypedDict, total=False):
    """Structured outputs collected from each specialized agent."""

    sightseeing: list[dict[str, Any]]
    restaurant: list[dict[str, Any]]
    hotel: list[dict[str, Any]]
    transport: list[dict[str, Any]]
    fallback: list[dict[str, Any]]


class ErrorInfo(TypedDict, total=False):
    node: str
    message: str
    retry_count: int


def merge_agent_results(
    current: AgentResults | None,
    update: AgentResults | None,
) -> AgentResults:
    """Merge parallel agent results without overwriting other agents."""

    merged = dict(current or {})
    merged.update(update or {})

    return merged


def merge_errors(
    current: list[ErrorInfo] | None,
    update: list[ErrorInfo] | None,
) -> list[ErrorInfo]:
    """Merge errors produced by parallel agents."""

    return (current or []) + (update or [])


class TravelState(TypedDict, total=False):
    # --- raw input ---
    user_input: str

    # --- orchestrator output ---
    travel_request: TravelRequest
    missing_info: MissingInfo
    requires_human_input: bool

    # --- planner output ---
    planned_agents: list[str]
    planner_reasoning: Optional[str]

    # --- parallel specialist worker ---
    current_agent: str

    # --- agent results ---
    agent_results: Annotated[
        AgentResults,
        merge_agent_results,
    ]

    # --- maps/routes ---
    routes: list[Route]

    # --- synthesizer output ---
    itinerary: Optional[Itinerary]

    # --- human-in-the-loop ---
    human_feedback: Optional[str]
    approved: bool
    awaiting_human_input: bool

    # --- control/meta ---
    errors: Annotated[
        list[ErrorInfo],
        merge_errors,
    ]

    iteration_count: int