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
SEND_FREQ_HZ = 30

# Power saving measures
microcontroller.cpu.frequency = 120_000_000
bno055.mode = adafruit_bno055.ACCONLY_MODE
bno055.accel_bandwidth = adafruit_bno055.ACCEL_31_25HZ

# BLE Advertising
advertisement = ProvideServicesAdvertisement(uart)
print("Ready to connect!")

# Main loop
while True:
    # Advertise until connected
    if not ble.connected:
        if not ble.advertising:
            try:
                ble.start_advertising(advertisement)
            except Exception as e:
                print(f"Failed to start advertising: {e}")
                gc.collect()
        time.sleep(0.5)
        continue

    print("Connected!")
    ble.stop_advertising()

    # Read sensors
    acc = bno055.acceleration or (0, 0, 0)
    x, y, z = (acc[0] or 0, acc[1] or 0, acc[2] or 0)
    uart.write(f"{x:.2f},{y:.2f},{z:.2f}\n".encode("utf-8"))

    # Sleep sequence
    time.sleep(1.0 / SEND_FREQ_HZ)
