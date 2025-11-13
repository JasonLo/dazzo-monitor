#pragma once

// Copy this file to `secrets.h` and fill in your values.
// `secrets.h` is git-ignored to keep credentials out of source control.

// Wi-Fi credentials
#define WIFI_SSID               "YOUR_WIFI_SSID"
#define WIFI_PASSWORD           "YOUR_WIFI_PASSWORD"

// InfluxDB v2 settings (HTTP only; HTTPS/TLS is not supported in receiver)
// Example for local Influx: "http://192.168.1.10:8086"
#define INFLUXDB_BASE_URL       "http://192.168.1.10:8086"
#define INFLUXDB_ORG            "home"
#define INFLUXDB_BUCKET         "dazzo"
#define INFLUXDB_TOKEN          "YOUR_INFLUXDB_TOKEN"

// Device identity used as the `sensor` tag value in line protocol
#define SENSOR_NAME             "feather-receiver"
