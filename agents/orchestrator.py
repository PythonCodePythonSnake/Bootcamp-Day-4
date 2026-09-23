"""Orchestrator agent.

Extracts a structured TravelRequest from raw user text, merges it with any
previously known fields, and decides whether essential information is
missing. Does NOT perform travel research — that is handled by the planner
and specialized agents.
"""

from __future__ import annotations

from config import get_llm
from graph.state import TravelState
from schemas.travel import MissingInfo, TravelRequest
from utils.helpers import load_prompt

_PROMPT = load_prompt("orchestrator")


def _detect_missing(travel_request: TravelRequest) -> MissingInfo:
    """Determine which essential fields are still missing."""
    missing_fields: list[str] = []
    questions: list[str] = []

    if not travel_request.destination:
        missing_fields.append("destination")
        questions.append("Where would you like to travel to?")

    has_duration = travel_request.dates.duration_days is not None
    has_exact_dates = bool(
        travel_request.dates.start_date
        and travel_request.dates.end_date
    )

    if not has_duration and not has_exact_dates:
        missing_fields.append("dates")
        questions.append(
            "What dates, or how many days, is your trip?"
        )

    if travel_request.budget.amount is None:
        missing_fields.append("budget")
        questions.append(
            "What is your approximate budget for this trip?"
        )

    return MissingInfo(
        fields=missing_fields,
        questions=questions,
    )


def run(state: TravelState) -> TravelState:
    """Extract or update the structured TravelRequest from user input."""
    user_input = state.get("user_input", "")
    existing = state.get("travel_request")
    human_feedback = state.get("human_feedback")

    context_parts: list[str] = []

    if existing:
        context_parts.append(
            "Previously extracted information — merge with and update "
            "this information. Do not discard known fields unless the "
            "new user input contradicts them:\n"
            f"{existing.model_dump_json()}"
        )

    if human_feedback:
        context_parts.append(
            "Human feedback from the previous itinerary review:\n"
            f"{human_feedback}\n"
            "Use this as additional context for the revised request."
        )

    context = ""

    if context_parts:
        context = "\n\n" + "\n\n".join(context_parts)

    try:
        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(TravelRequest)

        travel_request: TravelRequest = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": f"{user_input}{context}",
                },
            ]
        )

    except Exception as exc:
        errors = state.get("errors", []) + [
            {
                "node": "orchestrator",
                "message": str(exc),
                "retry_count": 0,
            }
        ]

        fallback_request = existing or TravelRequest(
            raw_text=user_input
        )

        missing_info = _detect_missing(fallback_request)

        fallback_request.missing_info = missing_info
        fallback_request.requires_human_input = True

        return {
            "travel_request": fallback_request,
            "missing_info": missing_info,
            "requires_human_input": True,
            "errors": errors,
        }

    travel_request.raw_text = user_input

    missing_info = _detect_missing(travel_request)

    travel_request.missing_info = missing_info
    travel_request.requires_human_input = not missing_info.is_complete

    return {
        "travel_request": travel_request,
        "missing_info": missing_info,
        "requires_human_input": travel_request.requires_human_input,
    }