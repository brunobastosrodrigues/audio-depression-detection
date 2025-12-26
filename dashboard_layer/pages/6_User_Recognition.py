"""
User Recognition page.
Register users and manage voice profiles for speaker identification.
Registration is REQUIRED for metrics to be computed.
"""

import streamlit as st
import os
import sys
import tempfile
import numpy as np
import uuid
import time
from datetime import datetime

from utils.database import get_database, render_mode_selector, get_current_mode

# Board recorder
try:
    from utils.board_recorder import BoardRecorder
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.board_recorder import BoardRecorder

# Resemblyzer
try:
    from resemblyzer import VoiceEncoder, preprocess_wav
    RESEMBLYZER_AVAILABLE = True
except ImportError:
    RESEMBLYZER_AVAILABLE = False

st.set_page_config(page_title="User Recognition", page_icon="🎤", layout="wide")

# Mode Check
if get_current_mode() != "live":
    st.info("This page is only available in Live mode.")
    st.stop()

render_mode_selector()

st.title("User Recognition")

# --- DATABASE CONNECTION ---
db = get_database()
user_config_collection = db["user_config"]
voice_profiling_collection = db["voice_profiling"]
boards_collection = db["boards"]
environments_collection = db["environments"]


@st.cache_resource
def get_encoder():
    if RESEMBLYZER_AVAILABLE:
        return VoiceEncoder()
    return None


encoder = get_encoder()

if not RESEMBLYZER_AVAILABLE:
    st.error("Resemblyzer library not available. Voice recognition features disabled.")
    st.stop()


def enroll_user(audio_path: str, user_id: str, user_data: dict) -> bool:
    """Generate voice embedding and store user profile."""
    try:
        wav = preprocess_wav(audio_path)
        embedding = encoder.embed_utterance(wav)

        # Store in user_config (dashboard storage)
        user_config_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "voice_profile": embedding.tolist(),
                    "d_vector": embedding.tolist(),
                    "name": user_data.get("name"),
                    "gender": user_data.get("gender"),
                    "age": user_data.get("age"),
                    "registered_at": user_data.get("registered_at", datetime.utcnow()),
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )

        # Also store in voice_profiling collection for processing layer
        voice_profiling_collection.update_one(
            {"user_id": user_id},
            {"$set": {"embedding": embedding.tolist(), "updated_at": datetime.utcnow()}},
            upsert=True,
        )

        return True
    except Exception as e:
        st.error(f"Enrollment error: {e}")
        return False


def get_registered_users():
    """Get all registered users."""
    users = list(user_config_collection.find({"voice_profile": {"$exists": True}}))
    return users


def delete_user(user_id: str):
    """Delete a user profile."""
    user_config_collection.delete_one({"user_id": user_id})
    voice_profiling_collection.delete_one({"user_id": user_id})


# =============================================================================
# MAIN CONTENT
# =============================================================================

st.markdown("""
**Voice registration is required** for the system to compute metrics.
Only audio from recognized speakers will be processed and analyzed.
""")

# Show registration status
users = get_registered_users()

if not users:
    st.warning("No users registered. Please register at least one user to start collecting metrics.")
else:
    st.success(f"{len(users)} user(s) registered. The system is ready to process audio.")

st.divider()

# =============================================================================
# TABS
# =============================================================================
tab_register, tab_users, tab_verify = st.tabs(["Register New User", "Registered Users", "Test Recognition"])

