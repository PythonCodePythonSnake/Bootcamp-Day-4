"""Places tool — Overpass API queries with active logging, multi-endpoint failover,
and search fallbacks.
"""

import requests

from config import HEADERS

# Primary and fallback Overpass API endpoints
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def _query(overpass_query: str) -> dict:
    """Execute an Overpass QL query with fallback mirrors and detailed logging."""
    last_err = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"  [PLACES API] Querying Overpass endpoint: {endpoint}...")
            response = requests.post(
                endpoint,
                data={"data": overpass_query},
                headers=HEADERS,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            el_count = len(data.get("elements", []))
            print(f"  [PLACES API] Success from {endpoint} ({el_count} raw elements returned)")
            return data
        except Exception as exc:
            print(f"  [PLACES API WARNING] {endpoint} failed: {exc}")
            last_err = exc
            continue

    if last_err:
        print(f"  [PLACES API ERROR] All Overpass endpoints failed. Last error: {last_err}")
        raise last_err
    return {"elements": []}


def _extract_elements(raw: dict, limit: int = 25) -> list[dict]:
    """Normalize Overpass API response into a plain list of place dicts."""
    elements = raw.get("elements", [])
    results: list[dict] = []

    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        if not name:
            continue

        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")

        entry: dict = {
            "name": name,
            "lat": lat,
            "lon": lon,
        }

        if tags.get("addr:full"):
            entry["address"] = tags["addr:full"]
        elif tags.get("addr:street"):
            entry["address"] = tags.get("addr:housenumber", "") + " " + tags["addr:street"]

        for field in ("cuisine", "opening_hours", "website", "phone",
                      "stars", "rating", "tourism", "amenity", "leisure"):
            if tags.get(field):
                entry[field] = tags[field]

        results.append(entry)

        if len(results) >= limit:
            break

    return results


def get_restaurants(latitude: float, longitude: float, radius: int = 2500) -> list[dict]:
    """Return a normalized list of restaurants near the given coordinates."""
    query = f"""
    [out:json][timeout:15];
    (
      node["amenity"="restaurant"](around:{radius},{latitude},{longitude});
    );
    out center 30;
    """
    return _extract_elements(_query(query))


def get_hotels(latitude: float, longitude: float, radius: int = 3500) -> list[dict]:
    """Return a normalized list of hotels near the given coordinates."""
    query = f"""
    [out:json][timeout:15];
    (
      node["tourism"="hotel"](around:{radius},{latitude},{longitude});
    );
    out center 30;
    """
    return _extract_elements(_query(query))


def get_attractions(latitude: float, longitude: float, radius: int = 4000) -> list[dict]:
    """Return a normalized list of tourist attractions near the given coordinates."""
    query = f"""
    [out:json][timeout:15];
    (
      node["tourism"~"attraction|theme_park|viewpoint|gallery"](around:{radius},{latitude},{longitude});
    );
    out center 30;
    """
    return _extract_elements(_query(query))


def get_museums(latitude: float, longitude: float, radius: int = 4000) -> list[dict]:
    """Return a normalized list of museums near the given coordinates."""
    query = f"""
    [out:json][timeout:15];
    (
      node["tourism"="museum"](around:{radius},{latitude},{longitude});
    );
    out center 30;
    """
    return _extract_elements(_query(query))


def get_parks(latitude: float, longitude: float, radius: int = 4000) -> list[dict]:
    """Return a normalized list of parks near the given coordinates."""
    query = f"""
    [out:json][timeout:15];
    (
      node["leisure"="park"](around:{radius},{latitude},{longitude});
    );
    out center 30;
    """
    return _extract_elements(_query(query))