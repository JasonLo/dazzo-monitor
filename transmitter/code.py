import time
import board
import adafruit_bno055
import adafruit_bmp280
import analogio
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

# --- I2C Setup ---
i2c = board.I2C()
bno055 = adafruit_bno055.BNO055_I2C(i2c)
bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(i2c)
bmp280.sea_level_pressure = 1013.25

# Battery
vbat = analogio.AnalogIn(board.A0)

# --- BLE Setup ---
ble = BLERadio()
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

print("Starting BLE advertisement...")
ble.start_advertising(advertisement)

# --- Main Loop ---
while True:
    if ble.connected:
        # Collect sensor data
        voltage = (vbat.value * 3.3 / 65535) * 2
        data = (
            f"Temperature: {bmp280.temperature:0.1f} C\n"
            f"Pressure: {bmp280.pressure:0.1f} hPa\n"
            f"Altitude: {bmp280.altitude:0.2f} m\n"
            f"Accel: {bno055.acceleration}\n"
            f"Mag: {bno055.magnetic}\n"
            f"Gyro: {bno055.gyro}\n"
            f"Euler: {bno055.euler}\n"
            f"Quat: {bno055.quaternion}\n"
            f"Lin Accel: {bno055.linear_acceleration}\n"
            f"Gravity: {bno055.gravity}\n\n"
            f"Battery: {voltage:0.2f} V\n]n"
        )

        print(data)          # still print locally
        uart.write(data)     # send over BLE UART
        time.sleep(1)

    else:
        if not ble.advertising:
            ble.start_advertising(advertisement)
        time.sleep(1)
