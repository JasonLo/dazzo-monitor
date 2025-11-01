import asyncio
import logging
import os

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from dotenv import load_dotenv

load_dotenv()
# Nordic UART Service (NUS)
UART_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"


async def find_by_name(target_name: str) -> str | None:
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


async def _connect_and_stream(addr: str, rx_buffer: bytearray) -> None:
    """Connect to the given address, stream notifications until disconnected.

    Returns when the device disconnects or an error occurs.
    """
    disconnected: asyncio.Event = asyncio.Event()

    def on_disconnect(_: BleakClient) -> None:
        logging.info("Disconnected.")
        disconnected.set()

    def handle_received_bytes(
        _: BleakGATTCharacteristic | int, data: bytearray
    ) -> None:
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
    async with BleakClient(addr, disconnected_callback=on_disconnect) as client:
        logging.info("Connected. Subscribing to notifications...")
        await client.start_notify(UART_RX_CHAR_UUID, handle_received_bytes)
        logging.info("Receiving data. Press Ctrl+C to stop.")
        await disconnected.wait()


async def main() -> None:
    load_dotenv()
    target_name: str = os.getenv("QT_PY_BLUETOOTH_NAME", "CIRCUITPY")

    # Keep buffer across reconnects so we don't lose partial lines
    rx_buffer = bytearray()

    # Remember last successful address to speed up subsequent reconnects
    last_addr: str | None = None

    # Exponential backoff for retries (caps at 30s)
    backoff: float = 1.0
    max_backoff: float = float(os.getenv("RESUME_MAX_BACKOFF_SECS", "30"))

    while True:
        addr: str | None = last_addr
        # If we don't have a known address, scan by name
        if not addr:
            addr = await find_by_name(target_name)
            if not addr:
                logging.warning(
                    f"No device matched '{target_name}'. Retrying in {backoff:.0f}s..."
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
                continue

        try:
            await _connect_and_stream(addr, rx_buffer)
            # Successful session ended due to disconnect; remember address and reset backoff
            last_addr = addr
            backoff = 1.0
            # Small pause before attempting to reconnect to avoid thrashing
            await asyncio.sleep(1.0)
            logging.info("Attempting to resume connection...")
        except Exception as e:
            logging.error(f"Connection error: {e}")
            # Force a rescan next iteration
            last_addr = None
            logging.info(f"Retrying in {backoff:.0f}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


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
