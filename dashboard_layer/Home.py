import streamlit as st
from pymongo import MongoClient
import pandas as pd
from utils.refresh_procedure import refresh_procedure
from utils.setup_db import setup_indexes

# Initialize database indexes
try:
    setup_indexes()
except Exception as e:
    print(f"Index setup failed (expected if DB is not ready): {e}")

st.title("IHearYou: Linking Acoustic Speech Features with Major Depressive Disorder Symptoms")

st.markdown("### Abstract")
st.write(
    """
    This master’s thesis introduces a novel approach for automated mental health monitoring. 
    Particularly designed around an acoustic-based approach for depression detection, designed 
    specifically as a software application for IoT-enabled private households. Using passive 
    sensing techniques, the system focuses on the detection of potential depressive behavior 
    to allow timely intervention. By constructing a direct mapping between behavioral patterns 
    and observable clinical symptoms, users can gain insight into their mental health state, 
    helping to overcome the limitations of traditional methods.
    """
)
st.image("assets/conceptual_idea.png", caption="Conceptual project idea.")

st.markdown("### Data Pipeline Overview")
st.write(
    """
    The proposed System Architecture is a platform-based architectural design that supports 
    modular development along a pre-defined data processing pipeline. The architecture 
    promotes reusability, encapsulation of complexity, and independent integration of 
    components. This strategy is particularly suited for multimodal, explainable health 
    assessments in IoT sensing environments.
    """
)
st.image("assets/highlevel_data_pipeline.png", caption="High-level Data Pipeline.")

st.divider()

import os
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
client = MongoClient(MONGO_URI)
db = client["iotsensing"]
collection = db["raw_metrics"]


@st.cache_data
def load_users():
    users = set()
    # Check multiple collections to ensure we find all users
    for col_name in ["raw_metrics", "indicator_scores", "analyzed_metrics"]:
        try:
            users.update(db[col_name].distinct("user_id"))
        except Exception:
            pass
    return sorted(list(users))


users = load_users()

if not users:
    st.warning("No data available.")
    st.stop()


st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()

st.sidebar.subheader("Select User")
selected_user = st.sidebar.selectbox("User", users, key="user_id")

# THIS PART IS ABOUT DELETING USER DATA IN THE DATABASE
# col1, col2 = st.columns(2)

# with col1:
#     if st.button("Reset User"):
#         result = collection.delete_many({"user_id": st.session_state["user_id"]})
#         st.success(
#             f"Deleted {result.deleted_count} records for user {st.session_state['user_id']}"
#         )
#         st.rerun()

# with col2:
#     if st.button("Reset All"):
#         result = collection.delete_many({})
#         st.success(f"Deleted all records ({result.deleted_count} total)")
#         st.rerun()
