import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

ADAFRUIT_IO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME")
ADAFRUIT_IO_KEY = os.getenv("ADAFRUIT_IO_KEY")


def push_data(group_key: str, data: dict[str, Any]) -> None:
    """Push a value to the specified Adafruit IO group."""
    url = (
        f"https://io.adafruit.com/api/v2/{ADAFRUIT_IO_USERNAME}/groups/{group_key}/data"
    )

    headers = {
        "X-AIO-Key": ADAFRUIT_IO_KEY,
        "Content-Type": "application/json",
    }

    payload = {"feeds": [{"key": k, "value": str(v)} for k, v in data.items()]}

    response = httpx.post(url, headers=headers, json=payload)
    response.raise_for_status()

    logging.debug(
        f"Pushed {data} to group '{group_key}' (status {response.status_code})"
    )
