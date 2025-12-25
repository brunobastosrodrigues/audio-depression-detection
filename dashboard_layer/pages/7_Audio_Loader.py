import streamlit as st
import os
import sys
import threading
import time
from pathlib import Path

# Add data_ingestion_layer to path so we can import modules
DATA_INGESTION_PATH = "/app/data_ingestion_layer"
if os.path.exists(DATA_INGESTION_PATH):
    if DATA_INGESTION_PATH not in sys.path:
        sys.path.append(DATA_INGESTION_PATH)
else:
    # Fallback for local testing/development if not in container
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    ingestion_path = os.path.join(repo_root, "data_ingestion_layer")
    if os.path.exists(ingestion_path) and ingestion_path not in sys.path:
        sys.path.append(ingestion_path)
        DATA_INGESTION_PATH = ingestion_path


# Try importing VoiceFromFile
try:
    from implementations.VoiceFromFile import VoiceFromFile
except ImportError as e:
    st.error(f"Failed to import VoiceFromFile: {e}")
    VoiceFromFile = None


# Define a stoppable wrapper
class StoppableVoiceFromFile:
    def __init__(self, filepath, topic="voice/mic1", mqtthostname="mqtt", mqttport=1883):
        if VoiceFromFile is None:
            raise ImportError("VoiceFromFile class is not available.")

        self.device = VoiceFromFile(
            filepath=filepath,
            topic=topic,
            mqtthostname=mqtthostname,
            mqttport=mqttport
        )
        self.running = False
        self.thread = None
        self.error = None
        self.completed = False

    def _run_loop(self):
        print(f"Starting playback of {self.device.filepath}")
        try:
            while self.running:
                # Collect audio chunk
                raw = self.device.collect()

                # Check for End of File
                if raw is None:
                    print("End of file reached.")
                    self.completed = True
                    break

                # Process and publish
                filtered = self.device.filter(raw)
                if filtered is not None:
                    self.device.transport(filtered)

                # Sleep to simulate real-time (approximate)
                time.sleep(0.01)

        except Exception as e:
            print(f"Error during playback: {e}")
            self.error = str(e)
        finally:
            self.running = False
            self.device.stop()
            print("Playback stopped.")

    def start(self):
        if self.running:
            return
        self.running = True
        self.completed = False
        self.error = None
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None

# Streamlit UI
st.title("Audio Data Loader")
st.markdown("Use this tool to stream pre-recorded audio files into the system for debugging purposes.")

# Dataset Directory
DATASETS_DIR = "/app/datasets"
if not os.path.exists(DATASETS_DIR):
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    DATASETS_DIR = os.path.join(repo_root, "datasets")

if not os.path.exists(DATASETS_DIR):
    st.error(f"Datasets directory not found at {DATASETS_DIR}")
    st.stop()

# List Files
try:
    files = [f for f in os.listdir(DATASETS_DIR) if f.endswith(".wav")]
except Exception as e:
    st.error(f"Error reading datasets directory: {e}")
    files = []

if not files:
    st.warning("No .wav files found in datasets directory.")
    st.stop()

# Select File
default_index = 0
if "long_depressed_sample_nobreak.wav" in files:
    default_index = files.index("long_depressed_sample_nobreak.wav")
elif "performance_test.wav" in files:
    default_index = files.index("performance_test.wav")

selected_file = st.selectbox("Select Audio File", files, index=default_index)
filepath = os.path.join(DATASETS_DIR, selected_file)

st.write(f"**Selected File:** `{filepath}`")

# Initialize session state for streamer
if "streamer" not in st.session_state:
    st.session_state.streamer = None

col1, col2 = st.columns(2)

with col1:
    if st.button("▶ Start Streaming", type="primary"):
        if st.session_state.streamer is not None and st.session_state.streamer.running:
            st.warning("Already streaming!")
        else:
            try:
                mqtthost = os.getenv("MQTT_HOST", "mqtt")
                st.session_state.streamer = StoppableVoiceFromFile(
                    filepath=filepath,
                    mqtthostname=mqtthost
                )
                st.session_state.streamer.start()
                st.rerun()
            except Exception as e:
                st.error(f"Failed to start streaming: {e}")

with col2:
    if st.button("⏹ Stop Streaming"):
        if st.session_state.streamer:
            st.session_state.streamer.stop()
            st.session_state.streamer = None
            st.rerun()

# Status Display
if st.session_state.streamer:
    if st.session_state.streamer.running:
        st.info(f"Streaming {os.path.basename(st.session_state.streamer.device.filepath)}...")
        # Auto-refresh to check status (e.g. completion)
        time.sleep(1)
        st.rerun()
    elif st.session_state.streamer.completed:
        st.success("Playback completed.")
        # Clean up streamer object so we can start again
        st.session_state.streamer = None
    elif st.session_state.streamer.error:
        st.error(f"Error: {st.session_state.streamer.error}")
        st.session_state.streamer = None
    else:
        # Stopped manually or initial state
        pass
