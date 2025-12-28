"""
User Management page for Live Mode.
Manage the identity of users in the Live system mode.
Allows enrollment of new users and management of voice profiles.
"""

import streamlit as st
import requests
import tempfile
import os
import uuid
import time
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.database import get_database, render_mode_selector, get_current_mode
from utils.user_selector import (
    render_user_selector,
    get_user_display_name,
    is_selected_user_calibrated,
    get_selected_user_info,
    clear_user_cache,
)
from utils.alerts import show_toast

# Import BoardRecorder
try:
    from utils.board_recorder import BoardRecorder
    BOARD_RECORDER_AVAILABLE = True
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from utils.board_recorder import BoardRecorder
        BOARD_RECORDER_AVAILABLE = True
    except ImportError:
        BOARD_RECORDER_AVAILABLE = False
        BoardRecorder = None

# Resemblyzer for local recognition tests
try:
    from resemblyzer import VoiceEncoder, preprocess_wav
    RESEMBLYZER_AVAILABLE = True
except ImportError:
    RESEMBLYZER_AVAILABLE = False

st.set_page_config(page_title="User Management", page_icon="👥", layout="wide")

# Mode Check - Only available in Live mode
if get_current_mode() != "live":
    st.warning("⚠️ User Management is only available in Live Mode.")
    st.info("Switch to Live mode from the sidebar to access user management features.")
    st.stop()

render_mode_selector()

st.title("👥 User Management")
st.markdown("""
**Digital Roll Call** - Manage authorized users for voice recognition.
Only registered users will be analyzed by the system.
""")

# --- DATABASE CONNECTION ---
db = get_database()
users_collection = db["users"]
boards_collection = db["boards"]
environments_collection = db["environments"]

# API endpoints
VOICE_PROFILING_API = os.getenv("VOICE_PROFILING_API", "http://voice_profiling:8000")


@st.cache_resource
def get_encoder():
    if RESEMBLYZER_AVAILABLE:
        return VoiceEncoder()
    return None


encoder = get_encoder()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_users():
    """Get all active users from database."""
    try:
        users = list(users_collection.find({"status": "active"}))
        return users
    except Exception as e:
        st.error(f"Error loading users: {e}")
        return []


def delete_user(user_id: str):
    """Delete a user from the database."""
    try:
        # Delete from local collection
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"status": "archived"}}
        )
        
        # Call API to delete from voice_profiling
        try:
            response = requests.delete(f"{VOICE_PROFILING_API}/management/users/{user_id}")
            if response.status_code != 200:
                st.warning(f"API deletion returned status {response.status_code}")
        except Exception as api_error:
            st.warning(f"Could not reach API for deletion: {api_error}")
        
        return True
    except Exception as e:
        st.error(f"Error deleting user: {e}")
        return False


def enroll_user_local(user_id: str, name: str, role: str, audio_path: str):
    """Enroll a user using the enrollment API."""
    try:
        with open(audio_path, 'rb') as f:
            files = {'audio_file': ('enrollment.wav', f, 'audio/wav')}
            data = {
                'user_id': user_id,
                'name': name,
                'role': role
            }
            
            response = requests.post(
                f"{VOICE_PROFILING_API}/enrollment/enroll",
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Also save to local database for dashboard reference
                users_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "user_id": user_id,
                            "name": name,
                            "role": role,
                            "created_at": datetime.utcnow(),
                            "status": "active"
                        }
                    },
                    upsert=True
                )
                
                return True, result
            else:
                return False, {"error": f"API returned {response.status_code}"}
                
    except Exception as e:
        st.error(f"Enrollment error: {e}")
        return False, {"error": str(e)}


# =============================================================================
# MAIN CONTENT
# =============================================================================

# Show current user count
users = get_all_users()
user_count = len(users)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Registered Users", user_count)
with col2:
    patients = len([u for u in users if u.get("role") == "patient"])
    st.metric("Patients", patients)
