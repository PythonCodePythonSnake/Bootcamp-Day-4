"""Constructs the LangGraph workflow for the travel itinerary planner."""

from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from agents.fallback import run as fallback_run
from agents.hotel import run as hotel_run
from agents.orchestrator import run as orchestrator_run
from agents.planner import run as planner_run
from agents.restaurant import run as restaurant_run
from agents.sightseeing import run as sightseeing_run
from agents.synthesizer import run as synthesizer_run
from agents.transport import run as transport_run
from graph.state import TravelState
from schemas.itinerary import Route
from tools.routes import optimize_route

VALID_AGENTS = {"sightseeing", "restaurant", "hotel", "transport", "fallback"}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def orchestrator_node(state: TravelState) -> TravelState:
    return orchestrator_run(state)


def human_clarification_node(state: TravelState) -> TravelState:
    """Pause the graph and ask the human for missing essential information."""
    missing = state.get("missing_info")
    questions = missing.questions if missing else ["Could you provide more trip details?"]

    answer = interrupt({"type": "missing_info", "questions": questions})

    existing_input = state.get("user_input", "")
    return {
        "user_input": f"{existing_input}\n{answer}".strip(),
        "awaiting_human_input": False,
    }


def planner_node(state: TravelState) -> TravelState:
    return planner_run(state)


def sightseeing_node(state: TravelState) -> TravelState:
    return sightseeing_run(state)


def restaurant_node(state: TravelState) -> TravelState:
    return restaurant_run(state)


def hotel_node(state: TravelState) -> TravelState:
    return hotel_run(state)


def transport_node(state: TravelState) -> TravelState:
    return transport_run(state)


def fallback_node(state: TravelState) -> TravelState:
    return fallback_run(state)


def maps_node(state: TravelState) -> TravelState:
    """Compute an efficient visiting order/route from agent results using the routes tool."""
    results = state.get("agent_results", {}) or {}
    waypoints: list[str] = []

    for place in results.get("sightseeing", []) or []:
        name = place.get("name")
        if name:
            waypoints.append(name)
    for restaurant in results.get("restaurant", []) or []:
        name = restaurant.get("name")
        if name:
            waypoints.append(name)

    if len(waypoints) < 2:
        return {}

    try:
        raw_route = optimize_route(waypoints=waypoints)
        route = Route(**raw_route)
        routes = state.get("routes", []) + [route]
        return {"routes": routes}
    except Exception as exc:  # a tool failure should not crash the whole graph
        errors = state.get("errors", []) + [
            {"node": "maps", "message": str(exc), "retry_count": 0}
        ]
        return {"errors": errors}


def synthesizer_node(state: TravelState) -> TravelState:
    return synthesizer_run(state)


def human_review_node(state: TravelState) -> TravelState:
    """Pause the graph for the human to approve the itinerary or request changes."""
    itinerary = state.get("itinerary")

    decision = interrupt(
        {
            "type": "review",
            "itinerary": itinerary.model_dump() if itinerary else None,
        }
    )
    # Expected shape: {"approved": bool, "feedback": Optional[str]}
    approved = bool(decision.get("approved", False))
    feedback = decision.get("feedback")

    return {
        "approved": approved,
        "human_feedback": feedback,
        "awaiting_human_input": False,
    }


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

def route_after_orchestrator(state: TravelState) -> Literal["human_clarification", "planner"]:
    if state.get("requires_human_input"):
        return "human_clarification"
    return "planner"


def route_planned_agents(state: TravelState) -> list[str]:
    """Fan out only to the agents the planner decided are actually needed."""
    planned = state.get("planned_agents", []) or []
    targets = [agent for agent in planned if agent in VALID_AGENTS]
    return targets or ["fallback"]


def route_after_review(state: TravelState) -> Literal["end", "planner"]:
    if state.get("approved"):
        return "end"
    return "planner"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_workflow():
    """Build and compile the LangGraph workflow with an in-memory checkpointer
    (required for interrupt-based human-in-the-loop)."""
    graph = StateGraph(TravelState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("human_clarification", human_clarification_node)
    graph.add_node("planner", planner_node)
    graph.add_node("sightseeing", sightseeing_node)
    graph.add_node("restaurant", restaurant_node)
    graph.add_node("hotel", hotel_node)
    graph.add_node("transport", transport_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("maps", maps_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("human_review", human_review_node)

    graph.set_entry_point("orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {"human_clarification": "human_clarification", "planner": "planner"},
    )
    graph.add_edge("human_clarification", "orchestrator")

    graph.add_conditional_edges(
        "planner",
        route_planned_agents,
        {agent: agent for agent in VALID_AGENTS},
    )

    # All specialized agents fan back in to maps before synthesis.
    for agent in VALID_AGENTS:
        graph.add_edge(agent, "maps")

    graph.add_edge("maps", "synthesizer")
    graph.add_edge("synthesizer", "human_review")

    graph.add_conditional_edges(
        "human_review",
        route_after_review,
        {"end": END, "planner": "planner"},
    )

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)