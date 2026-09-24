"""Constructs the LangGraph workflow for the travel itinerary planner."""

from __future__ import annotations

import time
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Send, interrupt

from agents.fallback import run as fallback_run
from agents.hotel import run as hotel_run
from agents.orchestrator import run as orchestrator_run
from agents.planner import run as planner_run
from agents.restaurant import run as restaurant_run
from agents.sightseeing import run as sightseeing_run
from agents.synthesizer import run as synthesizer_run
from agents.transport import run as transport_run
from graph.state import TravelState


VALID_AGENTS = {
    "sightseeing",
    "restaurant",
    "hotel",
    "transport",
    "fallback",
}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def orchestrator_node(state: TravelState) -> TravelState:
    start = time.perf_counter()

    print("\n[ORCHESTRATOR] Starting...")

    result = orchestrator_run(state)

    elapsed = time.perf_counter() - start

    if result.get("requires_human_input"):
        print(
            f"[ORCHESTRATOR] Missing required information "
            f"({elapsed:.2f}s)"
        )
    else:
        print(
            f"[ORCHESTRATOR] Travel request extracted "
            f"({elapsed:.2f}s)"
        )

    return result


def human_clarification_node(state: TravelState) -> TravelState:
    """Pause the graph and ask the human for missing information."""

    missing = state.get("missing_info")

    questions = (
        missing.questions
        if missing
        else ["Could you provide more trip details?"]
    )

    print("\n[HUMAN INPUT] Additional information required.")

    answer = interrupt(
        {
            "type": "missing_info",
            "questions": questions,
        }
    )

    existing_input = state.get("user_input", "")

    return {
        "user_input": f"{existing_input}\n{answer}".strip(),
        "awaiting_human_input": False,
    }


def planner_node(state: TravelState) -> TravelState:
    start = time.perf_counter()

    print("\n[PLANNER] Deciding which agents are required...")

    result = planner_run(state)

    elapsed = time.perf_counter() - start

    agents = result.get("planned_agents", [])

    print(
        f"[PLANNER] Selected: "
        f"{', '.join(agents)} "
        f"({elapsed:.2f}s)"
    )

    if state.get("human_feedback"):
        print(
            f"[PLANNER] Using human feedback: "
            f"{state['human_feedback']}"
        )

    return result


def specialist_node(state: TravelState) -> TravelState:
    """Run one selected specialist agent.

    Multiple instances of this node may execute in parallel through Send.
    """

    agent = state.get("current_agent")

    if not agent:
        return {
            "errors": [
                {
                    "node": "specialist",
                    "message": "No current_agent was provided.",
                    "retry_count": 0,
                }
            ]
        }

    start = time.perf_counter()

    print(f"\n[{agent.upper()}] Starting...")

    runners = {
        "sightseeing": sightseeing_run,
        "restaurant": restaurant_run,
        "hotel": hotel_run,
        "transport": transport_run,
        "fallback": fallback_run,
    }

    runner = runners.get(agent)

    if runner is None:
        return {
            "errors": [
                {
                    "node": "specialist",
                    "message": f"Unknown agent: {agent}",
                    "retry_count": 0,
                }
            ]
        }

    result = runner(state)

    elapsed = time.perf_counter() - start

    agent_results = result.get("agent_results", {})
    agent_output = agent_results.get(agent, [])

    print(
        f"[{agent.upper()}] Done "
        f"({elapsed:.2f}s) - "
        f"{len(agent_output)} results"
    )

    return result


def maps_node(state: TravelState) -> TravelState:
    """Process routes after all selected specialist agents finish."""

    start = time.perf_counter()

    print("\n[MAPS] Processing routes...")

    # The current routes.py supports origin -> destination routing.
    # Waypoint optimization is not implemented yet.
    #
    # Route integration can be added here once the itinerary places have
    # been selected and their coordinates are available.

    elapsed = time.perf_counter() - start

    print(f"[MAPS] Done ({elapsed:.2f}s)")

    return {}


