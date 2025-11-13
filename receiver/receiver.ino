#include <esp_now.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>
#include <WiFi.h>
#include <esp_wifi.h>

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

// Receiver MAC address (printed and shown on TFT)
String macAddress;

// Helper to fetch STA MAC using ESP-IDF (more reliable than WiFi.macAddress())
String getStaMac() {
  uint8_t mac[6] = {0};
  if (esp_wifi_get_mac(WIFI_IF_STA, mac) == ESP_OK) {
    char buf[18];
    snprintf(buf, sizeof(buf), "%02X:%02X:%02X:%02X:%02X:%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    return String(buf);
  }
  return String("00:00:00:00:00:00");
}


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

  // Always show MAC on the first line (smaller text to fit width)
  tft.setTextSize(2);
  tft.printf("MAC Address:\n%s\n\n", macAddress.c_str());

  // Show sensor values on lines 3-5. The padding (%5.2f)
  // automatically overwrites old values.
  tft.setTextSize(3);
  tft.printf("X: %5.2f\nY: %5.2f\nZ: %5.2f",
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

  // Capture and print MAC address for transmitter configuration
  macAddress = getStaMac();
  Serial.print("Receiver MAC Address: ");
  Serial.println(macAddress);

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