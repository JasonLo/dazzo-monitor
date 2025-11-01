import asyncio
import json
import logging
import os
import random
import signal
from typing import Optional

from bleak import BleakClient, BleakScanner

try:
    from . import parser as telemetry_parser  # if used as a package
except Exception:
    import parser as telemetry_parser  # local module fallback

# Default Nordic UART Service (NUS)
UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

# macOS-style BLE identifier for the target device (can be overridden via env var)
QTPY_ADDRESS = os.getenv(
    "BLE_ADDRESS",
    "2265B3DA-BA40-1315-A82B-37EFFCB0606E",
)

# Optional: discover by name substring if address isn't known
BLE_NAME = os.getenv("BLE_NAME", "")

# Backoff settings (can be tuned via env)
BACKOFF_INITIAL = float(os.getenv("BACKOFF_INITIAL", "1.0"))
BACKOFF_MAX = float(os.getenv("BACKOFF_MAX", "60.0"))
BACKOFF_JITTER = float(os.getenv("BACKOFF_JITTER", "0.5"))


def _jittered_sleep(backoff: float) -> float:
    """Return a sleep duration with small positive jitter."""
    return backoff + random.uniform(0, BACKOFF_JITTER)


def _print_cfg():
    print("=== Dazzo Monitor ===")
    if QTPY_ADDRESS:
        print(f"Target address: {QTPY_ADDRESS}")
    if BLE_NAME:
        print(f"Target name filter: '{BLE_NAME}'")
    print(
        f"Backoff: initial={BACKOFF_INITIAL}s max={BACKOFF_MAX}s jitter<= {BACKOFF_JITTER}s"
    )
    print("Press Ctrl+C to exit.")


async def _find_target() -> Optional[str]:
    """
    Find the device address to connect to.
    Priority:
    1) Explicit BLE_ADDRESS env (QTPY_ADDRESS)
    2) Scan and match by BLE_NAME substring
    """
    # If address provided explicitly, try that first
    if QTPY_ADDRESS:
        return QTPY_ADDRESS

    # Otherwise, try to discover by name
    print("Scanning for BLE devices...")
    devices = await BleakScanner.discover(timeout=5.0)
    for d in devices:
        name = (d.name or "").lower()
        if BLE_NAME and BLE_NAME.lower() in name:
            print(f"Found target by name: {d.name} [{d.address}]")
            return d.address

    print("No matching device found during scan.")
    return None


def _make_rx_handler():
    parse_mode = os.getenv("PARSE_TELEMETRY", "1").lower() in {"1", "true", "yes"}
    buffer = ""

    def handle_rx(_, data: bytearray):
        nonlocal buffer
        chunk = ""
        try:
            chunk = data.decode("utf-8", errors="replace")
        except Exception:
            chunk = repr(bytes(data))

        if not parse_mode:
            print(chunk.strip())
            return

        # Streaming parse: accumulate until we likely have a full block
        buffer += chunk

        # Heuristic: attempt parse when we see 'Battery:' marker which is last field
        if "Battery:" not in buffer:
            return

        # Try to extract and parse; if it fails, keep buffer (it may be incomplete)
        try:
            result = telemetry_parser.parse_telemetry(buffer)
        except Exception:
            # Keep collecting
            return

        if result:
            logging.info(json.dumps(result, separators=(",", ":")))
            buffer = ""  # reset after a successful parse

    return handle_rx


async def run_monitor(shutdown: asyncio.Event):
    _print_cfg()

    backoff = BACKOFF_INITIAL
    rx_handler = _make_rx_handler()

    while not shutdown.is_set():
        addr = await _find_target()
        if addr is None:
            # Couldn't find device this round; back off and retry
            sleep_for = _jittered_sleep(backoff)
            print(f"Retrying discovery in {sleep_for:.1f}s...")
            await asyncio.sleep(sleep_for)
            backoff = min(backoff * 2, BACKOFF_MAX)
            continue

        disconnected_evt = asyncio.Event()

        def _on_disconnect(_client):
            print("BLE disconnected.")
            # Ensure we can set the event from bleak's callback thread
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(disconnected_evt.set)

        try:
            print(f"Connecting to {addr} ...")
            async with BleakClient(
                addr, disconnected_callback=_on_disconnect
            ) as client:
                print("Connected. Subscribing to notifications...")
                await client.start_notify(UART_RX_CHAR_UUID, rx_handler)

                # Reset backoff after a successful connection
                backoff = BACKOFF_INITIAL
                print("Receiving data (auto-reconnect enabled)...")

                # Wait for either disconnection or shutdown
                disco_task = asyncio.create_task(disconnected_evt.wait())
                shut_task = asyncio.create_task(shutdown.wait())
                try:
                    await asyncio.wait(
                        {disco_task, shut_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                finally:
                    # Cancel whichever task is still pending to avoid warnings
                    for t in (disco_task, shut_task):
                        if not t.done():
                            t.cancel()
                            try:
                                await t
                            except asyncio.CancelledError:
                                pass

                # If shutdown fired, stop cleanly
                if shutdown.is_set():
                    print(
                        "Shutdown requested. Stopping notifications and disconnecting..."
                    )
                    try:
                        await client.stop_notify(UART_RX_CHAR_UUID)
                    except Exception:
                        pass
                    break

        except Exception as e:
            print(f"Connection/listen error: {e}")

        # If we're here, either error or disconnection occurred; back off and retry
        sleep_for = _jittered_sleep(backoff)
        print(f"Reconnecting in {sleep_for:.1f}s...")
        await asyncio.sleep(sleep_for)
        backoff = min(backoff * 2, BACKOFF_MAX)


async def _amain():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    shutdown = asyncio.Event()

    # Graceful Ctrl+C handling
    def _handle_sigint():
        shutdown.set()

    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, _handle_sigint)
        loop.add_signal_handler(signal.SIGTERM, _handle_sigint)
    except NotImplementedError:
        # add_signal_handler isn't supported on Windows event loop policy
        pass

    await run_monitor(shutdown)


if __name__ == "__main__":
    asyncio.run(_amain())
