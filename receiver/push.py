import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

ADAFRUIT_IO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME")
ADAFRUIT_IO_KEY = os.getenv("ADAFRUIT_IO_KEY")

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "home")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "dazzo")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "")


def push_to_adafruit_io(group_key: str, data: dict[str, Any]) -> None:
    """Push a value to the specified Adafruit IO group."""

    base_url = "https://io.adafruit.com/api/v2/"
    url = f"{base_url}{ADAFRUIT_IO_USERNAME}/groups/{group_key}/data"

    headers = {
        "X-AIO-Key": ADAFRUIT_IO_KEY,
        "Content-Type": "application/json",
    }

    payload = {"feeds": [{"key": k, "value": str(v)} for k, v in data.items()]}
    response = httpx.post(url, headers=headers, json=payload)
    response.raise_for_status()


def to_influx_line_protocol(data: dict[str, Any], sensor_name: str) -> str:
    """Convert data dict to valid InfluxDB line protocol."""
    line_protocol_lines = []
    for key, value in data.items():
        if isinstance(value, str):
            field = f'value="{value}"'
        elif isinstance(value, (int, float)):
            field = f"value={value}"
        else:
            continue  # skip unsupported types
        line = f"{key},sensor={sensor_name} {field}"
        line_protocol_lines.append(line)
    return "\n".join(line_protocol_lines)


def push_to_influxdb(
    data: dict[str, Any],
    sensor_name: str = "dazzo-monitor",
    bucket: str = INFLUXDB_BUCKET,
    org: str = INFLUXDB_ORG,
    token: str = INFLUXDB_TOKEN,
    influxdb_url: str = INFLUXDB_URL,
) -> None:
    """Push data to InfluxDB using the line protocol."""

    url = f"{influxdb_url}/api/v2/write"
    params = {"bucket": bucket, "org": org, "precision": "s"}
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "text/plain; charset=utf-8",
    }
    content = to_influx_line_protocol(data, sensor_name)
    response = httpx.post(url, params=params, headers=headers, content=content)
    response.raise_for_status()
