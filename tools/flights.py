"""Flights tool — Amadeus flight search API.

Key points:
- AmadeusClient.get_access_token() is called lazily on the first API request.
- _resolve_iata() converts city/country names to IATA airport codes before
  calling the flight-offers endpoint, which requires IATA codes.
- departure_date / return_date are explicitly converted to strings to avoid
  passing datetime.date objects to the requests params dict.
"""

import os

import requests

AMADEUS_BASE_URL = "https://test.api.amadeus.com"

AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")


class AmadeusClient:
    def __init__(self):
        self.access_token = None

    def get_access_token(self) -> str:
        if self.access_token:
            return self.access_token

        if not AMADEUS_CLIENT_ID or not AMADEUS_CLIENT_SECRET:
            raise RuntimeError(
                "AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET must be set "
                "in the environment to use the flights tool."
            )

        response = requests.post(
            f"{AMADEUS_BASE_URL}/v1/security/oauth2/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": AMADEUS_CLIENT_ID,
                "client_secret": AMADEUS_CLIENT_SECRET,
            },
            timeout=30,
        )

        response.raise_for_status()

        self.access_token = response.json()["access_token"]
        return self.access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.get_access_token()}"}


client = AmadeusClient()


# ---------------------------------------------------------------------------
# IATA code resolution
# ---------------------------------------------------------------------------

def airport_search(keyword: str) -> dict:
    """Search for airports matching a keyword (city name, country, etc.).

    Example:
        airport_search("Tokyo")   -> data[0]["iataCode"] == "TYO" / "NRT" / "HND"
        airport_search("Delhi")   -> data[0]["iataCode"] == "DEL"
    """
    response = requests.get(
        f"{AMADEUS_BASE_URL}/v1/reference-data/locations",
        headers=client._headers(),
        params={
            "subType": "AIRPORT",
            "keyword": keyword,
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def _resolve_iata(city: str) -> str:
    """Resolve a city/place name to its primary IATA airport code.

    Falls back to the original string if the lookup fails (the Amadeus
    endpoint may still accept it, or the error will be caught by the caller).
    """
    try:
        data = airport_search(city)
        locations = data.get("data", [])
        if locations:
            return locations[0]["iataCode"]
    except Exception:
        pass  # fall through to return the original name

    return city


# ---------------------------------------------------------------------------
# Flight search
# ---------------------------------------------------------------------------

def search_flights(
    origin: str,
    destination: str,
    departure_date,          # datetime.date or "YYYY-MM-DD" string
    adults: int = 1,
    max_results: int = 10,
) -> dict:
    """Search for one-way flight offers between two cities/airports.

    ``origin`` and ``destination`` may be city names or IATA codes.  City
    names are automatically resolved to IATA codes via airport_search().

    Example:
        search_flights("Delhi", "Tokyo", "2027-01-15")
        search_flights("DEL", "NRT", date(2027, 1, 15))
    """
    origin_code = _resolve_iata(origin)
    dest_code = _resolve_iata(destination)

    response = requests.get(
        f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers",
        headers=client._headers(),
        params={
            "originLocationCode": origin_code,
            "destinationLocationCode": dest_code,
            "departureDate": str(departure_date),   # ensure YYYY-MM-DD string
            "adults": adults,
            "max": max_results,
        },
        timeout=60,
    )

    response.raise_for_status()

    return response.json()


def search_round_trip(
    origin: str,
    destination: str,
    departure_date,          # datetime.date or "YYYY-MM-DD" string
    return_date,             # datetime.date or "YYYY-MM-DD" string
    adults: int = 1,
) -> dict:
    """Search for round-trip flight offers between two cities/airports."""
    origin_code = _resolve_iata(origin)
    dest_code = _resolve_iata(destination)

    response = requests.get(
        f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers",
        headers=client._headers(),
        params={
            "originLocationCode": origin_code,
            "destinationLocationCode": dest_code,
            "departureDate": str(departure_date),
            "returnDate": str(return_date),
            "adults": adults,
            "max": 10,
        },
        timeout=60,
    )

    response.raise_for_status()

    return response.json()