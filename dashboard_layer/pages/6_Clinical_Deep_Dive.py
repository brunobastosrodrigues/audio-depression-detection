import streamlit as st
from pymongo import MongoClient
import pandas as pd
import plotly.graph_objects as go
import json

from utils.SunburstAdapter import SunburstAdapter
from utils.SankeyAdapter import SankeyAdapter
from utils.WaterfallAdapter import WaterfallAdapter

st.set_page_config(page_title="Clinical Deep Dive", layout="wide")

st.title("Clinical Deep Dive")
st.markdown("Detailed visualization of symptom hierarchy, feature importance, and longitudinal progression.")

# --- DB SETUP ---
import os
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
client = MongoClient(MONGO_URI)
db = client["iotsensing"]
collection_ind = db["indicator_scores"]
collection_met = db["analyzed_metrics"]

@st.cache_data
def load_users():
    df = pd.DataFrame(collection_ind.find())
    return df["user_id"].unique()

selected_user = st.session_state.get("user_id", None)

if not selected_user:
    st.warning("Please select a user in the Home tab.")
    st.stop()

st.sidebar.markdown(f"**Analyzing User:** {selected_user}")

# --- DATA LOADING ---
user_inds = list(collection_ind.find({"user_id": selected_user}).sort("timestamp", -1))
if not user_inds:
    st.info("No data found for this user.")
    st.stop()

latest_ind = user_inds[0]
latest_ts = latest_ind["timestamp"]

# Load metrics for the latest timestamp
metric_cursor = collection_met.find({
    "user_id": selected_user,
    "timestamp": latest_ts
})
metric_records = list(metric_cursor)


# --- 1. HIERARCHICAL SUNBURST (7.1) ---
st.header("7.1 Symptom Hierarchy (Sunburst)")
st.markdown("""
**Clinical Utility:** Glanceable status of MDD Support -> DSM-5 Indicators -> Acoustic Features.
Red indicates active thresholds.
""")

try:
    sun_adapter = SunburstAdapter("/app/core/mapping/config.json")
    sun_data = sun_adapter.process(latest_ind, metric_records)

    fig_sun = go.Figure(go.Sunburst(
        ids=sun_data['ids'],
        labels=sun_data['labels'],
        parents=sun_data['parents'],
        values=sun_data['values'],
        marker=dict(colors=sun_data['colors']),
        branchvalues="total",
        hovertemplate='<b>%{label}</b><br>Impact: %{value:.2f}<extra></extra>'
    ))
    fig_sun.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=600)
    st.plotly_chart(fig_sun, use_container_width=True)

except Exception as e:
    st.error(f"Error generating Sunburst: {e}")


# --- 2. EXPLAINABILITY (7.3) ---
st.divider()
st.header("7.3 Feature Explainability (Waterfall)")
st.markdown("""
**Global Relevance:** Understand the drivers of the current state.
Select a specific indicator to see which acoustic features contributed to its score.
""")

# Dropdown to select indicator
with open("core/mapping/config.json", "r") as f:
    config = json.load(f)

# Sort indicators by score in descending order
scores = latest_ind.get('indicator_scores', {})
sorted_inds = sorted(config.keys(), key=lambda k: scores.get(k, 0), reverse=True)

def clean_name(k):
    return k.split('_', 1)[1].replace('_', ' ').title() if '_' in k else k

ind_options = {clean_name(k): k for k in sorted_inds}
selected_ind_name = st.selectbox("Select Indicator to Explain:", list(ind_options.keys()))
selected_ind_key = ind_options[selected_ind_name]

try:
    wf_adapter = WaterfallAdapter("/app/core/mapping/config.json")
    wf_data = wf_adapter.process(selected_ind_key, metric_records)

    if wf_data and len(wf_data['x']) > 1: # Only plot if there are metrics
        fig_wf = go.Figure(go.Waterfall(
            name=wf_data['name'],
            orientation=wf_data['orientation'],
            measure=wf_data['measure'],
            x=wf_data['x'],
            textposition=wf_data['textposition'],
            text=wf_data['text'],
            y=wf_data['y'],
            connector=wf_data['connector']
        ))

        fig_wf.update_layout(
            title=f"Feature Contribution for '{selected_ind_name}'",
            showlegend=False,
            height=500,
            yaxis_title="Contribution to Score"
        )
        st.plotly_chart(fig_wf, use_container_width=True)
    else:
        st.info("No metrics defined or active for this indicator.")

except Exception as e:
    st.error(f"Error generating Waterfall: {e}")


# --- 3. LONGITUDINAL PROGRESSION (7.2) ---
st.divider()
st.header("7.2 Longitudinal Progression (Sankey)")
st.markdown("""
**Dynamics:** Visualizes the flow of dominant symptoms over weeks.
Allows early detection of prodromal phases (e.g., Monopitch -> Loss of Interest).
""")

# Convert list of dicts to DataFrame for Adapter
df_inds = pd.DataFrame(user_inds)

try:
    sankey_adapter = SankeyAdapter("/app/core/mapping/config.json")
    sankey_data = sankey_adapter.process(df_inds)

    if sankey_data:
        fig_sankey = go.Figure(data=[go.Sankey(
            node=sankey_data['node'],
            link=sankey_data['link']
        )])

        fig_sankey.update_layout(
            title_text="Weekly Symptom Progression",
            font_size=12,
            height=500
        )
        st.plotly_chart(fig_sankey, use_container_width=True)
    else:
        st.info("Not enough data for longitudinal analysis.")

except Exception as e:
    st.error(f"Error generating Sankey: {e}")
