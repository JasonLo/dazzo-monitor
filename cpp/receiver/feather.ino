#include <WiFi.h>
#include <esp_now.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>

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

// Volatile flag to indicate new data is ready
volatile bool newDataAvailable = false;


// --- ESP-NOW Receive Callback ---
// Kept fast: just copies data and sets a flag.
void onReceive(const esp_now_recv_info_t *info, const uint8_t *incomingData, int len) {
  if (len != sizeof(SensorData)) {
    return;
  }
  memcpy(&latestData, incomingData, sizeof(latestData));
  newDataAvailable = true;
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
  Serial.println("ESP-NOW Receiver (Simple)");

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
  
  // We only print status to Serial, not the TFT.
  // The screen will remain black until data arrives.
  Serial.println("Waiting for data...");

  // Initialize Wi-Fi
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

  Serial.println("Receiver ready");
}

// --- Main Loop ---
void loop() {
  // Check if new data has arrived
  if (newDataAvailable) {
    newDataAvailable = false; // Reset the flag
    updateDisplay();      // Update the screen
  }
}