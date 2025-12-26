"""
User Recognition & Enrollment page.
Manage voice profiles for speaker verification using resemblyzer (VoiceEncoder).
Features guided reading prompts, in-browser audio recording, and board recording.
"""

import streamlit as st
import os
import sys
import tempfile
import numpy as np
import wave
import io
import uuid
import time
from datetime import datetime

# Import utils
from utils.database import get_database, render_mode_selector, get_current_mode

# Board recorder
try:
    from utils.board_recorder import BoardRecorder
except ImportError:
    # Handle relative import if needed
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.board_recorder import BoardRecorder

# --- REAMBLYSER & UTILS SETUP ---
try:
    from resemblyzer import VoiceEncoder, preprocess_wav
    from scipy.io.wavfile import write as write_wav
    RESEMBLYZER_AVAILABLE = True
except ImportError:
    RESEMBLYZER_AVAILABLE = False

st.set_page_config(page_title="User Recognition", page_icon="🎤", layout="wide")

# Mode Check
if get_current_mode() != "live":
    st.info("This page is only available in Live mode.")
    st.stop()

st.title("User Recognition")
st.markdown("Register users and manage voice profiles. **Registration is required** for metric computation.")

# Try importing webrtc for browser recording
try:
    from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
    import av
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False

# --- DATABASE CONNECTION ---
db = get_database()
user_config_collection = db["user_config"]
boards_collection = db["boards"]
# We also need to interface with processing_layer's storage if we want to be compatible
# But for now we stick to user_config and I will update VoiceAuthenticationService logic if possible
# Or just implement enrollment here directly using Resemblyzer to be compatible with live system.

# --- ENROLLMENT LOGIC (RESEMBLYZER) ---
# We will implement the enrollment logic directly here to ensure compatibility with processing_layer
# which uses resemblyzer.

@st.cache_resource
def get_encoder():
    if RESEMBLYZER_AVAILABLE:
        return VoiceEncoder()
    return None

encoder = get_encoder()

if not RESEMBLYZER_AVAILABLE:
    st.error("Resemblyzer library not found. Please install it to use this feature.")
    st.stop()

def enroll_user_resemblyzer(audio_path, user_id, user_data):
    """
    Generates embedding using Resemblyzer and stores it.
    """
    wav = preprocess_wav(audio_path)
    embedding = encoder.embed_utterance(wav)

    # Store in user_config (dashboard storage)
    user_config_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "voice_profile": embedding.tolist(), # Store as list
            "d_vector": embedding.tolist(), # Legacy compatibility
            "name": user_data.get("name"),
            "gender": user_data.get("gender"),
            "age": user_data.get("age"),
            "updated_at": datetime.utcnow()
        }},
        upsert=True
    )

    # Also store in 'voice_profiling' collection if it exists (Live System)
    # This ensures the processing_layer (live system) picks it up.
    try:
        voice_profiling_collection = db["voice_profiling"] # This might need to be iotsensing.voice_profiling
        # Check if we are in live mode, usually db is iotsensing_live.
        # But processing_layer usually connects to 'iotsensing'.
        # We try to write to 'voice_profiling' in the current DB.

        voice_profiling_collection.update_one(
             {"user_id": user_id},
             {"$set": {
                 "embedding": embedding.tolist(),
                 "updated_at": datetime.utcnow()
             }},
             upsert=True
        )
    except Exception as e:
        print(f"Could not update voice_profiling collection: {e}")

    return True

# --- SIDEBAR: USER SELECTION ---
render_mode_selector()

st.sidebar.title("User Management")

# Fetch users
users_cursor = user_config_collection.find({}, {"user_id": 1, "name": 1})
users_dict = {u.get("user_id"): u.get("name", "Unknown") for u in users_cursor if u.get("user_id")}

action = st.sidebar.radio("Action", ["Select Existing User", "Register New User"])

selected_user_id = None
user_metadata = {}

