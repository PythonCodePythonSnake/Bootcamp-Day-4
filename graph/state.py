"""Central LangGraph state for the travel itinerary workflow."""

from __future__ import annotations

from typing import Any, Optional, TypedDict

from schemas.itinerary import Itinerary, Route
from schemas.travel import MissingInfo, TravelRequest


class AgentResults(TypedDict, total=False):
    """Raw structured outputs collected from each specialized agent, keyed by agent name."""

    sightseeing: list[dict[str, Any]]
    restaurant: list[dict[str, Any]]
    hotel: list[dict[str, Any]]
    transport: list[dict[str, Any]]
    fallback: list[dict[str, Any]]


class ErrorInfo(TypedDict, total=False):
    node: str
    message: str
    retry_count: int


class TravelState(TypedDict, total=False):
    # --- raw input ---
    user_input: str

    # --- orchestrator output ---
    travel_request: TravelRequest
    missing_info: MissingInfo
    requires_human_input: bool

    # --- planner output ---
    planned_agents: list[str]  # e.g. ["sightseeing", "restaurant", "hotel", "maps"]
    planner_reasoning: Optional[str]

    # --- agent results ---
    agent_results: AgentResults

    # --- maps/routes ---
    routes: list[Route]

    # --- synthesizer output ---
    itinerary: Optional[Itinerary]

    # --- human-in-the-loop ---
    human_feedback: Optional[str]
    approved: bool
    awaiting_human_input: bool

    # --- control/meta ---
    errors: list[ErrorInfo]
    iteration_count: int