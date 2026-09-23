import requests

from config import EXCHANGE_URL


def convert_currency(
    amount,
    from_currency,
    to_currency,
):
    response = requests.get(
        f"{EXCHANGE_URL}/convert",
        params={
            "from": from_currency,
            "to": to_currency,
            "amount": amount,
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()