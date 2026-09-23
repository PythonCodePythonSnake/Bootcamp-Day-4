import requests

from config import NOMINATIM_URL, HEADERS


def geocode(location: str):
    response = requests.get(
        f"{NOMINATIM_URL}/search",
        params={
            "q": location,
            "format": "jsonv2",
            "limit": 1,
        },
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not data:
        return None

    result = data[0]

    return {
        "name": result["display_name"],
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
    }


def reverse_geocode(lat: float, lon: float):
    response = requests.get(
        f"{NOMINATIM_URL}/reverse",
        params={
            "lat": lat,
            "lon": lon,
            "format": "jsonv2",
        },
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()