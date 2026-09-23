import requests

from config import OSRM_URL


def route(origin_lon, origin_lat, dest_lon, dest_lat):
    url = (
        f"{OSRM_URL}/route/v1/driving/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    )

    response = requests.get(
        url,
        params={
            "overview": "false",
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not data["routes"]:
        return None

    route_data = data["routes"][0]

    return {
        "distance_km": route_data["distance"] / 1000,
        "duration_min": route_data["duration"] / 60,
    }