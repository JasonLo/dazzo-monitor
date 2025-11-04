import gc
import time

import adafruit_bno055
import board
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

# Hardware setup
ble = BLERadio()
uart = UARTService()
i2c = board.I2C()
bno055 = adafruit_bno055.BNO055_I2C(i2c)

# Configuration
SEND_FREQ_HZ = 30

# Power saving measures
bno055.mode = adafruit_bno055.ACCONLY_MODE
bno055.accel_bandwidth = adafruit_bno055.ACCEL_31_25HZ

# BLE Advertising
advertisement = ProvideServicesAdvertisement(uart)

# Main loop
while True:
    # Advertise until connected
    if not ble.connected:
        if not ble.advertising:
            try:
                print("Start advertising...")
                ble.start_advertising(advertisement)
            except Exception as e:
                print(f"Failed to start advertising: {e}")
                gc.collect()
        time.sleep(3)
        continue

    # Read sensors
    try:
        uart.write(
            f"{bno055.acceleration[0]},{bno055.acceleration[1]},{bno055.acceleration[2]}\n".encode(
                "utf-8"
            )
        )
    except Exception as e:
        print(f"Sensor read/send error: {e}")

    # Sleep sequence
    time.sleep(1.0 / SEND_FREQ_HZ)
