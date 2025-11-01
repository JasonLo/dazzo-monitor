import asyncio
import logging
import os
from typing import Any, Optional

from bleak import BleakClient, BleakScanner

# Nordic UART Service (NUS)
UART_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"


async def find_by_name(target_name: str) -> Optional[str]:
    """Scan for 5s and return the address of the first device matching name.

    Matching rule: prefer exact name match (case-sensitive),
    otherwise fall back to substring match (case-insensitive).
    """
    logging.info(f"Scanning for BLE devices (5s)... looking for '{target_name}'")
    devices = await BleakScanner.discover(timeout=5.0)
    if not devices:
        logging.warning("No BLE devices found.")
        return None

    # Try exact match first
    for d in devices:
        if (d.name or "") == target_name:
            logging.info(f"Found exact match: {d.name} [{d.address}]")
            return d.address

    # Fallback: substring case-insensitive
    t = target_name.lower()
    for d in devices:
        if t in (d.name or "").lower():
            logging.info(f"Found partial match: {d.name} [{d.address}]")
            return d.address

    logging.info(f"No device matched name '{target_name}'.")
    return None


async def main() -> None:
    target_name = os.getenv("QT_PY_BLUETOOTH_NAME", "CIRCUITPY")
    addr = await find_by_name(target_name)
    if not addr:
        logging.error("Aborting.")
        return

    disconnected: asyncio.Event = asyncio.Event()

    def on_disconnect(_: BleakClient) -> None:
        logging.info("Disconnected.")
        disconnected.set()

    # Buffer to reassemble newline-terminated messages across BLE fragments
    rx_buffer = bytearray()

    def handle_received_bytes(_: Any, data: bytearray) -> None:  # type: ignore[override]
        nonlocal rx_buffer
        rx_buffer.extend(data)
        # Process all complete lines found in buffer
        while True:
            try:
                idx = rx_buffer.index(0x0A)  # '\n'
            except ValueError:
                break
            line = bytes(rx_buffer[:idx])
            # remove the processed line + delimiter
            del rx_buffer[: idx + 1]
            try:
                logging.info(line.decode("utf-8", errors="replace"))
            except Exception:
                logging.error(repr(line))

    logging.info(f"Connecting to {addr} ...")
    try:
        async with BleakClient(addr, disconnected_callback=on_disconnect) as client:
            logging.info("Connected. Subscribing to notifications...")
            await client.start_notify(UART_RX_CHAR_UUID, handle_received_bytes)
            logging.info("Receiving data. Press Ctrl+C to stop.")
            await disconnected.wait()
    except Exception as e:
        logging.error(f"Connection error: {e}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()],
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
