import time

import adafruit_bno055
import analogio
import board
import wifi
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService


def _coalesce_tuple(t, length):
    """Return a tuple of floats, replacing None/missing with 0.0."""
    # Avoid list concatenation and slicing for efficiency
    if t is None:
        return (0.0,) * length
    result = []
    t_len = len(t)
    for i in range(length):
        if i < t_len:
            v = t[i]
            result.append(0.0 if v is None else float(v))
        else:
            result.append(0.0)
    return tuple(result)


def _fmt(v: float) -> str:
    """Format a number compactly with 2 decimal places."""
    # Avoid try/except for speed; assume sensors return valid floats
    return f"{v:.2f}" if isinstance(v, (float, int)) else "nan"


# Sensor Initialization
wifi.radio.enabled = False
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)
print("Starting BLE advertisement...")
i2c = board.I2C()

bno055 = adafruit_bno055.BNO055_I2C(i2c)
bno055.mode = adafruit_bno055.ACCONLY_MODE
bno055.accel_mode = adafruit_bno055.ACCEL_LOWPOWER1_MODE
bno055.accel_bandwidth = adafruit_bno055.ACCEL_15_63HZ

battery_voltage = analogio.AnalogIn(board.A0)
ble = BLERadio()
ble.start_advertising(advertisement)

while True:
    if ble.connected:
        voltage = (battery_voltage.value * 3.3 / 65535) * 2
        acceleration = _coalesce_tuple(bno055.acceleration, 3)
        sensors = (voltage,) + acceleration
        line = ",".join([_fmt(v) for v in sensors]) + "\n"
        uart.write(line.encode("utf-8"))
        time.sleep(1)
    else:
        if not ble.advertising:
            ble.start_advertising(advertisement)
        time.sleep(1)
