
# Dazzo Monitor

Ultra-lightweight ESP-NOW movement tracker for indoor pet monitoring.

[![CC0 1.0 Universal](https://img.shields.io/badge/License-CC0%201.0-lightgrey.svg)](https://creativecommons.org/publicdomain/zero/1.0/)

This project is dedicated to the public domain under the [CC0 1.0 Universal license](https://creativecommons.org/publicdomain/zero/1.0/). See the LICENSE file for details.

![receiver](img/receiver.jpg)

## System Architecture

The system consists of three components:

1. **Transmitter** - Battery-powered motion sensor (QT Py ESP32-S3)
2. **Receiver** - USB-connected display device (ESP32-S3 Feather Reverse TFT)
3. **Server** - Data processing and storage (Mac with InfluxDB)

Data flows via ESP-NOW from transmitter to receiver, then via USB serial to the server for storage and analysis.

## Transmitter

### Hardware

- [Adafruit QT Py ESP32-S3](https://www.adafruit.com/product/5700) - WiFi Dev Board
- [Adafruit BNO055 + BMP280 BFF](https://www.adafruit.com/product/5937) - Motion & Pressure Sensor
- [100mAh LiPo Battery](https://www.adafruit.com/product/1570)
- Headers & connectors: [Female](https://www.adafruit.com/product/2940), [Male](https://www.adafruit.com/product/3002), [JST Cable](https://www.adafruit.com/product/3814)

### Setup

1. Open [`transmitter/transmitter.ino`](transmitter/transmitter.ino) in Arduino IDE
2. Update the `peerAddress` MAC address to match your receiver
3. Upload to the QT Py ESP32-S3
4. The transmitter will send motion data via ESP-NOW when movement exceeds threshold

## Receiver

### Hardware

- [Adafruit ESP32-S3 Feather Reverse TFT](https://www.adafruit.com/product/5691) - ESP32 with built-in display

### Setup

1. Open [`receiver/receiver.ino`](receiver/receiver.ino) in Arduino IDE
2. Upload to the ESP32-S3 Feather
3. Open Serial Monitor (115200 baud) - the MAC address prints at startup and stays on the TFT first line
4. Note the receiver MAC (e.g. `B8:F8:62:D5:D1:D0`) for transmitter config
5. Connect via USB to your Mac running the server
6. The receiver displays motion data on the TFT and streams JSON via USB serial

## Server

Python service that reads sensor data from the receiver via USB serial and pushes to InfluxDB for storage and visualization.

### Usage

Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Run server

```bash
# Run server (auto-detects ESP32 receiver)
uv run server/main.py
```

### InfluxDB Integration

The server requires InfluxDB for data storage. A Docker Compose service is provided for local deployment.

1. Start InfluxDB:

    ```bash
    docker compose up -d influxdb
    ```

2. Configure environment variables (e.g., in a local `.env` file):

    - `INFLUXDB_TOKEN` (required for writes)
    - `INFLUXDB_URL` (default: `http://localhost:8086`)
    - `INFLUXDB_ORG` (default: `home`)
    - `INFLUXDB_BUCKET` (default: `dazzo`)

3. The server will automatically push sensor data to InfluxDB when `INFLUXDB_TOKEN` is set
