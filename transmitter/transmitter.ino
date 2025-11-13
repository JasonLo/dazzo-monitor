#include <Wire.h>
#include <esp_now.h>
#include <WiFi.h>
#include <Adafruit_BNO055.h>
#include <Adafruit_Sensor.h>
#include "config.h"

// BNO055 setup
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);

// Thresholds
const float MIN_TRANSMISSION_THRESHOLD = 1;
const unsigned long MIN_SEND_INTERVAL = 60000; // 1 minute in milliseconds

// Timing
unsigned long lastSendTime = 0;

// Structure to send
typedef struct {
  float x;
  float y;
  float z;
} SensorData;

void setup() {
  Serial.begin(115200);
  delay(100);

  Wire.begin();
  if (!bno.begin()) {
    Serial.println("BNO055 not detected!");
    while (1) delay(10);
  }

  bno.setExtCrystalUse(true); // improve stability

  // Wi-Fi and ESP-NOW init
  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    while (1) delay(10);
  }

  // Add peer
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, peerAddress, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  esp_now_add_peer(&peerInfo);
}

void loop() {
  imu::Vector<3> acc = bno.getVector(Adafruit_BNO055::VECTOR_LINEARACCEL);
  float x = acc.x(), y = acc.y(), z = acc.z();
  float magnitude = sqrt(x*x + y*y + z*z);

  unsigned long currentTime = millis();
  bool shouldSend = (magnitude >= MIN_TRANSMISSION_THRESHOLD) || 
                    (currentTime - lastSendTime >= MIN_SEND_INTERVAL);

  if (shouldSend) {
    SensorData data = {x, y, z};
    esp_err_t result = esp_now_send(peerAddress, (uint8_t*)&data, sizeof(data));
    if (result == ESP_OK) {
      Serial.printf("Sent: %.2f, %.2f, %.2f (mag: %.2f)\n", x, y, z, magnitude);
      lastSendTime = currentTime;
    } else {
      Serial.println("Send failed");
    }
  } else {
    Serial.println("Below threshold, not sending");
  }

  delay(500); // small delay between readings
}
