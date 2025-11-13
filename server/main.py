"""
Serial to InfluxDB bridge for ESP32 receiver.
Reads JSON sensor data from USB serial port and pushes to InfluxDB.
"""

import argparse
import json
import logging
import os
import sys
import time

import serial
import serial.tools.list_ports
from dotenv import load_dotenv

from server.push import push_to_influxdb

load_dotenv()

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "home")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "dazzo")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "")
SENSOR_NAME = os.getenv("SENSOR_NAME", "feather-receiver")


def find_esp32_port() -> str | None:
    """Auto-detect ESP32 device by manufacturer 'Adafruit' or description containing 'ESP32'."""
    ports = serial.tools.list_ports.comports()

    for port in ports:
        manufacturer = (port.manufacturer or "").strip()
        description = (port.description or "").strip()

        if manufacturer == "Adafruit":
            logging.info(f"Found ESP32 device: {port.device} ({description})")
            return port.device

        if "esp32" in description.lower():
            logging.info(
                f"Found ESP32 device by description: {port.device} ({description})"
            )
            return port.device

    return None


def list_serial_ports() -> None:
    """List all available serial ports."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found.")
        return

    print("\nAvailable serial ports:")
    for port in ports:
        print(f"  {port.device}")
        print(f"    Description: {port.description}")
        if port.manufacturer:
            print(f"    Manufacturer: {port.manufacturer}")
        print()


def process_serial_data(
    port: str,
    baudrate: int = 115200,
    sensor_name: str = SENSOR_NAME,
    push_to_influx: bool = True,
) -> None:
    """Read JSON data from serial port and push to InfluxDB."""

    if push_to_influx and not INFLUXDB_TOKEN:
        logging.warning("INFLUXDB_TOKEN not set. InfluxDB push disabled.")
        push_to_influx = False

    ser = None
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        logging.info(f"Connected to {port} at {baudrate} baud")
        logging.info(f"Sensor name: {sensor_name}")
        if push_to_influx:
            logging.info(f"Pushing to InfluxDB: {INFLUXDB_URL}")
        else:
            logging.info("InfluxDB push disabled (monitoring mode)")

        # Discard initial incomplete line
        ser.readline()

        # Track timing for inactivity detection
        last_data_time = time.monotonic()
        idle_zero_posted = False

        while True:
            try:
                line = ser.readline().decode("utf-8", errors="replace").strip()

                # If no data arrived within the serial timeout, consider posting zeros
                if not line:
                    now = time.monotonic()
                    if (now - last_data_time) >= 1.0 and not idle_zero_posted:
                        zero_data = {"x": 0, "y": 0, "z": 0}
                        logging.info(
                            "Inactivity >1s detected; posting zeros: x=0, y=0, z=0"
                        )
                        if push_to_influx:
                            try:
                                push_to_influxdb(
                                    zero_data,
                                    sensor_name=sensor_name,
                                    bucket=INFLUXDB_BUCKET,
                                    org=INFLUXDB_ORG,
                                    token=INFLUXDB_TOKEN,
                                    influxdb_url=INFLUXDB_URL,
                                )
                                logging.debug("Posted zero values to InfluxDB")
                            except Exception as e:
                                logging.error(
                                    f"Failed to push zero values to InfluxDB: {e}"
                                )
                        idle_zero_posted = True
                    continue

                # Skip non-JSON lines (status messages, etc.)
                if not line.startswith("{"):
                    logging.debug(f"Status: {line}")
                    continue

                # Parse JSON data
                try:
                    data = json.loads(line)
                except json.JSONDecodeError as e:
                    logging.warning(f"JSON decode error: {e} in line: {line}")
                    continue

                # Validate expected fields
                if not all(k in data for k in ["x", "y", "z"]):
                    logging.warning(f"Missing x/y/z fields in data: {data}")
                    continue

                logging.info(
                    f"Received: x={data['x']:.2f}, y={data['y']:.2f}, z={data['z']:.2f}"
                )

                # Update inactivity tracking on valid data
                last_data_time = time.monotonic()
                idle_zero_posted = False

                # Push to InfluxDB
                if push_to_influx:
                    try:
                        push_to_influxdb(
                            data,
                            sensor_name=sensor_name,
                            bucket=INFLUXDB_BUCKET,
                            org=INFLUXDB_ORG,
                            token=INFLUXDB_TOKEN,
                            influxdb_url=INFLUXDB_URL,
                        )
                        logging.debug("Pushed to InfluxDB")
                    except Exception as e:
                        logging.error(f"Failed to push to InfluxDB: {e}")

            except UnicodeDecodeError as e:
                logging.warning(f"Unicode decode error: {e}")
                continue
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logging.error(f"Error processing line: {e}")
                continue

    except serial.SerialException as e:
        logging.error(f"Serial port error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("Stopped by user")
    finally:
        if ser is not None and ser.is_open:
            ser.close()
            logging.info("Serial port closed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read sensor data from ESP32 via USB serial and push to InfluxDB"
    )
    parser.add_argument(
        "-p",
        "--port",
        help="Serial port (e.g., /dev/cu.usbserial-0001). If not specified, will try to auto-detect ESP32.",
    )
    parser.add_argument(
        "-b", "--baudrate", type=int, default=115200, help="Baud rate (default: 115200)"
    )
    parser.add_argument(
        "-l", "--list", action="store_true", help="List available serial ports and exit"
    )
    parser.add_argument(
        "-s",
        "--sensor-name",
        default=SENSOR_NAME,
        help=f"Sensor name for InfluxDB tag (default: {SENSOR_NAME})",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Disable InfluxDB push (monitoring mode only)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # List ports if requested
    if args.list:
        list_serial_ports()
        return

    # Auto-detect port if not specified
    port = args.port
    if not port:
        logging.info("No port specified, attempting auto-detection...")
        port = find_esp32_port()
        if not port:
            logging.error("Could not auto-detect ESP32 device.")
            logging.error("Use --list to see available ports, then specify with --port")
            sys.exit(1)

    # Process serial data
    process_serial_data(
        port=port,
        baudrate=args.baudrate,
        sensor_name=args.sensor_name,
        push_to_influx=not args.no_push,
    )


if __name__ == "__main__":
    main()
