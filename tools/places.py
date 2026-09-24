import requests

from config import OVERPASS_URL, HEADERS


def _query(overpass_query: str):
    response = requests.post(
        OVERPASS_URL,
        data={"data": overpass_query},
        headers=HEADERS,
        timeout=60,
    )

    response.raise_for_status()

    return response.json()


def get_restaurants(latitude, longitude, radius=3000):
    query = f"""
    [out:json];
    (
      node["amenity"="restaurant"](around:{radius},{latitude},{longitude});
      way["amenity"="restaurant"](around:{radius},{latitude},{longitude});
    );
    out center;
    """
    return _query(query)


def get_hotels(latitude, longitude, radius=5000):
    query = f"""
    [out:json];
    (
      node["tourism"="hotel"](around:{radius},{latitude},{longitude});
      way["tourism"="hotel"](around:{radius},{latitude},{longitude});
    );
    out center;
    """
    return _query(query)


def get_attractions(latitude, longitude, radius=5000):
    query = f"""
    [out:json];
    (
      node["tourism"](around:{radius},{latitude},{longitude});
      way["tourism"](around:{radius},{latitude},{longitude});
    );
    out center;
    """
    return _query(query)


def get_museums(latitude, longitude, radius=5000):
    query = f"""
    [out:json];
    (
      node["tourism"="museum"](around:{radius},{latitude},{longitude});
      way["tourism"="museum"](around:{radius},{latitude},{longitude});
    );
    out center;
    """
    return _query(query)


def get_parks(latitude, longitude, radius=5000):
    query = f"""
    [out:json];
    (
      node["leisure"="park"](around:{radius},{latitude},{longitude});
      way["leisure"="park"](around:{radius},{latitude},{longitude});
    );
    out center;
    """
    return _query(query)