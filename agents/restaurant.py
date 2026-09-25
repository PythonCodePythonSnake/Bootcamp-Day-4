"""Restaurant agent.

Reads the structured TravelRequest, resolves the destination to coordinates,
searches for nearby restaurants, and organizes the results according to the
user's cuisine, dietary, budget, and location preferences.
"""

from __future__ import annotations

import traceback
from pydantic import BaseModel, Field

from config import get_llm
from graph.state import TravelState
from schemas.travel import TravelRequest
from utils.helpers import load_prompt

_PROMPT = load_prompt("restaurant")


class RestaurantSelection(BaseModel):
    restaurants: list[dict] = Field(default_factory=list)
    reasoning: str = ""


def _fallback_web_search(travel_request: TravelRequest) -> list[dict]:
    """Fallback to web search for restaurants if Overpass API fails."""
    try:
        from tools.web_search import search
        query = f"best restaurants food dining in {travel_request.destination} {', '.join(travel_request.preferences.dietary_requirements)}"
        print(f"  [RESTAURANT] Attempting web search fallback: '{query}'...")
        web_res = search(query, max_results=6)
        if web_res:
            print(f"  [RESTAURANT] Web search fallback returned {len(web_res)} items.")
            return [
                {
                    "name": item.get("title", f"Dining in {travel_request.destination}"),
                    "description": item.get("content", ""),
                    "location": travel_request.destination,
                    "url": item.get("url", ""),
                }
                for item in web_res
            ]
    except Exception as exc:
        print(f"  [RESTAURANT] Web search fallback failed: {exc}")

    return [
        {
            "name": f"Recommended Dining in {travel_request.destination}",
            "location": travel_request.destination,
            "reason": "Live API lookup was unavailable.",
        }
    ]


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        print("  [RESTAURANT ERROR] No travel_request in state.")
        return {
            "agent_results": {"restaurant": []},
            "errors": [
                {
                    "node": "restaurant",
                    "message": "No structured travel request available.",
                    "retry_count": 0,
                }
            ],
        }

    try:
        from tools.maps import geocode
        from tools.places import get_restaurants

        print(f"  [RESTAURANT] Geocoding destination: '{travel_request.destination}'...")
        location = geocode(travel_request.destination)
        print(f"  [RESTAURANT] Geocode result: {location}")

        if not location:
            raise ValueError(
                f"Could not geocode destination: {travel_request.destination}"
            )

        latitude = location["lat"]
        longitude = location["lon"]

        print(f"  [RESTAURANT] Querying restaurants at ({latitude:.4f}, {longitude:.4f})...")
        restaurant_data = get_restaurants(
            latitude=latitude,
            longitude=longitude,
        )
        print(f"  [RESTAURANT] Total restaurants returned: {len(restaurant_data or [])}")

        if not restaurant_data:
            print("  [RESTAURANT] No raw restaurants found, switching to web search fallback...")
            restaurant_data = _fallback_web_search(travel_request)

        print("  [RESTAURANT] Invoking LLM to select and rank restaurants...")
        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(RestaurantSelection)

        selection: RestaurantSelection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Travel request:\n"
                        f"{travel_request.model_dump_json()}\n\n"
                        f"Available restaurant data:\n"
                        f"{restaurant_data}\n\n"
                        "Select and organize the most relevant restaurants "
                        "according to the user's interests, dietary "
                        "requirements, budget, and preferences. Do not "
                        "invent information that is not present in the "
                        "provided restaurant data."
                    ),
                },
            ]
        )

        restaurants = selection.restaurants
        print(f"  [RESTAURANT] LLM selected {len(restaurants)} restaurants.")

        if not restaurants:
            restaurants = restaurant_data or _fallback_web_search(travel_request)

        return {
            "agent_results": {
                "restaurant": restaurants,
            }
        }

    except Exception as exc:
        print(f"  [RESTAURANT ERROR] Failed with exception: {exc}")
        traceback.print_exc()
        errors = state.get("errors", []) + [
            {
                "node": "restaurant",
                "message": str(exc),
                "retry_count": 0,
            }
        ]

        fallback_restaurants = _fallback_web_search(travel_request)
        return {
            "agent_results": {
                "restaurant": fallback_restaurants,
            },
            "errors": errors,
        }