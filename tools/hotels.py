from tools.places import get_hotels


def search_hotels(lat, lon, radius=5000):
    return get_hotels(
        lat=lat,
        lon=lon,
        radius=radius,
    )