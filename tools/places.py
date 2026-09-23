import requests

from config import OVERPASS_URL


def _query(overpass_query: str):
    response = requests.post(
        OVERPASS_URL,
        data=overpass_query,
        timeout=60,
    )

    response.raise_for_status()

    return response.json()


def get_restaurants(lat, lon, radius=3000):
    query = f"""
    [out:json];
    (
      node["amenity"="restaurant"](around:{radius},{lat},{lon});
      way["amenity"="restaurant"](around:{radius},{lat},{lon});
    );
    out center;
    """
    return _query(query)


def get_hotels(lat, lon, radius=5000):
    query = f"""
    [out:json];
    (
      node["tourism"="hotel"](around:{radius},{lat},{lon});
      way["tourism"="hotel"](around:{radius},{lat},{lon});
    );
    out center;
    """
    return _query(query)


def get_attractions(lat, lon, radius=5000):
    query = f"""
    [out:json];
    (
      node["tourism"](around:{radius},{lat},{lon});
      way["tourism"](around:{radius},{lat},{lon});
    );
    out center;
    """
    return _query(query)


def get_museums(lat, lon, radius=5000):
    query = f"""
    [out:json];
    (
      node["tourism"="museum"](around:{radius},{lat},{lon});
      way["tourism"="museum"](around:{radius},{lat},{lon});
    );
    out center;
    """
    return _query(query)


def get_parks(lat, lon, radius=5000):
    query = f"""
    [out:json];
    (
      node["leisure"="park"](around:{radius},{lat},{lon});
      way["leisure"="park"](around:{radius},{lat},{lon});
    );
    out center;
    """
    return _query(query)