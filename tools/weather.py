import requests

from config import OPEN_METEO_URL


def get_weather(lat, lon):
    response = requests.get(
        f"{OPEN_METEO_URL}/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code",
            "timezone": "auto",
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def get_forecast(lat, lon):
    response = requests.get(
        f"{OPEN_METEO_URL}/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": (
                "temperature_2m_max,"
                "temperature_2m_min,"
                "precipitation_sum"
            ),
            "forecast_days": 7,
            "timezone": "auto",
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()