# Dazzo Monitor

Ultra-lightweight BLE movement tracker for indoor pet monitoring.

![receiver](img/receiver.jpg)

## Transmitter

### Hardware

- [Adafruit QT Py S3](https://www.adafruit.com/product/5700) - WiFi Dev Board
- [Adafruit BNO055 + BMP280 BFF](https://www.adafruit.com/product/5937) - Motion & Pressure Sensor
- [100mAh LiPo Battery](https://www.adafruit.com/product/1570)
- Headers & connectors: [Female](https://www.adafruit.com/product/2940), [Male](https://www.adafruit.com/product/3002), [JST Cable](https://www.adafruit.com/product/3814)

### Setup

1. Install [CircuitPython](https://circuitpython.org/board/adafruit_qtpy_esp32s3_4mbflash_2mbpsram/) on the QT Py
2. Copy [`transmitter/`](transmitter) code to the device
3. (Optional) Update libraries from [circuitpython.org/libraries](https://circuitpython.org/libraries)

## Receiver

Python service that receives BLE telemetry data via Nordic UART. No power or compute limit.

### Usage

**Requirements:** Python 3.12+

```bash
# Install dependencies
uv sync

# Run receiver
cd receiver
uv run main.py
```

### Optional: Self-hosted InfluxDB integration

This project can stream activity summaries to InfluxDB (v2) using the HTTP API. A Docker Compose service is provided for local development.

1. Start InfluxDB locally (optional):

    ```bash
    docker compose up -d influxdb
    ```

2. Configure the following environment variables (for example in a local `.env` file):

    - `INFLUXDB_URL` (default: `http://localhost:8086`)
    - `INFLUXDB_ORG` (default: `home`)
    - `INFLUXDB_BUCKET` (default: `dazzo`)
    - `INFLUXDB_TOKEN` (required for writes)

    When `INFLUXDB_TOKEN` is set, the receiver will automatically push each activity report to InfluxDB.

### Optional: Adafruit IO integration

You can stream activity summaries to [Adafruit IO](https://io.adafruit.com/) for easy cloud dashboards and automations.

1. Create a free Adafruit IO account and generate an **AIO Key**.
2. Create a group called `dazzo` (or use your preferred group name).
3. Add the following environment variables (e.g., in a local `.env` file):
    - `ADAFRUIT_IO_USERNAME` (your Adafruit IO username)
    - `ADAFRUIT_IO_KEY` (your Adafruit IO key)
4. When both variables are set, the receiver will push activity reports to Adafruit IO. Each activity (e.g., `resting`, `active`, etc.) is sent as a feed in the group.
