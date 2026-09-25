"""Sightseeing agent.

Reads the structured TravelRequest, resolves the destination to coordinates,
searches for relevant attractions and points of interest, and organizes the
results according to the user's interests, must-visit places, and preferences.
"""

from __future__ import annotations

import traceback
from pydantic import BaseModel, Field

from config import get_llm
from graph.state import TravelState
from schemas.travel import TravelRequest
from utils.helpers import load_prompt

_PROMPT = load_prompt("sightseeing")


class SightseeingSelection(BaseModel):
    places: list[dict] = Field(default_factory=list)
    reasoning: str = ""


def _fallback_web_search(travel_request: TravelRequest) -> list[dict]:
    """Fallback to web search for sightseeing if Overpass API fails."""
    try:
        from tools.web_search import search
        query = f"top attractions things to do sightseeing in {travel_request.destination}"
        print(f"  [SIGHTSEEING] Attempting web search fallback: '{query}'...")
        web_res = search(query, max_results=6)
        if web_res:
            print(f"  [SIGHTSEEING] Web search fallback returned {len(web_res)} items.")
            return [
                {
                    "name": item.get("title", f"Attraction in {travel_request.destination}"),
                    "description": item.get("content", ""),
                    "location": travel_request.destination,
                    "url": item.get("url", ""),
                }
                for item in web_res
            ]
    except Exception as exc:
        print(f"  [SIGHTSEEING] Web search fallback failed: {exc}")

    return [
        {
            "name": f"Top Sightseeing in {travel_request.destination}",
            "location": travel_request.destination,
            "reason": "Live API lookup was unavailable.",
        }
    ]


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        print("  [SIGHTSEEING ERROR] No travel_request in state.")
        return {
            "agent_results": {"sightseeing": []},
            "errors": [
                {
                    "node": "sightseeing",
                    "message": "No structured travel request available.",
                    "retry_count": 0,
                }
            ],
        }

    try:
        from tools.maps import geocode
        from tools.places import get_attractions, get_museums, get_parks

        print(f"  [SIGHTSEEING] Geocoding destination: '{travel_request.destination}'...")
        location = geocode(travel_request.destination)
        print(f"  [SIGHTSEEING] Geocode result: {location}")

        if not location:
            raise ValueError(
                f"Could not geocode destination: {travel_request.destination}"
            )

        latitude = location["lat"]
        longitude = location["lon"]

        print(f"  [SIGHTSEEING] Querying attractions at ({latitude:.4f}, {longitude:.4f})...")
        attractions = get_attractions(latitude=latitude, longitude=longitude)
        print(f"  [SIGHTSEEING] Attractions count: {len(attractions or [])}")

        print(f"  [SIGHTSEEING] Querying museums at ({latitude:.4f}, {longitude:.4f})...")
        museums = get_museums(latitude=latitude, longitude=longitude)
        print(f"  [SIGHTSEEING] Museums count: {len(museums or [])}")

        print(f"  [SIGHTSEEING] Querying parks at ({latitude:.4f}, {longitude:.4f})...")
        parks = get_parks(latitude=latitude, longitude=longitude)
        print(f"  [SIGHTSEEING] Parks count: {len(parks or [])}")

        sightseeing_data = (
            (attractions or [])
            + (museums or [])
            + (parks or [])
        )
        print(f"  [SIGHTSEEING] Total raw places: {len(sightseeing_data)}")

        if not sightseeing_data:
            print("  [SIGHTSEEING] No raw places found, switching to web search fallback...")
            sightseeing_data = _fallback_web_search(travel_request)

        print("  [SIGHTSEEING] Invoking LLM to filter and rank places...")
        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(SightseeingSelection)

        selection: SightseeingSelection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Travel request:\n"
                        f"{travel_request.model_dump_json()}\n\n"
                        f"Available sightseeing data:\n"
                        f"{sightseeing_data}\n\n"
                        "Select and organize the most relevant sightseeing "
                        "places according to the user's interests, trip "
                        "intent, must-visit places, and avoid preferences. "
                        "Do not invent information that is not present in "
                        "the provided sightseeing data."
                    ),
                },
            ]
        )

        places = selection.places
        print(f"  [SIGHTSEEING] LLM selected {len(places)} places.")

        if not places:
            places = sightseeing_data or _fallback_web_search(travel_request)

        return {
            "agent_results": {
                "sightseeing": places,
            }
        }

    except Exception as exc:
        print(f"  [SIGHTSEEING ERROR] Failed with exception: {exc}")
        traceback.print_exc()
        errors = state.get("errors", []) + [
            {
                "node": "sightseeing",
                "message": str(exc),
                "retry_count": 0,
            }
        ]

        fallback_places = _fallback_web_search(travel_request)
        return {
            "agent_results": {
                "sightseeing": fallback_places,
            },
            "errors": errors,
        }