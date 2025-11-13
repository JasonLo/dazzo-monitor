#include <WiFi.h>
#include <esp_now.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>
#include <HTTPClient.h>

// Load credentials and server settings from secrets.h if present
#if defined(__has_include)
#  if __has_include("secrets.h")
#    include "secrets.h"
#  else
#    define WIFI_SSID              ""
#    define WIFI_PASSWORD          ""
#    define INFLUXDB_BASE_URL      ""
#    define INFLUXDB_ORG           "home"
#    define INFLUXDB_BUCKET        "dazzo"
#    define INFLUXDB_TOKEN         ""
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

// Prevent overlapping pushes if packets arrive rapidly
static volatile bool influxPushInProgress = false;

// Influx batching and HTTP reuse state
static String g_influxURL;                 // Full write URL
static HTTPClient g_http;                  // Reused HTTP client (keep-alive)
static WiFiClient g_client;                // Plain HTTP client

// Buffering for batched writes
static String influxBuffer;                // Accumulated line protocol
static int influxLineCount = 0;            // Number of lines in buffer
static uint32_t lastInfluxFlushMs = 0;     // Last flush time
static const uint32_t INFLUX_FLUSH_INTERVAL_MS = 1000; // Flush at least every 1s
static const int INFLUX_MAX_LINES = 10;                 // Or when N lines queued
static const size_t INFLUX_MAX_BUFFER = 1024;           // Or when size exceeds

// Rate-limit WiFi maintenance attempts to avoid long blocking in loop
static uint32_t lastWiFiCheckMillis = 0;
static const uint32_t WIFI_CHECK_PERIOD_MS = 5000; // every 5s

// --- Helpers: WiFi connection ---
static void ensureWiFiConnected() {
  if (!WIFI_SSID || !*WIFI_SSID) {
    return; // Disabled
  }
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }
  Serial.printf("Connecting to WiFi SSID '%s'...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("WiFi connected. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("WiFi connect timeout.");
  }
}

// --- Helper: Create Influx Line Protocol from latest sample ---
static String toInfluxLineProtocol(const SensorData& d, const char* sensorName) {
  // Matches Python approach: each axis as measurement name with sensor tag and value field
  // Example:
  // x,sensor=feather-receiver value=0.123456
  // y,sensor=feather-receiver value=...
  // z,sensor=feather-receiver value=...
  String lp;
  lp.reserve(128);

  auto appendLine = [&](const char* key, float v) {
    lp += key;
    lp += ",sensor=";
    lp += sensorName;
    lp += " value=";
    // Use 6 decimal places for floats to balance precision/size
    lp += String(v, 6);
    lp += '\n';
  };

  appendLine("x", d.x);
  appendLine("y", d.y);
  appendLine("z", d.z);

  return lp;
}

// Append a sample to the buffer quickly (cheap operation)
static inline void influxEnqueue(const SensorData& d) {
  if (!INFLUXDB_BASE_URL || !*INFLUXDB_BASE_URL || !INFLUXDB_TOKEN || !*INFLUXDB_TOKEN) return;
  // Convert and append one sample worth of lines
  String lp = toInfluxLineProtocol(d, SENSOR_NAME);
  // Ensure buffer has reasonable capacity
  if (influxBuffer.length() + lp.length() > INFLUX_MAX_BUFFER) {
    // Will be flushed soon; drop oldest by flushing now to make room
    // Note: actual flush happens in loop based on timers, to keep callback fast
  } else {
    influxBuffer += lp;
    influxLineCount += 3; // x,y,z lines appended
  }
}

// Flush buffered lines to InfluxDB using a persistent HTTP client
static void influxFlush() {
  if (influxBuffer.isEmpty()) return;
  if (!INFLUXDB_BASE_URL || !*INFLUXDB_BASE_URL || !INFLUXDB_TOKEN || !*INFLUXDB_TOKEN) return;
  if (WiFi.status() != WL_CONNECTED) return;

  // Begin connection (kept-alive across requests via setReuse)
  bool began = false;
  g_client.setTimeout(1000);
  g_http.setConnectTimeout(1000);
  g_http.setTimeout(1000);
  g_http.setReuse(true);
  began = g_http.begin(g_client, g_influxURL);

  if (!began) {
    // Could not start HTTP request; keep buffer for next attempt
    return;
  }

  // Add required headers for each request (HTTPClient clears on end())
  g_http.addHeader("Content-Type", "text/plain; charset=utf-8");
  g_http.addHeader("Authorization", String("Token ") + INFLUXDB_TOKEN);
  g_http.addHeader("Connection", "keep-alive");

  int httpCode = g_http.POST((uint8_t*)influxBuffer.c_str(), influxBuffer.length());
  if (httpCode > 0 && httpCode >= 200 && httpCode < 300) {
    // Success, clear buffer
    influxBuffer = "";
    influxLineCount = 0;
  } else {
    Serial.printf("Influx POST failed, code=%d\n", httpCode);
    // Keep data buffered; next attempt will retry
  }

  g_http.end(); // With setReuse(true), underlying TCP may be reused
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

  // Only enqueue here; actual HTTP happens from loop() to avoid blocking callback
  influxEnqueue(latestData);
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

  // Attempt WiFi connection if credentials provided (for Influx pushes)
  ensureWiFiConnected();

  // Prepare Influx URL (HTTP only). If https is configured, warn and skip.
  if (INFLUXDB_BASE_URL && *INFLUXDB_BASE_URL && INFLUXDB_TOKEN && *INFLUXDB_TOKEN) {
    g_influxURL = String(INFLUXDB_BASE_URL) + "/api/v2/write?bucket=" + INFLUXDB_BUCKET +
                  "&org=" + INFLUXDB_ORG;
    if (g_influxURL.startsWith("https://")) {
      Serial.println("HTTPS URL configured, but TLS is disabled. Use http:// base URL.");
      g_influxURL = ""; // disable writes until corrected
    }
  }

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
  // If new data arrived, update the screen.
  if (newDataAvailable) {
    newDataAvailable = false;
    updateDisplay();
  }

  // Lightly maintain WiFi in the background, rate-limited to avoid long stalls
  uint32_t now = millis();
  if (now - lastWiFiCheckMillis >= WIFI_CHECK_PERIOD_MS) {
    lastWiFiCheckMillis = now;
    ensureWiFiConnected();
  }

  // Periodically flush buffered lines
  if (WiFi.status() == WL_CONNECTED) {
    bool timeToFlush = (millis() - lastInfluxFlushMs) >= INFLUX_FLUSH_INTERVAL_MS;
    bool bufferFull = influxLineCount >= INFLUX_MAX_LINES || influxBuffer.length() >= INFLUX_MAX_BUFFER;
    if (timeToFlush || bufferFull) {
      influxFlush();
      lastInfluxFlushMs = millis();
    }
  }

  delay(5);
}