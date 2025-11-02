import asyncio
import logging
import os
import time
from collections import deque

import numpy as np
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from dotenv import load_dotenv

from .classifier import ActivityClassifier, SensorMode
from .push import push_data

load_dotenv()

# Configuration
TRANSMITTER_NAME = os.getenv("TRANSMITTER_NAME", "CIRCUITPY")
SENSOR_MODE = SensorMode.NDOF
MAX_BACKOFF_SECS = float(os.getenv("MAX_BACKOFF_SECS", "30"))
REPORT_PERIOD_SECS = float(os.getenv("REPORT_PERIOD_SECS", "5"))
UART_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"


class DataProcessor:
    """Handles parsing incoming data, buffering samples, and periodic activity classification."""

    def __init__(
        self,
        classifier: ActivityClassifier,
        report_period_s: float = REPORT_PERIOD_SECS,
        push_to_io: bool = False,
    ) -> None:
        if report_period_s <= 0:
            raise ValueError("report_period_s must be positive")
        self.classifier = classifier
        self.report_period_s = report_period_s
        self.push_to_io = push_to_io

        self.samples = deque(maxlen=1000)  # Data buffer
        self.last_report_time = time.time()

    def __repr__(self) -> str:
        return f"DataProcessor(report_period_s={self.report_period_s}, samples_count={len(self.samples)})"

    def process(self, line: str) -> None:
        """Parse a line of data and add to samples buffer."""
        try:
            parts = line.strip().split(",")
            if len(parts) == 3:
                x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                self.samples.append((x, y, z))
            else:
                logging.warning(f"Unexpected data format: {line.strip()}")
        except ValueError as e:
            logging.error(f"Failed to parse line '{line.strip()}': {e}")

    def report_activity(self) -> None:
        """Classify activity from buffered samples and log the result."""
        if not self.samples:
            logging.info("No samples available for classification")
            return

        # Convert samples to numpy array
        data = np.array(list(self.samples))
        activity = self.classifier.classify(data)
        logging.info(f"Activity classification: {activity}")
        if self.push_to_io:
            try:
                push_data("dazzo", activity)
            except Exception as e:
                logging.error(f"Failed to push activity to Adafruit IO: {e}")
        # Clear samples after classification
        self.samples.clear()

    async def periodic_report(self) -> None:
        """Run periodic activity reporting."""
        while True:
            await asyncio.sleep(self.report_period_s)
            self.report_activity()


class BLEManager:
    """Manages BLE device discovery, connection, and data streaming with automatic reconnection."""

    def __init__(
        self,
        transmitter_name: str = TRANSMITTER_NAME,
        max_backoff: float = MAX_BACKOFF_SECS,
    ):
        if not transmitter_name.strip():
            raise ValueError("transmitter_name cannot be empty")
        if max_backoff <= 0:
            raise ValueError("max_backoff must be positive")

        self.transmitter_name = transmitter_name
        self.max_backoff = max_backoff

        self.rx_buffer = bytearray()
        self.last_addr: str | None = None

    def __repr__(self) -> str:
        return f"BLEManager(transmitter_name='{self.transmitter_name}', max_backoff={self.max_backoff})"

    async def scan_for_device(self) -> str | None:
        """Scan for 5s and return the address of the first device matching name.

        Matching rule: prefer exact name match (case-sensitive),
        otherwise fall back to substring match (case-insensitive).
        """
        logging.info(
            f"Scanning for BLE devices (5s)... looking for '{self.transmitter_name}'"
        )
        devices = await BleakScanner.discover(timeout=5.0)
        if not devices:
            logging.warning("No BLE devices found.")
            return None

        # Try exact match first
        for d in devices:
            if (d.name or "") == self.transmitter_name:
                logging.info(f"Found exact match: {d.name} [{d.address}]")
                return d.address

        # Fallback: substring case-insensitive
        t = self.transmitter_name.lower()
        for d in devices:
            if t in (d.name or "").lower():
                logging.info(f"Found partial match: {d.name} [{d.address}]")
                return d.address

        logging.info(f"No device matched name '{self.transmitter_name}'.")
        return None

    async def connect_and_stream(self, addr: str, processor: DataProcessor) -> None:
        """Connect to the given address, accumulate bytes, and process complete newline-terminated lines."""
        disconnected: asyncio.Event = asyncio.Event()

        def on_disconnect(_: BleakClient) -> None:
            logging.info("Disconnected.")
            disconnected.set()

        def handle_received_bytes(
            _: BleakGATTCharacteristic | int | str, data: bytearray
        ) -> None:
            self.rx_buffer.extend(data)

            while True:
                newline_index = self.rx_buffer.find(b"\n")
                if newline_index == -1:
                    break

                line_bytes = self.rx_buffer[:newline_index]
                del self.rx_buffer[: newline_index + 1]

                line_str = line_bytes.rstrip(b"\r").decode("utf-8", errors="replace")
                if not line_str:
                    continue

                try:
                    processor.process(line_str)
                except Exception:
                    logging.error(f"Failed to process line: {repr(line_str)}")

        logging.info(f"Connecting to {addr} ...")
        async with BleakClient(addr, disconnected_callback=on_disconnect) as client:
            logging.info("Connected. Subscribing to notifications...")
            await client.start_notify(UART_RX_CHAR_UUID, handle_received_bytes)
            logging.info("Receiving data. Press Ctrl+C to stop.")
            await disconnected.wait()

    async def run(self, processor: DataProcessor) -> None:
        """Run the main connection loop with automatic reconnection."""
        backoff: float = 1.0

        while True:
            addr: str | None = self.last_addr
            if not addr:
                addr = await self.scan_for_device()
                if not addr:
                    logging.warning(
                        f"No device matched '{self.transmitter_name}'. Retrying in {backoff:.0f}s..."
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, self.max_backoff)
                    continue

            try:
                await self.connect_and_stream(addr, processor)
                self.last_addr = addr
                backoff = 1.0
                await asyncio.sleep(1.0)
                logging.info("Attempting to resume connection...")
            except Exception as e:
                logging.error(f"Connection error: {e}")
                self.last_addr = None
                logging.info(f"Retrying in {backoff:.0f}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.max_backoff)


async def run_receiver(sensor_mode: SensorMode, push_to_io: bool) -> None:
    """Main receiver loop: connect, receive data, classify activity, and handle re-connections."""

    classifier = ActivityClassifier(sensor_mode=sensor_mode)
    processor = DataProcessor(classifier=classifier, push_to_io=push_to_io)
    ble_manager = BLEManager(transmitter_name=TRANSMITTER_NAME)

    report_task = asyncio.create_task(processor.periodic_report())

    try:
        await ble_manager.run(processor)
    finally:
        report_task.cancel()
        try:
            await report_task
        except asyncio.CancelledError:
            pass


async def main() -> None:
    await run_receiver(sensor_mode=SENSOR_MODE, push_to_io=True)


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
