# Dazzo Monitor

Ultra-lightweight (10g) BLE movement tracker for indoor pet monitoring.

![receiver](img/receiver.jpg)

## Transmitter

**Weight:** 10g

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

Python service that receives BLE telemetry data via Nordic UART.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BLE_ADDRESS` | Device address/UUID for direct connection | macOS UUID |
| `BLE_NAME` | Device name substring for scanning | - |
| `PARSE_TELEMETRY` | Parse telemetry to JSON (`1`) or raw (`0`) | `1` |
| `BACKOFF_INITIAL` | Initial reconnect delay (seconds) | `1.0` |
| `BACKOFF_MAX` | Maximum reconnect delay (seconds) | `60.0` |
| `BACKOFF_JITTER` | Random jitter added to backoff (seconds) | `0.5` |

### Usage

**Requirements:** Python 3.12+

```bash
# Install dependencies
uv sync

# Run receiver
cd receiver
uv run main.py
```

**How it works:**

- Connects to device via `BLE_ADDRESS` or scans for `BLE_NAME`
- Subscribes to Nordic UART RX characteristic
- Parses and displays telemetry data
- Auto-reconnects on disconnect with exponential backoff
