"""
Voice Enrollment & Calibration page.
Manage voice profiles for speaker verification using d-vectors.
Features guided reading prompts and in-browser audio recording.
"""

import streamlit as st
import os
import sys
import tempfile
import numpy as np
import wave
import io
from datetime import datetime

from utils.database import get_database, render_mode_selector

st.set_page_config(page_title="Voice Calibration", page_icon="🎤", layout="wide")

st.title("🎤 Voice Enrollment & Calibration")
st.markdown("Create and manage voice profiles for speaker verification using d-vectors.")

# Add analysis_layer to path
current_dir = os.path.dirname(os.path.abspath(__file__))
analysis_layer_path = os.path.abspath(os.path.join(current_dir, "../../analysis_layer"))
if analysis_layer_path not in sys.path:
    sys.path.append(analysis_layer_path)

try:
    from core.services.VoiceAuthenticationService import VoiceAuthenticationService
except ImportError:
    sys.path.append("/app/analysis_layer")
    try:
        from core.services.VoiceAuthenticationService import VoiceAuthenticationService
    except ImportError:
        VoiceAuthenticationService = None

# Try importing webrtc for browser recording
try:
    from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
    import av
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False

# --- DATABASE CONNECTION ---
db = get_database()
collection = db["user_config"]

# --- READING PROMPTS ---
READING_PROMPTS = {
    "rainbow_passage": {
        "title": "The Rainbow Passage",
        "description": "A classic speech pathology text covering all English phonemes",
        "text": """When the sunlight strikes raindrops in the air, they act as a prism and form a rainbow.
The rainbow is a division of white light into many beautiful colors. These take the shape of a long round arch,
with its path high above, and its two ends apparently beyond the horizon. There is, according to legend,
a boiling pot of gold at one end. People look, but no one ever finds it. When a man looks for something beyond his reach,
his friends say he is looking for the pot of gold at the end of the rainbow.""",
        "duration": "~30 seconds"
    },
    "north_wind": {
        "title": "The North Wind and the Sun",
        "description": "Aesop's fable, commonly used in phonetic research",
        "text": """The North Wind and the Sun were disputing which was the stronger, when a traveler came along
wrapped in a warm cloak. They agreed that the one who first succeeded in making the traveler take his cloak off
should be considered stronger than the other. Then the North Wind blew as hard as he could, but the more he blew
the more closely did the traveler fold his cloak around him; and at last the North Wind gave up the attempt.
Then the Sun shone out warmly, and immediately the traveler took off his cloak. And so the North Wind was obliged
to confess that the Sun was the stronger of the two.""",
        "duration": "~35 seconds"
    },
    "daily_routine": {
        "title": "Daily Routine",
        "description": "Natural conversational speech about everyday activities",
        "text": """I usually wake up around seven in the morning. After getting out of bed, I take a quick shower
and get dressed for the day. Breakfast is usually something simple like toast with coffee. I check my phone
for any important messages while eating. Then I head out to work, which takes about twenty minutes by bus.
During lunch break, I like to take a short walk outside if the weather is nice. In the evening,
I cook dinner and spend some time reading or watching television before going to bed around eleven.""",
        "duration": "~30 seconds"
    },
    "numbers_dates": {
        "title": "Numbers and Dates",
        "description": "Practice with numerical speech patterns",
        "text": """Today is a beautiful day. The temperature is around twenty-two degrees Celsius,
which is about seventy-two degrees Fahrenheit. I was born on March fifteenth, nineteen eighty-five.
My phone number is five five five, one two three four. The meeting is scheduled for two thirty in the afternoon.
There are three hundred and sixty-five days in a year. The population of this city is approximately
one million two hundred thousand people. My apartment is on the fourteenth floor, unit number forty-two.""",
        "duration": "~25 seconds"
    },
    "verification_short": {
        "title": "Quick Verification",
        "description": "Short text for verification tests",
        "text": """Hello, my name is speaking now for voice verification.
I am recording this message to confirm my identity.
The quick brown fox jumps over the lazy dog.
Please verify that this is my voice.""",
        "duration": "~15 seconds"
    }
}


@st.cache_resource
def get_service():
    if VoiceAuthenticationService is None:
        return None
    return VoiceAuthenticationService()


service = get_service()

if service is None:
    st.error("Voice Authentication Service is not available. Please check the installation.")
    st.stop()

# --- SIDEBAR ---
render_mode_selector()

st.sidebar.title("Actions")
st.sidebar.subheader("User ID")

# Get existing users
users_cursor = collection.find({}, {"user_id": 1})
existing_users = sorted(set(u.get("user_id") for u in users_cursor if u.get("user_id")))

