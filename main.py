"""Entry point for the travel itinerary agent."""

from __future__ import annotations

import uuid

from langgraph.types import Command

from graph.workflow import build_workflow


def print_itinerary(itinerary):
    if itinerary is None:
        print("\nNo itinerary was generated.")
        return

    print("\n" + "=" * 60)
    print("TRAVEL ITINERARY")
    print("=" * 60)

    print(f"\nDestination: {itinerary.destination}")

    if itinerary.origin:
        print(f"Origin: {itinerary.origin}")

    print(f"Currency: {itinerary.currency}")

    if itinerary.total_estimated_cost is not None:
        print(
            f"Estimated total cost: "
            f"{itinerary.total_estimated_cost} {itinerary.currency}"
        )

    for day in itinerary.day_plans:
        print(f"\n--- Day {day.day_number} ---")

        if day.date:
            print(f"Date: {day.date}")

        if day.summary:
            print(day.summary)

        for block in day.blocks:
            slot_str = block.time_slot or "Scheduled"
            print(f"\n{slot_str} - {block.activity_type}")

            if block.place:
                print(f"Place: {block.place.name}")

            if block.restaurant:
                print(f"Restaurant: {block.restaurant.name}")

            if block.transport:
                print(
                    f"Transport: "
                    f"{block.transport.origin} -> "
                    f"{block.transport.destination}"
                )

            if block.notes:
                print(f"Notes: {block.notes}")

            if block.estimated_cost is not None:
                print(
                    f"Estimated cost: "
                    f"{block.estimated_cost} {itinerary.currency}"
                )

    if itinerary.notes:
        print("\nNotes:")
        for note in itinerary.notes:
            print(f"- {note}")


def handle_interrupt(workflow, result, config):
    """Handle one LangGraph interrupt and return the resumed result."""

    interrupt_data = result["__interrupt__"][0].value
    interrupt_type = interrupt_data.get("type")

    if interrupt_type == "missing_info":
        questions = interrupt_data.get("questions", [])

        print("\nAdditional information is required:")

        for question in questions:
            print(f"- {question}")

        answer = input("\nYour answer:\n> ").strip()

        if not answer:
            print("No answer provided.")
            return None

        return workflow.invoke(
            Command(resume=answer),
            config=config,
        )

    if interrupt_type == "review":
        itinerary_data = interrupt_data.get("itinerary")

        if itinerary_data:
            from schemas.itinerary import Itinerary

            itinerary = Itinerary(**itinerary_data)
            print_itinerary(itinerary)

        print("\n" + "=" * 60)

        decision = input(
            "Approve itinerary? [y/n]\n> "
        ).strip().lower()

        if decision in {"y", "yes"}:
            return workflow.invoke(
                Command(
                    resume={
                        "approved": True,
                        "feedback": None,
                    }
                ),
                config=config,
            )

        feedback = input(
            "\nWhat would you like to change?\n> "
        ).strip()

        return workflow.invoke(
            Command(
                resume={
                    "approved": False,
                    "feedback": feedback,
                }
            ),
            config=config,
        )

    print("Unknown human interaction requested.")
    return None


def main():
    workflow = build_workflow()

    thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    print("Travel Itinerary Agent")
    print("=" * 60)

    user_input = input(
        "\nWhat kind of trip would you like to plan?\n> "
    ).strip()

    if not user_input:
        print("No travel request provided.")
        return

    state = {
        "user_input": user_input,
        "iteration_count": 0,
        "errors": [],
    }

    result = workflow.invoke(
        state,
        config=config,
    )

    while "__interrupt__" in result:
        result = handle_interrupt(
            workflow,
            result,
            config,
        )

        if result is None:
            return

    final_state = result

    # Only print errors/warnings at the end; itinerary was already printed on review
    if final_state.get("errors"):
        print("\nWarnings/errors:")

        for error in final_state["errors"]:
            print(
                f"- {error.get('node', 'unknown')}: "
                f"{error.get('message', 'Unknown error')}"
            )


if __name__ == "__main__":
    main()