import os
import requests
from datetime import date

AMADEUS_BASE_URL = "https://test.api.amadeus.com"

AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")


class AmadeusClient:
    def __init__(self):
        self.access_token = None

    def get_access_token(self):
        if self.access_token:
            return self.access_token

        response = requests.post(
            f"{AMADEUS_BASE_URL}/v1/security/oauth2/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "client_credentials",
                "client_id": AMADEUS_CLIENT_ID,
                "client_secret": AMADEUS_CLIENT_SECRET,
            },
            timeout=30,
        )

        response.raise_for_status()

        token_data = response.json()

        self.access_token = token_data["access_token"]

        return self.access_token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.get_access_token()}"
        }


client = AmadeusClient()


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
    max_results: int = 10,
):
    """
    Example:

    search_flights(
        origin="DEL",
        destination="NRT",
        departure_date="2027-01-15"
    )
    """

    response = requests.get(
        f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers",
        headers=client._headers(),
        params={
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
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
    departure_date: str,
    return_date: str,
    adults: int = 1,
):
    response = requests.get(
        f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers",
        headers=client._headers(),
        params={
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "returnDate": return_date,
            "adults": adults,
            "max": 10,
        },
        timeout=60,
    )

    response.raise_for_status()

    return response.json()


def airport_search(keyword: str):
    """
    Example:
    airport_search("Tokyo")
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