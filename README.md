# Movement receiver

Receive Bluetooth LE data packets from QtPy ESP32‑S3 + BNO055+BMP280 BFF.

## Fault-tolerant auto-reconnect

This app now automatically reconnects if the BLE link drops and resumes listening for UART notifications once the device is available again.

Notes:

- BLE notifications are not buffered while disconnected; data sent during the gap cannot be recovered. On reconnection, the app simply resumes receiving new notifications.
- Reconnects use exponential backoff with jitter to avoid hammering the device or OS stack.

### Configuration

You can configure behavior via environment variables:

- `BLE_ADDRESS` — Preferred target identifier (address/UUID). If set, the app attempts to connect directly to this target first. Default: the built-in macOS UUID from the original script.
- `BLE_NAME` — Optional name substring to find the device via scanning when `BLE_ADDRESS` is not set.
- `BACKOFF_INITIAL` — Initial backoff in seconds (default `1.0`).
- `BACKOFF_MAX` — Maximum backoff in seconds (default `60.0`).
- `BACKOFF_JITTER` — Up to this many seconds of positive jitter added to backoff (default `0.5`).
- `PARSE_TELEMETRY` — When set to `1`/`true`, the monitor parses incoming text into JSON using `parser.py` and prints the resulting object per sample. Default `1` (enabled). Set to `0` to print raw lines.

### Run

Python 3.12+

1. Install dependencies (managed by `pyproject.toml`):

```bash
pip install -U bleak
```

1. Run the monitor:

```bash
python main.py
```

Optional with config:

```bash
PARSE_TELEMETRY=1 BLE_ADDRESS=<your-device-id> BACKOFF_INITIAL=1 BACKOFF_MAX=30 python main.py
```

On macOS, the BLE identifier often looks like a UUID and is already included by default. On Linux/Windows, use the device MAC address or set `BLE_NAME` for discovery.

### Behavior

- On start, it either uses `BLE_ADDRESS` or scans for devices and picks the first match by `BLE_NAME`.
- Subscribes to the Nordic UART RX characteristic and prints each line of text received.
- If disconnected or an error occurs, it waits with backoff and tries again indefinitely until you press Ctrl+C.
