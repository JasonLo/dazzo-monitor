import gc
import time

import adafruit_bno055
import board
import microcontroller
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

# Hardware setup
ble = BLERadio()
uart = UARTService()
i2c = board.I2C()
bno055 = adafruit_bno055.BNO055_I2C(i2c)

# Configuration
MIN_TRANSMISSION_THRESHOLD = 0.2
ACTIVE_SLEEP_DURATION_SECS = 1.0
PASSIVE_SLEEP_DURATION_SECS = 5.0

# Power saving measures
microcontroller.cpu.frequency = 120_000_000
# bno055.mode = adafruit_bno055.ACCONLY_MODE
# bno055.accel_mode = adafruit_bno055.ACCEL_LOWPOWER1_MODE
# bno055.accel_bandwidth = adafruit_bno055.ACCEL_15_63HZ

# BLE Advertising
advertisement = ProvideServicesAdvertisement(uart)
print("Ready to connect!")

# Main loop
while True:
    # Advertise until connected
    if not ble.connected:
        if not ble.advertising:
            gc.collect()  # Clean up memory, works around some memory leak issues
            ble.start_advertising(advertisement)
        time.sleep(0.5)
        continue

    print("Connected!")
    ble.stop_advertising()

    # Read sensors
    acc = bno055.linear_acceleration or (0, 0, 0)
    x, y, z = (acc[0] or 0, acc[1] or 0, acc[2] or 0)
    uart.write(f"{x:.2f},{y:.2f},{z:.2f}\n".encode("utf-8"))
    time.sleep(1.0)