selected_user = st.sidebar.text_input(
    "Enter User ID",
    value=st.session_state.get("user_id", ""),
    help="Enter an existing user ID or create a new one",
)

if existing_users:
    st.sidebar.caption(f"Existing profiles: {', '.join(str(u) for u in existing_users[:5])}")

if not selected_user:
    st.warning("Please enter a User ID in the sidebar.")
    st.stop()

st.session_state["user_id"] = selected_user

st.divider()

# --- INSTRUCTIONS ---
with st.expander("📖 How Voice Enrollment Works", expanded=False):
    st.markdown(
        """
        **Voice Enrollment** creates a unique voice profile for speaker verification using d-vectors.

        **What is a d-vector?**
        A d-vector is a high-dimensional numerical representation of your voice characteristics,
        extracted using a deep neural network. It captures the unique acoustic properties that
        make your voice distinguishable from others.

        **Recording Tips:**
        - 🔇 Find a quiet environment with minimal background noise
        - 🎙️ Position yourself about 6-12 inches from the microphone
        - 🗣️ Speak naturally at your normal volume and pace
        - ⏱️ Record at least 30 seconds for enrollment (10+ seconds for verification)
        - 🔄 You can re-record if you make a mistake

        **Privacy Note:** Your voice profile is stored locally and used only for speaker verification.
        """
    )

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📝 Enrollment", "✅ Verification Test", "📊 Profile Status"])