# =============================================================================
# TAB 1: REGISTER NEW USER
# =============================================================================
with tab_register:
    st.header("Register New User")
    st.markdown("Complete the form below to register a new user for voice recognition.")

    # User Details Section
    st.subheader("1. User Details")

    col1, col2, col3 = st.columns(3)
    with col1:
        user_name = st.text_input("Name *", placeholder="Enter full name")
    with col2:
        user_gender = st.selectbox("Gender", ["Male", "Female", "Non-binary", "Prefer not to say"])
    with col3:
        user_age = st.number_input("Age", min_value=1, max_value=120, value=30)

    if not user_name:
        st.info("Please enter a name to continue.")
    else:
        st.divider()

        # Voice Sample Section
        st.subheader("2. Record Voice Sample")

        st.markdown("""
        Read the passage below **once, clearly** (~10-15 seconds). This creates your unique voice profile.
        """)

        # Simple, short passage
        passage = """The rainbow is a division of white light into many beautiful colors.
These take the shape of a long round arch, with its path high above,
and its two ends apparently beyond the horizon."""

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white; padding: 1.5rem; border-radius: 12px;
                        font-size: 1.15rem; line-height: 1.8; margin: 1rem 0;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <strong>Read this passage:</strong><br><br>
                "{passage}"
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### Choose Recording Method")

        # Get active boards
        active_boards = list(boards_collection.find({"is_active": True}))
        env_lookup = {e["environment_id"]: e["name"] for e in environments_collection.find({})}

        method = st.radio(
            "Recording source:",
            ["Record from Board (Recommended)", "Upload Audio File"],
            horizontal=True,
            help="Using a registered board ensures audio quality matches your deployment setup.",
        )

        audio_ready = False
        audio_source = None

        if method == "Record from Board (Recommended)":
            if not active_boards:
                st.warning("No active boards found. Please ensure a board is connected and streaming.")
                st.caption("Go to the Boards page to check board status.")
            else:
                board_options = {}
                for b in active_boards:
                    env_name = env_lookup.get(b.get("environment_id"), "Unknown")
                    board_options[b["board_id"]] = f"{b.get('name', 'Unknown')} - {env_name}"

                selected_board = st.selectbox(
                    "Select Board",
                    options=list(board_options.keys()),
                    format_func=lambda x: board_options[x],
                )

                col_rec, col_status = st.columns([1, 2])

                with col_rec:
                    record_duration = st.select_slider(
                        "Recording duration",
                        options=[10, 15, 20],
                        value=15,
                        format_func=lambda x: f"{x} seconds",
                    )

                    if st.button("Start Recording", type="primary", use_container_width=True):
                        recorder = BoardRecorder()
                        with st.spinner(f"Recording for {record_duration} seconds... Please read the passage now!"):
                            recorded_audio = recorder.start_recording(selected_board, duration=record_duration)

                        if recorded_audio is not None and len(recorded_audio) > 0:
                            st.session_state["enrollment_audio"] = recorded_audio
                            st.session_state["enrollment_source"] = "board"
                            st.success("Recording captured!")
                            st.rerun()
                        else:
                            st.error("No audio received. Ensure the board is streaming.")

                with col_status:
                    if "enrollment_audio" in st.session_state and st.session_state.get("enrollment_source") == "board":
                        st.success("Audio sample ready!")
                        st.audio(st.session_state["enrollment_audio"], sample_rate=16000)
                        audio_ready = True
                        audio_source = "session"

                        if st.button("Clear Recording", type="secondary"):
                            del st.session_state["enrollment_audio"]
                            del st.session_state["enrollment_source"]
                            st.rerun()

        else:  # Upload File
            uploaded_file = st.file_uploader(
                "Upload a WAV or MP3 file",
                type=["wav", "mp3"],
                help="Record yourself reading the passage above.",
            )

            if uploaded_file:
                st.audio(uploaded_file)
                st.session_state["enrollment_audio"] = uploaded_file
                st.session_state["enrollment_source"] = "upload"
                audio_ready = True
                audio_source = "upload"

        # Registration Button
        st.divider()
        st.subheader("3. Complete Registration")

        can_register = user_name and (
            audio_ready
            or ("enrollment_audio" in st.session_state)
        )

        if st.button(
            "Register User",
            type="primary",
            disabled=not can_register,
            use_container_width=True,
        ):
            with st.spinner("Processing voice profile..."):
                try:
                    # Generate unique ID
                    new_user_id = str(uuid.uuid4())

                    # Save audio to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                        audio_data = st.session_state.get("enrollment_audio")

                        if isinstance(audio_data, np.ndarray):
                            import soundfile as sf
                            sf.write(tmp.name, audio_data, 16000)
                        elif hasattr(audio_data, "getvalue"):
                            tmp.write(audio_data.getvalue())
                        elif hasattr(audio_data, "read"):
                            tmp.write(audio_data.read())

                        tmp_path = tmp.name

                    # Enroll user
                    user_data = {
                        "name": user_name,
                        "gender": user_gender,
                        "age": user_age,
                        "registered_at": datetime.utcnow(),
                    }

                    success = enroll_user(tmp_path, new_user_id, user_data)

                    # Cleanup
                    os.remove(tmp_path)

                    if success:
                        st.success(f"User '{user_name}' registered successfully!")
                        st.balloons()

                        # Clear session state
                        if "enrollment_audio" in st.session_state:
                            del st.session_state["enrollment_audio"]
                        if "enrollment_source" in st.session_state:
                            del st.session_state["enrollment_source"]

                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Registration failed. Please try again.")

                except Exception as e:
                    st.error(f"Error during registration: {e}")

        if not can_register:
            st.caption("Enter user details and record a voice sample to enable registration.")

