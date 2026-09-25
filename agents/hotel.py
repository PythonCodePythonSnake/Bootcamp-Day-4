"""Hotel agent.

Reads the structured TravelRequest, resolves the destination to coordinates,
searches for nearby hotels, and organizes the results according to the user's
accommodation preferences and budget.
"""

from __future__ import annotations

import traceback
from pydantic import BaseModel, Field

from config import get_llm
from graph.state import TravelState
from schemas.travel import TravelRequest
from utils.helpers import load_prompt

_PROMPT = load_prompt("hotel")


class HotelSelection(BaseModel):
    hotels: list[dict] = Field(default_factory=list)
    reasoning: str = ""


def _fallback_web_search(travel_request: TravelRequest) -> list[dict]:
    """Fallback to web search for hotels if Overpass API fails."""
    try:
        from tools.web_search import search
        query = f"best hotels places to stay in {travel_request.destination} budget {travel_request.budget.amount or ''}"
        print(f"  [HOTEL] Attempting web search fallback: '{query}'...")
        web_res = search(query, max_results=5)
        if web_res:
            print(f"  [HOTEL] Web search fallback returned {len(web_res)} items.")
            return [
                {
                    "name": item.get("title", f"Hotel in {travel_request.destination}"),
                    "description": item.get("content", ""),
                    "location": travel_request.destination,
                    "url": item.get("url", ""),
                }
                for item in web_res
            ]
    except Exception as exc:
        print(f"  [HOTEL] Web search fallback failed: {exc}")

    return [
        {
            "name": f"Recommended Accommodation in {travel_request.destination}",
            "location": travel_request.destination,
            "reason": "Live API lookup was unavailable.",
        }
    ]


def run(state: TravelState) -> TravelState:
    travel_request = state.get("travel_request")

    if travel_request is None:
        print("  [HOTEL ERROR] No travel_request in state.")
        return {
            "agent_results": {"hotel": []},
            "errors": [
                {
                    "node": "hotel",
                    "message": "No structured travel request available.",
                    "retry_count": 0,
                }
            ],
        }

    try:
        from tools.maps import geocode
        from tools.hotels import search_hotels

        print(f"  [HOTEL] Geocoding destination: '{travel_request.destination}'...")
        location = geocode(travel_request.destination)
        print(f"  [HOTEL] Geocode result: {location}")

        if not location:
            raise ValueError(
                f"Could not geocode destination: {travel_request.destination}"
            )

        latitude = location["lat"]
        longitude = location["lon"]

        print(f"  [HOTEL] Querying hotels at ({latitude:.4f}, {longitude:.4f})...")
        hotel_data = search_hotels(
            latitude=latitude,
            longitude=longitude,
        )
        print(f"  [HOTEL] Total hotels returned: {len(hotel_data or [])}")

        if not hotel_data:
            print("  [HOTEL] No raw hotels found, switching to web search fallback...")
            hotel_data = _fallback_web_search(travel_request)

        print("  [HOTEL] Invoking LLM to select and rank hotels...")
        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(HotelSelection)

        selection: HotelSelection = structured_llm.invoke(
            [
                {"role": "system", "content": _PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Travel request:\n"
                        f"{travel_request.model_dump_json()}\n\n"
                        f"Available hotel data:\n"
                        f"{hotel_data}\n\n"
                        "Select and organize the most relevant hotel "
                        "options according to the user's accommodation "
                        "preference and budget. Do not invent information "
                        "that is not present in the provided hotel data."
                    ),
                },
            ]
        )

        hotels = selection.hotels
        print(f"  [HOTEL] LLM selected {len(hotels)} hotels.")

        if not hotels:
            hotels = hotel_data or _fallback_web_search(travel_request)

        return {
            "agent_results": {
                "hotel": hotels,
            }
        }

    except Exception as exc:
        print(f"  [HOTEL ERROR] Failed with exception: {exc}")
        traceback.print_exc()
        errors = state.get("errors", []) + [
            {
                "node": "hotel",
                "message": str(exc),
                "retry_count": 0,
            }
        ]

        fallback_hotels = _fallback_web_search(travel_request)
        return {
            "agent_results": {
                "hotel": fallback_hotels,
            },
            "errors": errors,
        }