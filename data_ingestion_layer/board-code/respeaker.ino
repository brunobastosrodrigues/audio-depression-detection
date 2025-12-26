#include <Arduino.h>
#include <WiFi.h>
#include <driver/i2s.h>
#include <freertos/ringbuf.h>

// ================= USER CONFIGURATION =================
const char* ssid     = "bbr";
const char* password = "Nopassword1";
const char* host     = "192.168.1.34"; // <--- YOUR PC IP ADDRESS
const int port       = 8010;

// ================= HIGH-FIDELITY AUDIO SETTINGS =================
#define SAMPLE_RATE     16000
#define I2S_SCK         8
#define I2S_WS          7
#define I2S_SD          44  // Mic Input

// VAD SETTINGS (Edge Intelligence)
// Threshold: Adjust this if it cuts off too much (Lower = More Sensitive)
#define VAD_THRESHOLD   150 
// Hangover: Keeps recording for 500ms AFTER you stop speaking
// This preserves the "breathiness" or "trailing off" at the end of sentences.
#define HANGOVER_MS     500 

// DIGITAL GAIN
// 12 is the standard boost for ReSpeaker. 
// If audio is too quiet, try 11. If distorted, try 13.
#define BIT_SHIFT       12 

// Internal Globals
RingbufHandle_t audio_ringbuf;
WiFiClient client;
TaskHandle_t i2s_task_handle;

// ================= CORE 1: SMART AUDIO TASK =================
void i2s_reader_task(void *param) {
  size_t bytes_read = 0;
  
  // Buffers
  const int samples_per_chunk = 256; 
  int32_t raw_buffer[samples_per_chunk]; 
  int16_t clean_buffer[samples_per_chunk]; 

  // VAD State Variables
  unsigned long last_speech_time = 0;
  bool is_streaming = false;

  while (true) {
    // 1. READ RAW DATA
    // We request 32-bit data. Because we configured "ONLY_LEFT" in setup,
    // this data comes directly from the XMOS Noise Suppression engine.
    i2s_read(I2S_NUM_0, raw_buffer, sizeof(raw_buffer), &bytes_read, portMAX_DELAY);
    
    int samples_acquired = bytes_read / 4;
    int idx = 0;
    long energy_sum = 0;

    // 2. PROCESS & CONVERT
    for (int i = 0; i < samples_acquired; i++) {
      int32_t sample = raw_buffer[i];

      // Digital Gain Boost
      sample = sample >> BIT_SHIFT;

      // Soft Limiter (Prevents harsh digital clipping distortion)
      if (sample > 32767) sample = 32767;
      else if (sample < -32768) sample = -32768;

      int16_t final_sample = (int16_t)sample;
      clean_buffer[idx++] = final_sample;
      
      // Calculate Energy (Loudness) for VAD
      energy_sum += abs(final_sample);
    }

    // 3. EDGE LOGIC (VAD)
    float average_energy = energy_sum / samples_acquired;

    // Detect Voice
    if (average_energy > VAD_THRESHOLD) {
      last_speech_time = millis(); // Reset "silence" timer
      is_streaming = true;
    }

    // Check Hangover (Are we still in the "tail" of the speech?)
    if (millis() - last_speech_time < HANGOVER_MS) {
        is_streaming = true;
    } else {
        is_streaming = false;
    }

    // 4. SMART SEND
    // Only send data if we are actively streaming. 
    // This utilizes the hardware to filter silence, saving bandwidth.
    if (is_streaming && idx > 0) {
      xRingbufferSend(audio_ringbuf, clean_buffer, idx * sizeof(int16_t), pdMS_TO_TICKS(10));
    }
    // Note: If silence, we drop the data here. The loop continues instantly.
  }
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);

  // 1. Create Ring Buffer
  audio_ringbuf = xRingbufferCreate(32 * 1024, RINGBUF_TYPE_BYTEBUF);
  if (audio_ringbuf == NULL) {
    Serial.println("Error: Failed to create Ring Buffer");
    while(1);
  }

  // 2. Connect WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWiFi Connected!");

  // 3. I2S CONFIGURATION (CRITICAL FOR QUALITY)
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_SLAVE | I2S_MODE_RX), // Slave Mode = Perfect Sync with XMOS Clock
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,       // Native ReSpeaker depth
    
    // THIS LINE IS THE KEY TO QUALITY:
    // "ONLY_LEFT" selects Channel 0, which carries the XMOS Processed Audio (Noise Cancelled).
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
    .data_out_num = -1, 
    .data_in_num = I2S_SD
  };

  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);

  // 4. Start the Smart Task
  xTaskCreatePinnedToCore(
    i2s_reader_task,   
    "HighFi_Reader",      
    4096,              
    NULL,              
    1,                 
    &i2s_task_handle,  
    1                  
  );
  
  Serial.println("High-Fidelity Audio System Ready.");
}

// ================= CORE 0: WIFI SENDER =================
void loop() {
  // 1. Connection Logic
  if (!client.connected()) {
    Serial.println("Connecting to PC Server...");
    if (client.connect(host, port)) {
      Serial.println("Connected!");

      // REQUIRED: Handshake with MAC Address
      String mac = WiFi.macAddress();
      Serial.print("Sending Handshake: ");
      Serial.println(mac);
      client.print(mac);
      
      // Wait for Server Acknowledgment
      unsigned long start_wait = millis();
      bool server_ready = false;
      while (millis() - start_wait < 5000) {
        if (client.available()) {
          String response = client.readStringUntil('\n');
          if (response.indexOf("READY") >= 0) {
            server_ready = true;
            break;
          }
        }
        delay(10);
      }

      if (server_ready) {
        Serial.println("Server Ready! Streaming Audio...");
      } else {
        Serial.println("Server handshake failed or timed out.");
        client.stop();
        return;
      }
    } else {
      delay(1000); 
      return;
    }
  }

  // 2. Retrieve Data (Empty if VAD is active & room is silent)
  size_t size_received = 0;
  uint8_t *data = (uint8_t *)xRingbufferReceive(audio_ringbuf, &size_received, pdMS_TO_TICKS(10));

  // 3. Send
  if (data != NULL) {
    if (client.connected()) {
        client.write(data, size_received);
    }
    vRingbufferReturnItem(audio_ringbuf, (void *)data);
  }
}