with col3:
    controls = len([u for u in users if u.get("role") == "control"])
    st.metric("Controls", controls)

st.divider()

# =============================================================================
# TABS
# =============================================================================

tab1, tab2, tab3, tab4 = st.tabs(["📋 User Roster", "➕ Enroll New User", "🔍 Test Recognition", "📡 Live Monitor"])

# =============================================================================
# TAB 1: USER ROSTER
# =============================================================================

with tab1:
    st.header("User Roster")

    if not users:
        st.info("No users registered yet. Use the 'Enroll New User' tab to add users.")
    else:
        st.markdown(f"**{len(users)} registered user(s)**")

        # Batch fetch all enrolled user IDs (fixes N+1 query)
        voice_profiling_collection = db["voice_profiling"]
        enrolled_user_ids = set(
            doc["user_id"]
            for doc in voice_profiling_collection.find({}, {"user_id": 1})
        )

        # Create a table-like display
        for user in users:
            user_id = user.get('user_id', 'N/A')

            # Check if user has voice enrollment (O(1) set lookup)
            has_voice_enrollment = user_id in enrolled_user_ids

            with st.container():
                col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 2, 1, 1])

                with col1:
                    st.markdown(f"**{user.get('name', 'Unknown')}**")
                    st.caption(f"ID: {user_id}")

                with col2:
                    role = user.get('role', 'N/A')
                    role_color = "#3b82f6" if role == "patient" else "#10b981"
                    st.markdown(
                        f'<span style="background: {role_color}20; color: {role_color}; '
                        f'padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.85rem;">'
                        f'{role.upper()}</span>',
                        unsafe_allow_html=True
                    )

                with col3:
                    created = user.get('created_at')
                    if created:
                        if isinstance(created, str):
                            date_str = created[:10]
                        else:
                            date_str = created.strftime('%Y-%m-%d')
                        st.caption(f"📅 {date_str}")

                with col4:
                    # Voice enrollment status
                    if has_voice_enrollment:
                        st.markdown(
                            '<span style="color: #10b981; font-size: 0.85rem;">✅ Voice Enrolled</span>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            '<span style="color: #f59e0b; font-size: 0.85rem;">⚠️ No Voice</span>',
                            unsafe_allow_html=True
                        )

                with col5:
                    # Calibrate voice button
                    calibrate_key = f"cal_{user_id}"
                    if st.button("🎙️", key=calibrate_key, help="Calibrate voice profile"):
                        st.session_state["calibrating_user_id"] = user_id
                        st.session_state["calibrating_user_name"] = user.get('name', 'Unknown')
                        st.session_state["calibrating_user_role"] = user.get('role', 'patient')

                with col6:
                    if st.button("🗑️", key=f"del_{user_id}", help="Delete user"):
                        if delete_user(user_id):
                            clear_user_cache()  # Invalidate cache after deletion
                            st.success(f"User '{user.get('name')}' deleted.")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("Failed to delete user.")

                st.divider()

        # =====================================================================
        # VOICE CALIBRATION MODAL
        # =====================================================================
        if "calibrating_user_id" in st.session_state:
            cal_user_id = st.session_state["calibrating_user_id"]
            cal_user_name = st.session_state.get("calibrating_user_name", "Unknown")
            cal_user_role = st.session_state.get("calibrating_user_role", "patient")

            st.divider()
            st.subheader(f"🎙️ Voice Calibration: {cal_user_name}")
            st.markdown("""
            Record a new voice sample to update this user's voice profile.
            This will improve speaker recognition accuracy.
            """)

            # Reading passage
            cal_passage = """The rainbow is a division of white light into many beautiful colors.
These take the shape of a long round arch, with its path high above."""

            st.markdown(
                f"""
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white; padding: 1rem; border-radius: 8px;
                            font-size: 1rem; line-height: 1.6; margin: 0.5rem 0;">
                    <strong>📖 Read this:</strong> "{cal_passage}"
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Recording method for calibration
            cal_method = st.radio(
                "Recording source:",
                ["Record from Board", "Upload Audio File"],
                horizontal=True,
                key="calibration_method"
            )

            cal_audio_ready = False

            if cal_method == "Record from Board":
                cal_active_boards = list(boards_collection.find({"is_active": True}))
                if not cal_active_boards:
                    st.warning("No active boards found.")
                else:
                    cal_board_opts = {}
                    for b in cal_active_boards:
                        env_name = env_lookup.get(b.get("environment_id"), "Unknown") if 'env_lookup' in dir() else "Unknown"
                        cal_board_opts[b["board_id"]] = f"{b.get('name', 'Unknown')}"

                    cal_selected_board = st.selectbox(
                        "Select Board",
                        options=list(cal_board_opts.keys()),
                        format_func=lambda x: cal_board_opts[x],
                        key="cal_board_select"
                    )

                    col_rec, col_preview = st.columns([1, 2])

                    with col_rec:
                        if st.button("🎙️ Record (15 sec)", type="primary", key="cal_record_btn"):
                            if BOARD_RECORDER_AVAILABLE and BoardRecorder:
                                recorder = BoardRecorder()
                                with st.spinner("Recording... Please read now!"):
                                    audio_data = recorder.start_recording(cal_selected_board, duration=15)

                                if audio_data is not None and len(audio_data) > 0:
                                    st.session_state["calibration_audio_data"] = audio_data
                                    st.success("Recording captured!")
                                    st.rerun()
                                else:
                                    st.error("No audio received.")
                            else:
                                st.error("Board recorder not available.")

                    with col_preview:
                        if "calibration_audio_data" in st.session_state:
                            st.audio(st.session_state["calibration_audio_data"], sample_rate=16000)
                            cal_audio_ready = True

            else:  # Upload File
                cal_uploaded = st.file_uploader(
                    "Upload WAV file",
                    type=["wav", "mp3"],
                    key="cal_upload"
                )
                if cal_uploaded:
                    st.audio(cal_uploaded)
                    st.session_state["calibration_audio_file"] = cal_uploaded
                    cal_audio_ready = True

            # Action buttons
            col_save, col_cancel = st.columns(2)

            with col_save:
                can_calibrate = cal_audio_ready or "calibration_audio_data" in st.session_state or "calibration_audio_file" in st.session_state

                if st.button("✅ Save Voice Profile", type="primary", disabled=not can_calibrate, key="cal_save_btn"):
                    with st.spinner("Updating voice profile..."):
                        try:
                            # Save audio to temporary file
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                                if "calibration_audio_data" in st.session_state:
                                    import soundfile as sf
                                    sf.write(tmp.name, st.session_state["calibration_audio_data"], 16000)
                                elif "calibration_audio_file" in st.session_state:
                                    tmp.write(st.session_state["calibration_audio_file"].getvalue())
                                tmp_path = tmp.name

                            # Re-enroll user via API (updates existing profile)
                            success, result = enroll_user_local(cal_user_id, cal_user_name, cal_user_role, tmp_path)

                            # Cleanup
                            os.remove(tmp_path)

                            if success:
                                clear_user_cache()  # Invalidate cache after profile update
                                st.success(f"Voice profile updated for {cal_user_name}!")

                                # Clear calibration state
                                for key in ["calibrating_user_id", "calibrating_user_name", "calibrating_user_role",
                                           "calibration_audio_data", "calibration_audio_file"]:
                                    if key in st.session_state:
                                        del st.session_state[key]

                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"Failed to update: {result.get('error', 'Unknown error')}")

                        except Exception as e:
                            st.error(f"Error: {e}")

            with col_cancel:
                if st.button("❌ Cancel", key="cal_cancel_btn"):
                    # Clear calibration state
                    for key in ["calibrating_user_id", "calibrating_user_name", "calibrating_user_role",
                               "calibration_audio_data", "calibration_audio_file"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()

# =============================================================================
# TAB 2: ENROLL NEW USER
# =============================================================================

with tab2:
    st.header("Enroll New User")
    st.markdown("""
    Register a new user by providing their information and recording a voice sample.
    The voice sample will be used to create a unique voice profile for speaker identification.
    """)
    
    # User Information Section
    st.subheader("1️⃣ User Information")
    
    col1, col2 = st.columns(2)
    with col1:
        user_name = st.text_input(
            "Full Name *",
            placeholder="Enter user's full name",
            help="The display name for this user"
        )
    
    with col2:
        user_role = st.selectbox(
            "Role *",
            options=["patient", "control"],
            help="Patient: Person being monitored. Control: Household member (not monitored)"
        )
    
    # Voice Sample Section
    st.divider()
    st.subheader("2️⃣ Voice Sample")
    
    st.markdown("""
    **Instructions:** The user should read the passage below clearly for 15-30 seconds.
    This creates a unique voice profile for identification.
    """)
    
    # Reading passage
    passage = """The rainbow is a division of white light into many beautiful colors.
These take the shape of a long round arch, with its path high above,
and its two ends apparently beyond the horizon. There is, according to legend,
a boiling pot of gold at one end. People look, but no one ever finds it."""
    
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white; padding: 1.5rem; border-radius: 12px;
                    font-size: 1.15rem; line-height: 1.8; margin: 1rem 0;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <strong>📖 Reading Passage:</strong><br><br>
            "{passage}"
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Recording method
    st.markdown("#### Choose Recording Method")
    
    # Get active boards
    active_boards = list(boards_collection.find({"is_active": True}))
    env_lookup = {e["environment_id"]: e["name"] for e in environments_collection.find({})}
    
    recording_method = st.radio(
        "Recording source:",
        ["Record from Board", "Upload Audio File"],
        horizontal=True,
        help="Using a board ensures audio quality matches deployment setup"
    )
    
    audio_ready = False
    audio_path = None
    
    if recording_method == "Record from Board":
        if not active_boards:
            st.warning("⚠️ No active boards found. Please ensure a board is connected.")
        else:
            board_options = {}
            for b in active_boards:
                env_name = env_lookup.get(b.get("environment_id"), "Unknown")
                board_options[b["board_id"]] = f"{b.get('name', 'Unknown')} - {env_name}"
            
            selected_board = st.selectbox(
                "Select Board",
                options=list(board_options.keys()),
                format_func=lambda x: board_options[x]
            )
            
            col_a, col_b = st.columns([1, 2])
            
            with col_a:
                duration = st.select_slider(
                    "Duration",
                    options=[15, 20, 30],
                    value=20,
                    format_func=lambda x: f"{x} sec"
                )
                
                if st.button("🎙️ Start Recording", type="primary", use_container_width=True):
                    recorder = BoardRecorder()
                    with st.spinner(f"Recording for {duration} seconds... Please read now!"):
                        audio_data = recorder.start_recording(selected_board, duration=duration)
                    
                    if audio_data is not None and len(audio_data) > 0:
                        st.session_state["enrollment_audio_data"] = audio_data
                        st.session_state["enrollment_method"] = "board"
                        st.success("✅ Recording captured!")
                        st.rerun()
                    else:
                        st.error("❌ No audio received. Check board connection.")
            
            with col_b:
                if "enrollment_audio_data" in st.session_state and st.session_state.get("enrollment_method") == "board":
                    st.success("✅ Audio sample ready!")
                    st.audio(st.session_state["enrollment_audio_data"], sample_rate=16000)
                    audio_ready = True
                    
                    if st.button("🔄 Re-record"):
                        del st.session_state["enrollment_audio_data"]
                        del st.session_state["enrollment_method"]
                        st.rerun()
    
    else:  # Upload File
        uploaded_file = st.file_uploader(
            "Upload WAV or MP3 file",
            type=["wav", "mp3"],
            help="Upload a recording of the user reading the passage"
        )
        
        if uploaded_file:
            st.audio(uploaded_file)
            st.session_state["enrollment_audio_file"] = uploaded_file
            st.session_state["enrollment_method"] = "upload"
            audio_ready = True
    
    # Enrollment Button
    st.divider()
    st.subheader("3️⃣ Complete Enrollment")
    
    can_enroll = user_name and (
        audio_ready or 
        ("enrollment_audio_data" in st.session_state) or 
        ("enrollment_audio_file" in st.session_state)
    )
    
    if st.button(
        "✅ Register User",
        type="primary",
        disabled=not can_enroll,
        use_container_width=True
    ):
        with st.spinner("Processing voice profile..."):
            try:
                # Generate unique user ID
                new_user_id = str(uuid.uuid4())
                
                # Save audio to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    if st.session_state.get("enrollment_method") == "board":
                        # Board recording - save numpy array
                        audio_data = st.session_state.get("enrollment_audio_data")
                        import soundfile as sf
                        sf.write(tmp.name, audio_data, 16000)
                    else:
                        # Uploaded file
                        audio_file = st.session_state.get("enrollment_audio_file")
                        tmp.write(audio_file.getvalue())
                    
                    tmp_path = tmp.name
                
                # Enroll user via API
                success, result = enroll_user_local(new_user_id, user_name, user_role, tmp_path)
                
                # Cleanup
                os.remove(tmp_path)
                
                if success:
                    clear_user_cache()  # Invalidate cache after enrollment
                    st.success(f"🎉 User '{user_name}' enrolled successfully!")
                    st.balloons()

                    # Clear session state
                    for key in ["enrollment_audio_data", "enrollment_audio_file", "enrollment_method"]:
                        if key in st.session_state:
                            del st.session_state[key]

                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error(f"❌ Enrollment failed: {result.get('error', 'Unknown error')}")
            
            except Exception as e:
                st.error(f"❌ Error during enrollment: {e}")
    
    if not can_enroll:
        st.caption("💡 Enter user information and record/upload audio to enable registration.")

# =============================================================================
# TAB 3: TEST RECOGNITION
# =============================================================================

with tab3:
    st.header("Test Recognition")
    st.markdown("Upload or record audio to test if the system can identify a registered user.")

    if not RESEMBLYZER_AVAILABLE:
        st.error("❌ Voice recognition library (resemblyzer) not available.")
        st.info("Please ensure the dashboard container has resemblyzer installed.")
    elif not users:
        st.warning("⚠️ No users registered. Register users first to test recognition.")
    else:
        test_method = st.radio("Test audio source:", ["Upload File", "Record from Board"], horizontal=True, key="test_method_radio")

        test_audio = None

        if test_method == "Upload File":
            test_file = st.file_uploader("Upload test audio", type=["wav", "mp3"], key="test_file_upload")
            if test_file:
                st.audio(test_file)
                test_audio = test_file

        else:
            active_boards = list(boards_collection.find({"is_active": True}))
            if active_boards:
                board_opts = {b["board_id"]: b.get("name", "Unknown") for b in active_boards}
                test_board = st.selectbox("Board", list(board_opts.keys()), format_func=lambda x: board_opts[x], key="test_board_select")

                if st.button("🎙️ Record Test Sample (10s)", key="rec_test_btn"):
                    recorder = BoardRecorder()
                    with st.spinner("Recording..."):
                        audio = recorder.start_recording(test_board, duration=10)
                    if audio is not None:
                        st.session_state["test_audio_data"] = audio
                        st.rerun()

                if "test_audio_data" in st.session_state:
                    st.audio(st.session_state["test_audio_data"], sample_rate=16000)
                    test_audio = st.session_state["test_audio_data"]
            else:
                st.warning("No active boards available.")

        if test_audio is not None:
            if st.button("🔍 Run Recognition Test", type="primary"):
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
                            # Users in 'users' collection should have voice_embedding if enrolled properly
                            if "voice_embedding" in user:
                                ref_embed = np.array(user["voice_embedding"])
                                sim = np.dot(ref_embed, query_embed) / (
                                    np.linalg.norm(ref_embed) * np.linalg.norm(query_embed)
                                )
                                results.append({
                                    "name": user.get("name", "Unknown"),
                                    "similarity": sim,
                                    "user_id": user["user_id"],
                                    "role": user.get("role", "unknown")
                                })

                        os.remove(tmp_path)

                        if results:
                            # Sort by similarity
                            results.sort(key=lambda x: x["similarity"], reverse=True)
                            best = results[0]

                            st.subheader("Recognition Results")

                            if best["similarity"] >= 0.75:
                                st.success(f"✅ Identified: **{best['name']}** (Similarity: {best['similarity']:.1%})")
                            elif best["similarity"] >= 0.6:
                                st.warning(f"⚠️ Possible match: **{best['name']}** (Similarity: {best['similarity']:.1%})")
                            else:
                                st.error("❌ No match found. Speaker not recognized.")

                            # Show all scores
                            st.markdown("##### All Similarity Scores")
                            for r in results:
                                icon = "🟢" if r["similarity"] >= 0.75 else "🟡" if r["similarity"] >= 0.6 else "🔴"
                                st.markdown(f"{icon} **{r['name']}** ({r['role']}): `{r['similarity']:.1%}`")
                        else:
                            st.warning("No users with voice profiles found.")

                            # Clear test audio
                            if "test_audio_data" in st.session_state:
                                del st.session_state["test_audio_data"]

                    except Exception as e:
                        st.error(f"Recognition error: {e}")


# =============================================================================
# TAB 4: LIVE MONITOR
# =============================================================================

with tab4:
    st.header("Live Monitor")
    st.markdown("""
    Real-time audio pipeline monitoring and speaker verification status.
    Monitor gatekeeper decisions, context classification, and data quality.
    """)

    # User selector for monitoring
    st.markdown("#### Select User to Monitor")
    selected_user = render_user_selector()

    if not selected_user:
        st.warning("No users available. Register a user first using the 'Enroll New User' tab.")
    else:
        user_display_name = get_user_display_name(selected_user)

        # Calibration check
        if not is_selected_user_calibrated():
            st.warning(
                f"⚠️ Voice profile missing for {user_display_name}. "
                "Data is being discarded by the gatekeeper. "
                "Use the 'User Roster' tab to calibrate this user's voice."
            )

        # Time window selector
        time_window = st.selectbox(
            "Time Window",
            options=[1, 5, 15, 30, 60],
            index=1,
            format_func=lambda x: f"Last {x} min",
            key="live_monitor_time_window"
        )

        col_refresh, _ = st.columns([1, 3])
        with col_refresh:
            if st.button("🔄 Refresh", key="live_monitor_refresh"):
                st.rerun()

        st.divider()

        # --- DATA LOADING ---
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=time_window)

        # Load scene logs
        scene_logs_collection = db["scene_logs"]
        scene_logs = list(scene_logs_collection.find({
            "user_id": selected_user,
            "timestamp": {"$gte": cutoff_time}
        }).sort("timestamp", -1).limit(500))

        # Load indicator scores
        indicator_collection = db["indicator_scores"]
        indicator_docs = list(
            indicator_collection.find({"user_id": selected_user}).sort("timestamp", -1).limit(50)
        )

        # =============================================================================
        # LIVE STATUS PANEL
        # =============================================================================
        st.subheader("🔴 Pipeline Status")

        col_status1, col_status2, col_status3, col_status4 = st.columns(4)

        with col_status1:
            if scene_logs:
                latest_log = scene_logs[0]
                log_ts = latest_log.get("timestamp", datetime.now(timezone.utc))
                # Handle naive datetime from MongoDB by assuming UTC
                if log_ts.tzinfo is None:
                    log_ts = log_ts.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - log_ts).total_seconds()
                if age < 30:
                    st.success("Pipeline Active")
                    st.caption(f"Last update: {age:.0f}s ago")
                elif age < 120:
                    st.warning("Pipeline Slow")
                    st.caption(f"Last update: {age:.0f}s ago")
                else:
                    st.error("Pipeline Stale")
                    st.caption(f"Last update: {age:.0f}s ago")
            else:
                st.info("No scene data")
                st.caption("Waiting for audio...")

        with col_status2:
            if scene_logs:
                df_scene = pd.DataFrame(scene_logs)
                processed = len(df_scene[df_scene["decision"] == "process"])
                total = len(df_scene)
                rate = (processed / total * 100) if total > 0 else 0
                st.metric("Data Quality", f"{rate:.0f}%", delta=f"{processed}/{total} chunks")
            else:
                st.metric("Data Quality", "N/A")

        with col_status3:
            if scene_logs:
                df_scene = pd.DataFrame(scene_logs)
                if "context" in df_scene.columns:
                    dominant = df_scene["context"].mode().iloc[0] if len(df_scene["context"].mode()) > 0 else "unknown"
                    context_icons = {
                        "solo_activity": "🎤 Solo",
                        "social_interaction": "👥 Social",
                        "background_noise_tv": "📺 Background",
                        "unknown": "❓ Unknown",
                    }
                    st.metric("Room Context", context_icons.get(dominant, dominant))
                else:
                    st.metric("Room Context", "N/A")
            else:
                st.metric("Room Context", "N/A")

        with col_status4:
            if indicator_docs:
                latest_scores = indicator_docs[0].get("indicator_scores", {})
                active_count = sum(1 for v in latest_scores.values() if v is not None and v >= 0.5)
                st.metric("Active Indicators", f"{active_count}/9")
            else:
                st.metric("Active Indicators", "N/A")

        st.divider()

        # =============================================================================
        # SUB-TABS: SCENE ANALYSIS | RAW DATA
        # =============================================================================
        subtab_scene, subtab_data = st.tabs([
            "🔬 Scene Analysis",
            "📋 Raw Data",
        ])

        # --- SCENE ANALYSIS SUB-TAB ---
        with subtab_scene:
            if not scene_logs:
                st.info("No scene logs found. Ensure audio is being processed and a board is connected.")
            else:
                df_scene = pd.DataFrame(scene_logs)
                df_scene["timestamp"] = pd.to_datetime(df_scene["timestamp"])

                # Metrics row
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)

                processed = len(df_scene[df_scene["decision"] == "process"])
                discarded = len(df_scene[df_scene["decision"] == "discard"])
                total = len(df_scene)

                with col_s1:
                    st.metric("Processed", processed, delta=f"{(processed/total*100):.0f}%" if total > 0 else "0%")
                with col_s2:
                    st.metric("Discarded", discarded)
                with col_s3:
                    if "similarity" in df_scene.columns:
                        avg_sim = df_scene[df_scene["similarity"] > 0]["similarity"].mean()
                        st.metric("Avg Similarity", f"{avg_sim:.2f}" if pd.notna(avg_sim) else "N/A")
                    else:
                        st.metric("Avg Similarity", "N/A")
                with col_s4:
                    error_count = len(df_scene[df_scene.get("classification", "") == "error"]) if "classification" in df_scene.columns else 0
                    st.metric("Errors", error_count)

                st.markdown("---")

                # Decision timeline
                st.markdown("##### Gatekeeper Decisions")

                df_sorted = df_scene.sort_values("timestamp")

                fig = px.scatter(
                    df_sorted,
                    x="timestamp",
                    y="classification",
                    color="decision",
                    color_discrete_map={
                        "process": "#22c55e",
                        "discard": "#9ca3af",
                    },
                    hover_data=["similarity", "context"],
                    opacity=[1.0 if d == "process" else 0.4 for d in df_sorted["decision"]],
                )
                fig.update_layout(height=300, showlegend=True)
                st.plotly_chart(fig, use_container_width=True)

                # Context distribution
                st.markdown("##### Context Classification")

                if "context" in df_scene.columns:
                    context_counts = df_scene["context"].value_counts()

                    col_ctx1, col_ctx2 = st.columns([1, 2])

                    with col_ctx1:
                        for ctx, count in context_counts.items():
                            pct = (count / len(df_scene)) * 100
                            ctx_style = {
                                "solo_activity": ("🎤", "#22c55e"),
                                "social_interaction": ("👥", "#8b5cf6"),
                                "background_noise_tv": ("📺", "#9ca3af"),
                                "unknown": ("❓", "#6b7280"),
                            }.get(ctx, ("❓", "#6b7280"))

                            st.markdown(
                                f"""
                                <div style="
                                    display: flex;
                                    align-items: center;
                                    gap: 0.5rem;
                                    padding: 0.5rem;
                                    background: {ctx_style[1]}15;
                                    border-radius: 8px;
                                    margin-bottom: 0.5rem;
                                ">
                                    <span style="font-size: 1.2rem;">{ctx_style[0]}</span>
                                    <span style="flex: 1; font-weight: 500;">{ctx.replace('_', ' ').title()}</span>
                                    <span style="font-weight: 600;">{pct:.0f}%</span>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                    with col_ctx2:
                        fig_ctx = px.pie(
                            values=context_counts.values,
                            names=context_counts.index,
                            color=context_counts.index,
                            color_discrete_map={
                                "solo_activity": "#22c55e",
                                "social_interaction": "#8b5cf6",
                                "background_noise_tv": "#9ca3af",
                                "unknown": "#6b7280",
                            },
                        )
                        fig_ctx.update_traces(textposition='inside', textinfo='percent+label')
                        fig_ctx.update_layout(height=220, showlegend=False)
                        st.plotly_chart(fig_ctx, use_container_width=True)

        # --- RAW DATA SUB-TAB ---
        with subtab_data:
            st.markdown("##### Recent Data")

            data_source = st.selectbox(
                "Data Source",
                ["Scene Logs", "Raw Metrics", "Indicator Scores"],
                key="live_monitor_data_source"
            )

            if data_source == "Scene Logs":
                if scene_logs:
                    df_display = pd.DataFrame(scene_logs)
                    cols_to_show = ["timestamp", "classification", "context", "decision", "similarity"]
                    available = [c for c in cols_to_show if c in df_display.columns]
                    st.dataframe(df_display[available].head(100), use_container_width=True)
                else:
                    st.info("No scene logs available.")

            elif data_source == "Raw Metrics":
                raw_collection = db["raw_metrics"]
                raw_docs = list(raw_collection.find({"user_id": selected_user}).sort("timestamp", -1).limit(100))
                if raw_docs:
                    df_raw = pd.DataFrame(raw_docs)
                    if "timestamp" in df_raw.columns and "metric_name" in df_raw.columns:
                        df_pivot = df_raw.pivot_table(
                            index="timestamp",
                            columns="metric_name",
                            values="metric_value",
                            aggfunc="first"
                        ).reset_index()
                        st.dataframe(df_pivot.head(50), use_container_width=True)
                    else:
                        st.dataframe(df_raw.head(50), use_container_width=True)
                else:
                    st.info("No raw metrics available.")

            elif data_source == "Indicator Scores":
                if indicator_docs:
                    df_ind = pd.DataFrame(indicator_docs)
                    st.dataframe(df_ind[["timestamp", "indicator_scores"]].head(50), use_container_width=True)
                else:
                    st.info("No indicator scores available.")


# =============================================================================
# FOOTER
# =============================================================================

st.divider()
st.caption("👥 User Management - Live Mode Only")