# =============================================================================
# TAB 2: REGISTERED USERS
# =============================================================================
with tab_users:
    st.header("Registered Users")

    users = get_registered_users()

    if not users:
        st.info("No users registered yet. Use the 'Register New User' tab to add users.")
    else:
        for user in users:
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 2, 1])

                with col1:
                    st.markdown(f"**{user.get('name', 'Unknown')}**")

                with col2:
                    st.caption(f"Gender: {user.get('gender', 'N/A')}")

                with col3:
                    st.caption(f"Age: {user.get('age', 'N/A')}")

                with col4:
                    reg_date = user.get("registered_at") or user.get("updated_at")
                    if reg_date:
                        st.caption(f"Registered: {reg_date.strftime('%Y-%m-%d')}")

                with col5:
                    if st.button("Delete", key=f"del_{user['user_id']}", type="secondary"):
                        delete_user(user["user_id"])
                        st.success(f"User '{user.get('name')}' deleted.")
                        time.sleep(0.5)
                        st.rerun()

                st.divider()

        # Update voice profile section
        st.subheader("Update Voice Profile")
        st.markdown("Re-record a user's voice sample to improve recognition accuracy.")

        user_options = {u["user_id"]: u.get("name", "Unknown") for u in users}
        selected_user_id = st.selectbox(
            "Select user to update",
            options=list(user_options.keys()),
            format_func=lambda x: user_options[x],
        )

        if selected_user_id:
            update_method = st.radio("Recording method:", ["Board", "Upload"], horizontal=True, key="update_method")

            if update_method == "Board":
                active_boards = list(boards_collection.find({"is_active": True}))
                if active_boards:
                    board_opts = {b["board_id"]: b.get("name", "Unknown") for b in active_boards}
                    sel_board = st.selectbox("Board", list(board_opts.keys()), format_func=lambda x: board_opts[x], key="upd_board")

                    if st.button("Record Update Sample (15s)", key="upd_rec"):
                        recorder = BoardRecorder()
                        with st.spinner("Recording..."):
                            audio = recorder.start_recording(sel_board, duration=15)
                        if audio is not None and len(audio) > 0:
                            st.session_state["update_audio"] = audio
                            st.success("Recorded!")
                else:
                    st.warning("No active boards.")

            else:
                upd_file = st.file_uploader("Upload file", type=["wav", "mp3"], key="upd_file")
                if upd_file:
                    st.session_state["update_audio"] = upd_file

            if "update_audio" in st.session_state:
                if st.button("Update Profile", type="primary", key="upd_btn"):
                    with st.spinner("Updating..."):
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                            audio_data = st.session_state["update_audio"]
                            if isinstance(audio_data, np.ndarray):
                                import soundfile as sf
                                sf.write(tmp.name, audio_data, 16000)
                            else:
                                tmp.write(audio_data.getvalue())
                            tmp_path = tmp.name

                        user_doc = user_config_collection.find_one({"user_id": selected_user_id})
                        success = enroll_user(tmp_path, selected_user_id, user_doc or {})
                        os.remove(tmp_path)

                        if success:
                            st.success("Profile updated!")
                            del st.session_state["update_audio"]
                            st.rerun()