# ============================================================================
# ENROLLMENT TAB
# ============================================================================
with tab1:
    st.header("Voice Enrollment")

    # Check if profile exists
    existing_profile = collection.find_one({"user_id": selected_user, "d_vector": {"$exists": True}})

    if existing_profile:
        st.success(f"✅ Profile exists for user '{selected_user}'")
        st.caption("You can record a new sample to update your profile.")
    else:
        st.info(f"No profile found for user '{selected_user}'. Create one below.")

    st.markdown("### Step 1: Select a Reading Prompt")
    st.markdown("Choose a text to read aloud. Reading a prepared text helps ensure consistent, clear speech.")

    # Prompt selection
    prompt_options = {k: v["title"] for k, v in READING_PROMPTS.items() if k != "verification_short"}
    selected_prompt = st.selectbox(
        "Choose a reading passage:",
        options=list(prompt_options.keys()),
        format_func=lambda x: f"{READING_PROMPTS[x]['title']} ({READING_PROMPTS[x]['duration']})",
    )

    prompt_data = READING_PROMPTS[selected_prompt]

    # Display the prompt
    st.markdown(f"**{prompt_data['title']}**")
    st.caption(prompt_data['description'])

    st.markdown(
        f"""
        <div style="background: #F8F9FA; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #3498DB;
             font-size: 1.1rem; line-height: 1.8; margin: 1rem 0;">
            {prompt_data['text']}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Step 2: Record Your Voice")

    # Recording method selection
    record_method = st.selectbox(
        "Recording method:",
        ["🎙️ Record in Browser", "📁 Upload Audio File"],
        help="Browser recording uses your device's microphone. Upload works with pre-recorded WAV files.",
    )

    audio_data = None

    if record_method == "🎙️ Record in Browser":
        if WEBRTC_AVAILABLE:
            st.markdown("""
            <div style="background: #FEF9E7; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                <strong>Instructions:</strong>
                <ol style="margin: 0.5rem 0 0 1rem; padding: 0;">
                    <li>Click "START" to begin recording</li>
                    <li>Allow microphone access when prompted</li>
                    <li>Read the passage above clearly</li>
                    <li>Click "STOP" when finished</li>
                </ol>
            </div>
            """, unsafe_allow_html=True)

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

            # WebRTC streamer for audio capture
            webrtc_ctx = webrtc_streamer(
                key="voice-enrollment",
                mode=WebRtcMode.SENDONLY,
                audio_receiver_size=256,
                rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
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
                st.success("Audio recorded! Click 'Generate Profile' below to process.")
                audio_data = st.session_state.get("recorded_audio")
        else:
            st.warning(
                "Browser recording requires additional setup. "
                "Please use 'Upload Audio File' option or install streamlit-webrtc."
            )
            st.code("pip install streamlit-webrtc av", language="bash")

            # Fallback: Use Streamlit's built-in audio input (available in newer versions)
            st.markdown("**Alternative: Use your device's voice recorder app and upload the file below.**")

    if record_method == "📁 Upload Audio File":
        st.markdown("""
        <div style="background: #E8F8F5; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
            <strong>Tip:</strong> Use your phone's voice memo app or computer's sound recorder
            to record yourself reading the passage, then upload the file here.
        </div>
        """, unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Upload Audio Recording",
            type=["wav", "mp3", "m4a", "ogg", "flac"],
            key="enroll_upload",
            help="Supported formats: WAV, MP3, M4A, OGG, FLAC",
        )

        if uploaded_file is not None:
            st.audio(uploaded_file, format="audio/wav")
            audio_data = uploaded_file

    st.markdown("### Step 3: Generate Voice Profile")

    col1, col2 = st.columns([1, 2])

    with col1:
        generate_disabled = audio_data is None and "recorded_audio" not in st.session_state

        if st.button(
            "🎤 Generate Profile",
            type="primary",
            use_container_width=True,
            disabled=generate_disabled,
        ):
            with st.spinner("Processing audio and generating voice profile..."):
                try:
                    # Handle different audio sources
                    if isinstance(audio_data, np.ndarray):
                        # From browser recording
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                            # Write numpy array as WAV
                            import soundfile as sf
                            sf.write(tmp.name, audio_data.flatten(), 16000)
                            tmp_path = tmp.name
                    elif audio_data is not None:
                        # From file upload
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                            tmp.write(audio_data.getvalue())
                            tmp_path = tmp.name
                    elif "recorded_audio" in st.session_state:
                        # From session state
                        audio_array = st.session_state["recorded_audio"]
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                            import soundfile as sf
                            sf.write(tmp.name, audio_array.flatten(), 16000)
                            tmp_path = tmp.name
                    else:
                        st.error("No audio data available.")
                        st.stop()

                    service.enroll_user(tmp_path, selected_user, collection)

                    # Clear recorded audio from session
                    if "recorded_audio" in st.session_state:
                        del st.session_state["recorded_audio"]

                    st.success(f"✅ Profile successfully created for user '{selected_user}'!")
                    st.balloons()

                except Exception as e:
                    st.error(f"Error creating profile: {e}")
                finally:
                    if 'tmp_path' in locals() and os.path.exists(tmp_path):
                        os.remove(tmp_path)

    with col2:
        if generate_disabled:
            st.caption("⬆️ Record or upload audio first, then click to generate your profile.")
        else:
            st.caption("Click to process your audio and create/update your voice profile.")

# ============================================================================
# VERIFICATION TAB
# ============================================================================
with tab2:
    st.header("Verification Test")
    st.markdown("Test if the system recognizes your voice with a short recording.")

    # Check if profile exists
    existing_profile = collection.find_one({"user_id": selected_user, "d_vector": {"$exists": True}})

    if not existing_profile:
        st.warning(f"No profile found for user '{selected_user}'. Please complete enrollment first.")
    else:
        st.success(f"✅ Profile found for '{selected_user}'. Ready for verification.")

        # Show verification prompt
        st.markdown("### Reading Prompt for Verification")

        verify_prompt = READING_PROMPTS["verification_short"]
        st.markdown(
            f"""
            <div style="background: #F8F9FA; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #27AE60;
                 font-size: 1.1rem; line-height: 1.8; margin: 1rem 0;">
                {verify_prompt['text']}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(f"Duration: {verify_prompt['duration']}")

        st.markdown("### Upload or Record Verification Sample")

        test_file = st.file_uploader(
            "Upload Test Audio (WAV format)",
            type=["wav", "mp3", "m4a", "ogg", "flac"],
            key="test_upload",
            help="10+ seconds of speech for verification",
        )

        if test_file is not None:
            st.audio(test_file, format="audio/wav")

            if st.button("🔍 Verify Identity", type="primary"):
                with st.spinner("Analyzing voice pattern..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                        tmp.write(test_file.getvalue())
                        tmp_path = tmp.name

                    try:
                        is_match, score, message = service.verify_user(
                            tmp_path, selected_user, collection
                        )

                        # Display result
                        st.markdown("### Verification Result")

                        col1, col2, col3 = st.columns([1, 1, 1])

                        with col1:
                            if is_match:
                                st.markdown(
                                    """
                                    <div style="text-align: center; padding: 2rem; background: #27AE6015; border-radius: 12px; border: 2px solid #27AE60;">
                                        <div style="font-size: 3rem;">✅</div>
                                        <div style="font-size: 1.2rem; font-weight: 600; color: #27AE60;">Identity Verified</div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(
                                    """
                                    <div style="text-align: center; padding: 2rem; background: #E74C3C15; border-radius: 12px; border: 2px solid #E74C3C;">
                                        <div style="font-size: 3rem;">❌</div>
                                        <div style="font-size: 1.2rem; font-weight: 600; color: #E74C3C;">Not Verified</div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

                        with col2:
                            # Score gauge
                            score_color = "#27AE60" if score > 0.75 else "#F39C12" if score > 0.5 else "#E74C3C"
                            st.markdown(
                                f"""
                                <div style="text-align: center; padding: 1.5rem; background: #F8F9FA; border-radius: 12px;">
                                    <div style="font-size: 2.5rem; font-weight: 700; color: {score_color};">{score:.2f}</div>
                                    <div style="color: #7F8C8D;">Similarity Score</div>
                                    <div style="margin-top: 0.5rem;">
                                        <div style="background: #DEE2E6; border-radius: 4px; height: 8px; overflow: hidden;">
                                            <div style="background: {score_color}; width: {min(score * 100, 100)}%; height: 100%;"></div>
                                        </div>
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                        with col3:
                            st.markdown(
                                f"""
                                <div style="padding: 1.5rem; background: #F8F9FA; border-radius: 12px;">
                                    <div style="font-weight: 600; margin-bottom: 0.5rem;">Thresholds</div>
                                    <div style="font-size: 0.9rem; color: #7F8C8D;">
                                        <div>🟢 &gt; 0.75: Match</div>
                                        <div>🟡 0.50 - 0.75: Uncertain</div>
                                        <div>🔴 &lt; 0.50: No match</div>
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                        if not is_match:
                            st.markdown("---")
                            st.markdown("**Possible reasons for failed verification:**")
                            st.markdown("""
                            - Background noise in the recording
                            - Different microphone than enrollment
                            - Speaking too softly or too loudly
                            - Cold or changed voice condition
                            """)

                    except Exception as e:
                        st.error(f"Error during verification: {e}")
                    finally:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)

# ============================================================================
# PROFILE STATUS TAB
# ============================================================================
with tab3:
    st.header("Profile Status")

    profile = collection.find_one({"user_id": selected_user})

    if profile and profile.get("d_vector"):
        st.success(f"✅ Voice profile exists for user '{selected_user}'")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("User ID", selected_user)

        with col2:
            d_vector = profile.get("d_vector", [])
            st.metric("D-Vector Dimensions", len(d_vector) if isinstance(d_vector, list) else "N/A")

        with col3:
            created_at = profile.get("created_at") or profile.get("updated_at")
            if created_at:
                st.metric("Created", created_at.strftime("%b %d, %Y") if hasattr(created_at, 'strftime') else str(created_at)[:10])
            else:
                st.metric("Created", "Unknown")

        st.markdown("---")

        # Profile visualization
        if isinstance(d_vector, list) and len(d_vector) > 0:
            with st.expander("🔬 View D-Vector Visualization"):
                import plotly.graph_objects as go

                # Show first 50 dimensions as bar chart
                display_dims = min(50, len(d_vector))

                fig = go.Figure(data=[
                    go.Bar(
                        x=list(range(display_dims)),
                        y=d_vector[:display_dims],
                        marker_color='#3498DB',
                    )
                ])

                fig.update_layout(
                    title=f"D-Vector (first {display_dims} of {len(d_vector)} dimensions)",
                    xaxis_title="Dimension",
                    yaxis_title="Value",
                    height=300,
                    margin=dict(t=40, b=40),
                )

                st.plotly_chart(fig, use_container_width=True)

                st.caption(
                    "This visualization shows the embedding values that represent your unique voice signature. "
                    "Each bar represents a different acoustic feature dimension."
                )

        st.markdown("---")

        # Danger zone
        st.markdown("### Manage Profile")

        col1, col2 = st.columns([1, 3])

        with col1:
            if st.button("🗑️ Delete Profile", type="secondary"):
                st.session_state["confirm_delete"] = True

        if st.session_state.get("confirm_delete"):
            st.warning("Are you sure you want to delete your voice profile? This cannot be undone.")
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("Yes, Delete", type="primary"):
                    try:
                        collection.update_one(
                            {"user_id": selected_user},
                            {"$unset": {"d_vector": "", "created_at": ""}}
                        )
                        st.session_state["confirm_delete"] = False
                        st.success("Profile deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting profile: {e}")
            with col2:
                if st.button("Cancel"):
                    st.session_state["confirm_delete"] = False
                    st.rerun()

    else:
        st.info(f"No voice profile found for user '{selected_user}'.")

        st.markdown(
            """
            <div style="text-align: center; padding: 3rem; background: #F8F9FA; border-radius: 12px; margin-top: 1rem;">
                <div style="font-size: 4rem; margin-bottom: 1rem;">🎤</div>
                <div style="font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem;">No Voice Profile Yet</div>
                <div style="color: #7F8C8D;">Go to the <strong>Enrollment</strong> tab to create your voice profile.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
