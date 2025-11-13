#include <esp_now.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>
#include <WiFi.h>

// Load sensor name from secrets.h if present
#if defined(__has_include)
#  if __has_include("secrets.h")
#    include "secrets.h"
#  else
#    define SENSOR_NAME            "feather-receiver"
#  endif
#else
#  include "secrets.h"
#endif

// Initialize the TFT display
Adafruit_ST7789 tft = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_RST);

// Structure for incoming sensor data
struct SensorData {
  float x;
  float y;
  float z;
};

// Global variable to hold the latest data
SensorData latestData;

// Volatile flag to indicate new data is ready (for display updates)
volatile bool newDataAvailable = false;


// --- ESP-NOW Receive Callback ---
// Kept fast: just copies data and sets a flag.
void onReceive(const esp_now_recv_info_t *info, const uint8_t *incomingData, int len) {
  if (len != sizeof(SensorData)) {
    return;
  }
  memcpy(&latestData, incomingData, sizeof(latestData));
  // Update display in loop to keep callback fast
  newDataAvailable = true;

  // Send data to USB Serial in JSON format for Python script to parse
  Serial.printf("{\"x\":%.2f,\"y\":%.2f,\"z\":%.2f}\n", 
                latestData.x, latestData.y, latestData.z);
}

// --- Display Update Function ---
void updateDisplay() {
  // Set cursor to the top-left
  tft.setCursor(0, 0);

  // Print formatted data. The padding (%7.2f)
  // automatically overwrites old values.
  tft.printf("X: %7.2f\nY: %7.2f\nZ: %7.2f",
             latestData.x,
             latestData.y,
             latestData.z);
}

// --- Setup ---
void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("ESP-NOW Receiver (USB Serial Mode)");

  // Initialize backlight
  pinMode(TFT_BACKLITE, OUTPUT);
  digitalWrite(TFT_BACKLITE, HIGH);

  // Initialize TFT
  tft.init(135, 240); // Init ST7789 240x135
  tft.setRotation(1);
  
  // Set display properties
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextSize(3);
  tft.setTextColor(ST77XX_WHITE, ST77XX_BLACK);
  
  Serial.println("Waiting for data...");

  // Initialize Wi-Fi in station mode (required for ESP-NOW)
  WiFi.mode(WIFI_STA);

  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed!");
    tft.fillScreen(ST77XX_RED);
    tft.setCursor(0, 0);
    tft.println("ESP-NOW FAILED!");
    while (true) delay(10); // Halt
  }

  // Register receive callback
  esp_now_register_recv_cb(onReceive);

  Serial.println("Receiver ready - data will be sent via USB Serial");
}

// --- Main Loop ---
void loop() {
  // If new data arrived, update the screen.
  if (newDataAvailable) {
    newDataAvailable = false;
    updateDisplay();
  }

  delay(5);
}