import streamlit as st
import os
import sys
import numpy as np
import soundfile as sf
import tempfile
from pymongo import MongoClient

# Add analysis_layer to path
current_dir = os.path.dirname(os.path.abspath(__file__))
analysis_layer_path = os.path.abspath(os.path.join(current_dir, "../../analysis_layer"))
if analysis_layer_path not in sys.path:
    sys.path.append(analysis_layer_path)

try:
    from core.services.VoiceAuthenticationService import VoiceAuthenticationService
except ImportError:
    # Fallback for Docker structure if local path fails
    sys.path.append("/app/analysis_layer")
    from core.services.VoiceAuthenticationService import VoiceAuthenticationService


st.title("Voice Enrollment & Calibration")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
client = MongoClient(MONGO_URI)
db = client["iotsensing"]
collection = db["user_config"]

# Initialize Service
@st.cache_resource
def get_service():
    return VoiceAuthenticationService()

service = get_service()

# User Selection
st.sidebar.subheader("Select User")
# Fetch users from user_config or standard place
# Using user_config for simplicity here, or generic list
users_cursor = collection.find({}, {"user_id": 1})
existing_users = [u["user_id"] for u in users_cursor]
# Also allow entering a new user ID
selected_user = st.sidebar.text_input("User ID", value=st.session_state.get("user_id", ""))

if not selected_user:
    st.warning("Please enter or select a User ID.")
    st.stop()

st.session_state["user_id"] = selected_user

tab1, tab2 = st.tabs(["Enrollment", "Verification Test"])

with tab1:
    st.header("1. Enrollment")
    st.write("Please upload a 30-second recording of your voice to create your reference profile.")
    st.write("This generates your unique d-vector embedding.")

    uploaded_file = st.file_uploader("Upload Audio (WAV)", type=["wav"], key="enroll_upload")

    if uploaded_file is not None:
        st.audio(uploaded_file, format='audio/wav')

        if st.button("Generate Profile"):
            with st.spinner("Processing..."):
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name

                try:
                    service.enroll_user(tmp_path, selected_user, collection)
                    st.success(f"Profile successfully created for user '{selected_user}'!")
                except Exception as e:
                    st.error(f"Error creating profile: {e}")
                finally:
                    os.remove(tmp_path)

    st.info("Concept: The system uses a pre-trained encoder to generate a high-dimensional vector from your voice. This reference vector is used to identify you later.")

with tab2:
    st.header("2. Verification Test")
    st.write("Upload a shorter clip (e.g., 10 seconds) to test if the system recognizes you.")

    test_file = st.file_uploader("Upload Audio (WAV)", type=["wav"], key="test_upload")

    if test_file is not None:
        st.audio(test_file, format='audio/wav')

        if st.button("Verify Identity"):
            with st.spinner("Verifying..."):
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(test_file.getvalue())
                    tmp_path = tmp.name

                try:
                    is_match, score, message = service.verify_user(tmp_path, selected_user, collection)

                    st.metric("Similarity Score", f"{score:.4f}", delta="> 0.75 is Match" if score > 0.75 else "Low Similarity")

                    if is_match:
                        st.success(f"Identity Verified! (Score: {score:.2f})")
                    else:
                        st.error(f"Identity Verification Failed. (Score: {score:.2f})")

                except Exception as e:
                    st.error(f"Error verifying: {e}")
                finally:
                    os.remove(tmp_path)
