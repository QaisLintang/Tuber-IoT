#include <Wire.h>
#include "MAX30100_PulseOximeter.h"
#include <WiFi.h>
#include <PubSubClient.h>

#define REPORTING_PERIOD_MS 1000

PulseOximeter pox;

uint32_t tsLastReport = 0;
int bpm = 0;
int spo2 = 0;

TaskHandle_t Task1;
TaskHandle_t Task2;

SemaphoreHandle_t dataMutex;

// WiFi and MQTT credentials
const char* ssid = "kambing";
const char* password = "cccccccc";
const char* mqtt_server = "broker.mqtt-dashboard.com";

WiFiClient espClient;
PubSubClient client(espClient);

#define MSG_BUFFER_SIZE  (50)
char msg[MSG_BUFFER_SIZE];

void Task1code(void *pvParameters) {
  for (;;) {
    pox.update();
    if (millis() - tsLastReport > REPORTING_PERIOD_MS) {
      bpm = pox.getHeartRate();
      spo2 = pox.getSpO2();

      tsLastReport = millis();
    }
    vTaskDelay(100); // Adjust the delay as needed
  }
}

void Task2code(void *pvParameters) {
  // Attempt WiFi and MQTT connection setup outside the loop
  WiFi.begin(ssid, password);
  client.setServer(mqtt_server, 1883);

  // Wait for WiFi connection
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }

  // Wait for MQTT connection
  while (!client.connected()) {
    if (client.connect("Max30100Client")) {
      Serial.println("Connected to MQTT broker");
    } else {
      Serial.print("MQTT connection failed, rc=");
      Serial.print(client.state());
      Serial.println(" Retrying in 2 seconds...");
      delay(2000);
    }
  }

  // Once connected, loop for data publishing
  for (;;) {
    xSemaphoreTake(dataMutex, portMAX_DELAY);
    int localBpm = bpm;
    int localSpo2 = spo2;
    xSemaphoreGive(dataMutex);

    if (millis() - tsLastReport > REPORTING_PERIOD_MS) {
      snprintf(msg, MSG_BUFFER_SIZE, "Heart rate: %d bpm / SpO2: %d%%", localBpm, localSpo2);
      Serial.print("Publish message: ");
      Serial.println(msg);

      if (client.publish("Max30100", msg)) {
        Serial.println("Message published!");
      } else {
        Serial.println("Failed to publish message.");
      }
      tsLastReport = millis();
    }
    client.loop();
    vTaskDelay(500); // Adjust the delay as needed
  }
}

void setup() {
  Serial.begin(115200);

  if (!pox.begin()) {
    Serial.println("FAILED");
    while (1);
  } else {
    Serial.println("SUCCESS");
  }

  dataMutex = xSemaphoreCreateMutex();

  xTaskCreatePinnedToCore(Task1code, "Task1", 10000, NULL, 1, &Task1, 0);
  delay(500);
  xTaskCreatePinnedToCore(Task2code, "Task2", 10000, NULL, 1, &Task2, 1);
  delay(500);
  
}

void loop() {
  // Nothing to be done here since tasks are runningÂ independently
}