def synthesizer_node(state: TravelState) -> TravelState:
    start = time.perf_counter()

    print("\n[SYNTHESIZER] Building itinerary...")

    result = synthesizer_run(state)

    elapsed = time.perf_counter() - start

    if result.get("itinerary") is not None:
        print(
            f"[SYNTHESIZER] Itinerary generated "
            f"({elapsed:.2f}s)"
        )
    else:
        print(
            f"[SYNTHESIZER] Failed to generate itinerary "
            f"({elapsed:.2f}s)"
        )

    return result


def human_review_node(state: TravelState) -> TravelState:
    """Pause the graph for human approval or requested changes."""

    itinerary = state.get("itinerary")

    print("\n[HUMAN REVIEW] Waiting for approval...")

    decision = interrupt(
        {
            "type": "review",
            "itinerary": (
                itinerary.model_dump()
                if itinerary
                else None
            ),
        }
    )

    approved = bool(decision.get("approved", False))
    feedback = decision.get("feedback")

    if approved:
        print("[HUMAN REVIEW] Itinerary approved.")
    else:
        print(
            "[HUMAN REVIEW] Itinerary rejected. "
            "Returning to planner."
        )

    return {
        "approved": approved,
        "human_feedback": feedback,
        "awaiting_human_input": False,
    }


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

def route_after_orchestrator(
    state: TravelState,
) -> Literal["human_clarification", "planner"]:

    if state.get("requires_human_input"):
        return "human_clarification"

    return "planner"


def route_planned_agents(
    state: TravelState,
) -> list[Send]:
    """Fan out selected specialist agents in parallel."""

    planned = state.get("planned_agents", []) or []

    targets = [
        agent
        for agent in planned
        if agent in VALID_AGENTS
    ]

    if not targets:
        targets = ["fallback"]

    print(
        "\n[PLANNER] Launching agents in parallel: "
        + ", ".join(targets)
    )

    return [
        Send(
            "specialist",
            {
                **state,
                "current_agent": agent,
            },
        )
        for agent in targets
    ]


def route_after_review(
    state: TravelState,
) -> Literal["end", "planner"]:

    if state.get("approved"):
        return "end"

    return "planner"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_workflow():
    """Build and compile the LangGraph workflow."""

    graph = StateGraph(TravelState)

    graph.add_node(
        "orchestrator",
        orchestrator_node,
    )

    graph.add_node(
        "human_clarification",
        human_clarification_node,
    )

    graph.add_node(
        "planner",
        planner_node,
    )

    graph.add_node(
        "specialist",
        specialist_node,
    )

    graph.add_node(
        "maps",
        maps_node,
    )

    graph.add_node(
        "synthesizer",
        synthesizer_node,
    )

    graph.add_node(
        "human_review",
        human_review_node,
    )

    graph.set_entry_point("orchestrator")

    # --------------------------------------------------
    # Orchestrator
    # --------------------------------------------------

    graph.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            "human_clarification": "human_clarification",
            "planner": "planner",
        },
    )

    # --------------------------------------------------
    # Human clarification -> orchestrator
    # --------------------------------------------------

    graph.add_edge(
        "human_clarification",
        "orchestrator",
    )

    # --------------------------------------------------
    # Planner -> parallel specialists
    # --------------------------------------------------

    graph.add_conditional_edges(
        "planner",
        route_planned_agents,
        ["specialist"],
    )

    # --------------------------------------------------
    # Parallel specialists -> maps
    # --------------------------------------------------

    graph.add_edge(
        "specialist",
        "maps",
    )

    # --------------------------------------------------
    # Maps -> synthesizer -> human review
    # --------------------------------------------------

    graph.add_edge(
        "maps",
        "synthesizer",
    )

    graph.add_edge(
        "synthesizer",
        "human_review",
    )

    # --------------------------------------------------
    # Human review -> end or regeneration
    # --------------------------------------------------

    graph.add_conditional_edges(
        "human_review",
        route_after_review,
        {
            "end": END,
            "planner": "planner",
        },
    )

    checkpointer = MemorySaver()

    return graph.compile(
        checkpointer=checkpointer,
    )