if action == "Select Existing User":
    if users_dict:
        selected_user_id_str = st.sidebar.selectbox(
            "Select User",
            options=list(users_dict.keys()),
            format_func=lambda x: f"{users_dict[x]} ({x})"
        )
        selected_user_id = selected_user_id_str
        # Load metadata
        user_doc = user_config_collection.find_one({"user_id": selected_user_id})
        if user_doc:
            st.sidebar.info(f"**Name:** {user_doc.get('name')}\n\n**Gender:** {user_doc.get('gender')}\n\n**Age:** {user_doc.get('age')}")
    else:
        st.sidebar.warning("No users found.")
else:
    st.sidebar.subheader("New User Details")
    new_name = st.sidebar.text_input("Name")
    new_gender = st.sidebar.selectbox("Gender", ["Male", "Female", "Non-binary", "Prefer not to say"])
    new_age = st.sidebar.number_input("Age", min_value=0, max_value=120, value=25)

    if new_name:
        # Generate ID only when we actually enroll, or preview it
        # We will generate it during enrollment process
        pass

# --- MAIN CONTENT ---

# TABS
tab1, tab2 = st.tabs(["📝 Enrollment", "✅ Verification Check"])

with tab1:
    st.header("Voice Enrollment")

    if action == "Register New User" and not new_name:
        st.info("👈 Please enter user details in the sidebar to start registration.")
    elif action == "Select Existing User" and not selected_user_id:
        st.info("👈 Please select a user in the sidebar.")
    else:
        # Enrollment Flow
        if action == "Register New User":
             st.markdown(f"### Registering: {new_name}")
             st.info("Registration requires a voice sample. Metrics will ONLY be computed for registered voices.")
        else:
             st.markdown(f"### Update Voice Profile: {users_dict[selected_user_id]}")

        st.markdown("#### Step 1: Record Voice Sample")
        st.caption("Please read the text below clearly.")

        # Simplified Prompt
        prompt_text = """When the sunlight strikes raindrops in the air, they act as a prism and form a rainbow.
The rainbow is a division of white light into many beautiful colors."""

        st.markdown(
            f"""
            <div style="background: #F8F9FA; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #3498DB;
                 font-size: 1.2rem; line-height: 1.6; margin: 1rem 0;">
                {prompt_text}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Recording Methods
        method = st.radio("Recording Method", ["Microphone (Browser)", "Record from Board", "Upload File"], horizontal=True)

        audio_data = None

        if method == "Microphone (Browser)":
            if WEBRTC_AVAILABLE:
                # Audio processor for capturing audio
                class AudioProcessor(AudioProcessorBase):
                    def __init__(self):
                        self.audio_frames = []
                        self.sample_rate = 16000

                    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
                        # Store audio data
                        audio_array = frame.to_ndarray()
                        self.audio_frames.append(audio_array)
                        return frame

                webrtc_ctx = webrtc_streamer(
                    key="enrollment-recorder",
                    mode=WebRtcMode.SENDONLY,
                    audio_receiver_size=256,
                    media_stream_constraints={"video": False, "audio": True},
                )

                if webrtc_ctx.audio_receiver:
                    st.info("🎤 Recording in progress... Read the passage above.")

                    # Collect audio frames
                    audio_frames = []
                    try:
                        while True:
                            frame = webrtc_ctx.audio_receiver.get_frame(timeout=1)
                            audio_frames.append(frame.to_ndarray())
                    except Exception:
                        pass

                    if audio_frames:
                        # Combine frames
                        audio_array = np.concatenate(audio_frames, axis=1)
                        st.session_state["recorded_audio"] = audio_array
                        st.success(f"✅ Recorded {len(audio_frames)} frames")

                # Check for recorded audio in session state
                if "recorded_audio" in st.session_state:
                    st.success("Audio recorded! Click 'Complete Registration' below to process.")
                    audio_data = st.session_state.get("recorded_audio")
            else:
                st.error("WebRTC not installed.")

        elif method == "Record from Board":
            st.markdown("#### Record from a connected ReSpeaker Board")
            # List boards
            active_boards = list(boards_collection.find({"is_active": True}))
            if not active_boards:
                st.warning("No active boards found.")
            else:
                board_options = {b['board_id']: f"{b.get('name', 'Unknown')} ({b.get('environment_name', 'Unknown')})" for b in active_boards}
                selected_board_id = st.selectbox("Select Board", options=list(board_options.keys()), format_func=lambda x: board_options[x])

                if st.button("🔴 Start Recording (15s)"):
                    recorder = BoardRecorder()
                    with st.spinner(f"Recording from {board_options[selected_board_id]} for 15 seconds... Please speak now."):
                        recorded_audio = recorder.start_recording(selected_board_id, duration=15)

                    if recorded_audio is not None and len(recorded_audio) > 0:
                        st.success("Audio captured from board!")
                        st.session_state["board_audio"] = recorded_audio
                    else:
                        st.error("Failed to capture audio. Ensure the board is streaming.")

            if "board_audio" in st.session_state:
                st.audio(st.session_state["board_audio"], sample_rate=16000)
                audio_data = st.session_state["board_audio"]

        elif method == "Upload File":
            uploaded = st.file_uploader("Upload WAV/MP3", type=["wav", "mp3"])
            if uploaded:
                st.audio(uploaded)
                audio_data = uploaded

        # Enroll Button
        if st.button("Complete Registration / Update Profile", type="primary", disabled=(audio_data is None and "board_audio" not in st.session_state and "recorded_audio" not in st.session_state)):
            # Prepare audio file
            with st.spinner("Processing voice profile..."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                        if isinstance(audio_data, np.ndarray):
                            # From browser recording
                            # Ensure we handle different shapes if needed, but simple write is ok if it's 1D/2D
                            if audio_data.ndim == 2:
                                # (Channels, Samples) -> (Samples, Channels) or Flatten if mono
                                # Webrtc usually gives (Channels, Samples)
                                audio_data = audio_data.T
                            import soundfile as sf
                            sf.write(tmp.name, audio_data, 16000)
                        elif hasattr(audio_data, "getvalue"):
                            tmp.write(audio_data.getvalue())
                        elif "board_audio" in st.session_state:
                             import soundfile as sf
                             sf.write(tmp.name, st.session_state["board_audio"], 16000)

                        tmp_path = tmp.name

                    # Determine User ID
                    if action == "Register New User":
                        uid = str(uuid.uuid4())
                        u_data = {"name": new_name, "gender": new_gender, "age": new_age}
                    else:
                        uid = selected_user_id
                        # Get existing data to preserve or update
                        u_data = user_config_collection.find_one({"user_id": uid})

                    # Enroll
                    enroll_user_resemblyzer(tmp_path, uid, u_data)

                    st.success(f"User {u_data['name']} successfully registered/updated!")
                    if action == "Register New User":
                        st.info(f"Assigned User ID: {uid}")

                    # Cleanup
                    os.remove(tmp_path)
                    if "board_audio" in st.session_state:
                        del st.session_state["board_audio"]

                    time.sleep(1)
                    st.rerun()

                except Exception as e:
                    st.error(f"Enrollment failed: {e}")

with tab2:
    st.header("Verification Check")
    # Simple check against selected user
    if selected_user_id:
        st.markdown(f"Verify against **{users_dict.get(selected_user_id)}**")

        check_file = st.file_uploader("Upload Audio to Verify", key="verify_up")
        if check_file:
             if st.button("Verify"):
                 with st.spinner("Verifying..."):
                     # Load profile
                     user_doc = user_config_collection.find_one({"user_id": selected_user_id})
                     if not user_doc or "voice_profile" not in user_doc:
                         st.error("No profile found.")
                     else:
                         ref_embed = np.array(user_doc["voice_profile"])

                         with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                            tmp.write(check_file.getvalue())
                            tmp_path = tmp.name

                         wav = preprocess_wav(tmp_path)
                         query_embed = encoder.embed_utterance(wav)

                         # Cosine similarity
                         sim = np.dot(ref_embed, query_embed) / (np.linalg.norm(ref_embed) * np.linalg.norm(query_embed))

                         st.metric("Similarity Score", f"{sim:.2f}")
                         if sim > 0.75:
                             st.success("✅ Match Confirmed")
                         else:
                             st.error("❌ No Match")

                         os.remove(tmp_path)
    else:
        st.info("Select a user from the sidebar to verify.")
