#include <Arduino.h>
#include <WiFi.h>
#include <driver/i2s.h>
#include <freertos/ringbuf.h>

// ================= USER CONFIGURATION =================
const char* ssid     = "bbr";
const char* password = "Nopassword1";
const char* host     = "192.168.1.34"; // <--- YOUR PC IP ADDRESS
const int port       = 8010;           // ReSpeaker Service port

// ================= AUDIO SETTINGS =================
#define SAMPLE_RATE     16000
#define I2S_SCK         8
#define I2S_WS          7
#define I2S_SD          44  // Mic Input

// VOLUME CONTROL (Digital Gain)
// 12 is usually the "sweet spot" (16x boost)
// If too loud/distorted, change to 13 or 14.
#define BIT_SHIFT       12 

// Internal Globals
RingbufHandle_t audio_ringbuf;
WiFiClient client;
TaskHandle_t i2s_task_handle;

// ================= CORE 1: RECORDING TASK =================
// This runs on a separate core to ensure smooth recording (No Helicopter noise)
void i2s_reader_task(void *param) {
  size_t bytes_read = 0;
  
  // We process data in small, fast chunks
  const int samples_per_chunk = 256; 
  
  // Buffers
  int32_t raw_buffer[samples_per_chunk]; 
  int16_t clean_buffer[samples_per_chunk]; 

  while (true) {
    // 1. Read Raw 32-bit Data (Blocks until data arrives)
    i2s_read(I2S_NUM_0, raw_buffer, sizeof(raw_buffer), &bytes_read, portMAX_DELAY);
    
    int samples_acquired = bytes_read / 4; // Number of 32-bit samples received
    int idx = 0;

    // 2. PROCESS EVERY SAMPLE (Fixes "Fast" Audio)
    // We iterate i++ (taking everything) instead of i+=2 (skipping half)
    for (int i = 0; i < samples_acquired; i++) {
      
      int32_t sample = raw_buffer[i];

      // Manual Volume Boost
      sample = sample >> BIT_SHIFT;

      // Hard Limiter (Prevents crackling if too loud)
      if (sample > 32767) sample = 32767;
      else if (sample < -32768) sample = -32768;

      clean_buffer[idx++] = (int16_t)sample;
    }

    // 3. Send to Ring Buffer (Safety Net)
    if (idx > 0) {
      // Send data to the buffer so the WiFi loop can pick it up later
      xRingbufferSend(audio_ringbuf, clean_buffer, idx * sizeof(int16_t), pdMS_TO_TICKS(10));
    }
  }
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);

  // 1. Create Ring Buffer (32KB is plenty for audio)
  audio_ringbuf = xRingbufferCreate(32 * 1024, RINGBUF_TYPE_BYTEBUF);
  if (audio_ringbuf == NULL) {
    Serial.println("Error: Could not allocate Ring Buffer");
    while(1);
  }

  // 2. Connect WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWiFi Connected!");

  // 3. Configure I2S (SLAVE MODE - Critical for ReSpeaker)
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_SLAVE | I2S_MODE_RX), 
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    
    // We read everything as a single stream to ensure we don't lose data
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT, 
    
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 16,
    .dma_buf_len = 512,
    .use_apll = false
  };
  
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK, 
    .ws_io_num = I2S_WS, 
    .data_out_num = -1, // Not used
    .data_in_num = I2S_SD
  };

  // Install and Start I2S Driver
  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);

  // 4. Start the Recording Task on Core 1
  // This separates recording from WiFi sending
  xTaskCreatePinnedToCore(
    i2s_reader_task,   // Function
    "I2S Reader",      // Name
    4096,              // Stack size
    NULL,              // Parameters
    1,                 // Priority
    &i2s_task_handle,  // Handle
    1                  // Core ID (1)
  );
  
  Serial.println("System Ready. Waiting for connection...");
}

// ================= CORE 0: WIFI SENDER =================
void loop() {
  // 1. Ensure Connection to PC
  if (!client.connected()) {
    Serial.println("Connecting to PC Server...");
    if (client.connect(host, port)) {
      Serial.println("Connected!");

      // --- NEW: MAC ADDRESS HANDSHAKE ---
      // Send the MAC address (e.g. "AA:BB:CC:DD:EE:FF") as the first message
      String mac = WiFi.macAddress();
      Serial.print("Sending Handshake: ");
      Serial.println(mac);
      client.print(mac);
      // ----------------------------------

      Serial.println("Streaming Audio...");
    } else {
      delay(1000); 
      return;
    }
  }

  // 2. Retrieve Data from Ring Buffer
  size_t size_received = 0;
  // We allow a small wait (10ms) to gather data
  uint8_t *data = (uint8_t *)xRingbufferReceive(audio_ringbuf, &size_received, pdMS_TO_TICKS(10));

  // 3. Send Data to PC
  if (data != NULL) {
    if (client.connected()) {
        client.write(data, size_received);
    }
    
    // Return the memory to the buffer so it can be reused
    vRingbufferReturnItem(audio_ringbuf, (void *)data);
  }
}
