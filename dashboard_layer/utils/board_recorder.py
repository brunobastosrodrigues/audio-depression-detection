
import os
import sys
import threading
import queue
import time
import json
import base64
import numpy as np
import paho.mqtt.client as mqtt

# Try to find audio_utils or re-implement necessary parts
try:
    from framework.audio_utils import decode_base64_audio
except ImportError:
    # Minimal fallback
    def decode_base64_audio(b64_string, dtype=np.int16):
        audio_bytes = base64.b64decode(b64_string)
        return np.frombuffer(audio_bytes, dtype=dtype)

class BoardRecorder:
    def __init__(self, broker_address="mqtt", broker_port=1883):
        self.client = mqtt.Client()
        self.broker_address = broker_address
        self.broker_port = broker_port
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.target_board_id = None
        self.collected_samples = []
        self.sample_rate = 16000

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT broker")
        else:
            print(f"Failed to connect to MQTT broker, rc: {rc}")

    def on_message(self, client, userdata, msg):
        if not self.is_recording:
            return

        try:
            # Topic format: voice/{user_id}/{board_id}/{env}
            parts = msg.topic.split('/')
            if len(parts) >= 3:
                board_id = parts[2]
                if self.target_board_id and board_id != self.target_board_id:
                    return

                payload = json.loads(msg.payload.decode())
                if 'data' in payload:
                    # Decode audio
                    audio_data = decode_base64_audio(payload['data'])
                    self.audio_queue.put(audio_data)
        except Exception as e:
            print(f"Error processing message: {e}")

    def start_recording(self, board_id, duration=15):
        self.target_board_id = board_id
        self.is_recording = True
        self.collected_samples = []

        try:
            self.client.connect(self.broker_address, self.broker_port, 60)
            self.client.subscribe("voice/+/+/+")
            self.client.loop_start()

            start_time = time.time()
            while time.time() - start_time < duration:
                try:
                    chunk = self.audio_queue.get(timeout=1.0)
                    self.collected_samples.append(chunk)
                except queue.Empty:
                    continue

        except Exception as e:
            print(f"Recording error: {e}")
        finally:
            self.is_recording = False
            self.client.loop_stop()
            self.client.disconnect()

        if self.collected_samples:
            return np.concatenate(self.collected_samples)
        return None