# =============================================================================
# TAB 3: TEST RECOGNITION
# =============================================================================
with tab_verify:
    st.header("Test Recognition")
    st.markdown("Upload or record audio to test if the system can identify a registered user.")

    users = get_registered_users()

    if not users:
        st.warning("No users registered. Register users first to test recognition.")
    else:
        test_method = st.radio("Test audio source:", ["Upload File", "Record from Board"], horizontal=True)

        test_audio = None

        if test_method == "Upload File":
            test_file = st.file_uploader("Upload test audio", type=["wav", "mp3"], key="test_file")
            if test_file:
                st.audio(test_file)
                test_audio = test_file

        else:
            active_boards = list(boards_collection.find({"is_active": True}))
            if active_boards:
                board_opts = {b["board_id"]: b.get("name", "Unknown") for b in active_boards}
                test_board = st.selectbox("Board", list(board_opts.keys()), format_func=lambda x: board_opts[x], key="test_board")

                if st.button("Record Test Sample (10s)"):
                    recorder = BoardRecorder()
                    with st.spinner("Recording..."):
                        audio = recorder.start_recording(test_board, duration=10)
                    if audio is not None:
                        st.session_state["test_audio"] = audio
                        st.rerun()

                if "test_audio" in st.session_state:
                    st.audio(st.session_state["test_audio"], sample_rate=16000)
                    test_audio = st.session_state["test_audio"]
            else:
                st.warning("No active boards available.")

        if test_audio is not None:
            if st.button("Run Recognition Test", type="primary"):
                with st.spinner("Analyzing voice..."):
                    try:
                        # Save to temp
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                            if isinstance(test_audio, np.ndarray):
                                import soundfile as sf
                                sf.write(tmp.name, test_audio, 16000)
                            else:
                                tmp.write(test_audio.getvalue())
                            tmp_path = tmp.name

                        # Generate embedding
                        wav = preprocess_wav(tmp_path)
                        query_embed = encoder.embed_utterance(wav)

                        # Compare against all users
                        results = []
                        for user in users:
                            if "voice_profile" in user:
                                ref_embed = np.array(user["voice_profile"])
                                sim = np.dot(ref_embed, query_embed) / (
                                    np.linalg.norm(ref_embed) * np.linalg.norm(query_embed)
                                )
                                results.append({
                                    "name": user.get("name", "Unknown"),
                                    "similarity": sim,
                                    "user_id": user["user_id"],
                                })

                        os.remove(tmp_path)

                        if results:
                            # Sort by similarity
                            results.sort(key=lambda x: x["similarity"], reverse=True)
                            best = results[0]

                            st.subheader("Recognition Results")

                            if best["similarity"] >= 0.75:
                                st.success(f"Identified: **{best['name']}** (similarity: {best['similarity']:.2%})")
                            elif best["similarity"] >= 0.6:
                                st.warning(f"Possible match: **{best['name']}** (similarity: {best['similarity']:.2%})")
                            else:
                                st.error("No match found. Speaker not recognized.")

                            # Show all scores
                            st.markdown("##### All Similarity Scores")
                            for r in results:
                                icon = "🟢" if r["similarity"] >= 0.75 else "🟡" if r["similarity"] >= 0.6 else "🔴"
                                st.markdown(f"{icon} **{r['name']}**: {r['similarity']:.2%}")

                            # Clear test audio
                            if "test_audio" in st.session_state:
                                del st.session_state["test_audio"]

                    except Exception as e:
                        st.error(f"Recognition error: {e}")
