from tools.places import get_hotels


def search_hotels(latitude, longitude, radius=5000):
    return get_hotels(
        latitude=latitude,
        longitude=longitude,
        radius=radius,
    )