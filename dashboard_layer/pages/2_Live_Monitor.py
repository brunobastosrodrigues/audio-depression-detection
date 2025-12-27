"""
Live Monitor - Unified Real-Time Dashboard

Consolidates Scene Forensics and Real-Time Indicators into a single coherent view.
Blocks data access if user is not voice-calibrated, presenting an inline
calibration workflow without requiring navigation to separate pages.

Visual Hierarchy:
- Active Data (User Speaking): Full opacity, green highlights
- Context Data (Background): Reduced opacity, gray styling
- Discarded Data: Faded, strikethrough styling
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import json
import plotly.express as px
import plotly.graph_objects as go
import tempfile
import os

from utils.database import get_database, render_mode_selector, get_current_mode
from utils.user_selector import (
    render_user_selector,
    get_user_display_name,
    is_selected_user_calibrated,
    get_selected_user_info,
)
from utils.alerts import (
    render_actionable_banner,
    render_calibration_required_overlay,
    render_data_context_badge,
    show_toast,
)
from utils.theme import (
    COLORS,
    INDICATOR_CLINICAL_NAMES,
    get_severity_color,
    get_mdd_status,
    apply_custom_css,
)

# Page config
st.set_page_config(page_title="Live Monitor", page_icon="📡", layout="wide")
apply_custom_css()

# --- MODE CHECK ---
current_mode = get_current_mode()

# Render mode selector (shows badge and dropdown)
render_mode_selector()

# This page works in all modes but has special features for Live mode
selected_user = render_user_selector()

if not selected_user:
    st.warning("No users available. Register a user first.")
    st.stop()

# --- DATABASE ---
db = get_database()
user_display_name = get_user_display_name(selected_user)

# --- PAGE HEADER ---
st.markdown(
    f"""
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
        <h1 style="margin: 0;">📡 Live Monitor</h1>
        <div style="
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background: {'#dcfce7' if current_mode == 'live' else '#f3f4f6'};
            border-radius: 20px;
        ">
            <span style="font-size: 1.2rem;">{'🟢' if current_mode == 'live' else '🔵'}</span>
            <span style="font-weight: 600;">{user_display_name}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# CALIBRATION GATE (Live Mode Only)
# =============================================================================
if current_mode == "live" and not is_selected_user_calibrated():
    # Block data view and show calibration overlay
    render_actionable_banner(
        message=f"Voice profile missing for {user_display_name}. Data is being discarded by the gatekeeper.",
        alert_type="error",
        action_label="Go to User Management",
        action_page="pages/8_User_Management.py",
        key="calibration_warning",
    )

    show_calibration = render_calibration_required_overlay(
        user_name=user_display_name,
        user_id=selected_user,
    )

    if show_calibration:
        # Inline Voice Recorder Widget
        st.markdown("---")

        # Import board recorder utilities
        try:
            from utils.board_recorder import BoardRecorder
            BOARD_RECORDER_AVAILABLE = True
        except ImportError:
            BOARD_RECORDER_AVAILABLE = False
            BoardRecorder = None

        boards_collection = db["boards"]
        active_boards = list(boards_collection.find({"is_active": True}))

        # Reading passage
        passage = """The rainbow is a division of white light into many beautiful colors.
These take the shape of a long round arch, with its path high above."""

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white; padding: 1rem; border-radius: 8px;
                        font-size: 1rem; line-height: 1.6; margin: 1rem 0;">
                <strong>📖 Read this passage (15 seconds):</strong><br>
                "{passage}"
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_method, col_action = st.columns([2, 1])

        with col_method:
            cal_method = st.radio(
                "Recording method:",
                ["Record from Board", "Upload Audio File"],
                horizontal=True,
                key="inline_cal_method",
            )

        # Recording/Upload logic
        if cal_method == "Record from Board":
            if not active_boards:
                st.warning("No active boards found. Please use file upload or connect a board.")
            else:
                board_opts = {b["board_id"]: b.get("name", "Unknown") for b in active_boards}
                selected_board = st.selectbox(
                    "Select Board",
                    list(board_opts.keys()),
                    format_func=lambda x: board_opts[x],
                    key="inline_cal_board",
                )

                col_rec, col_preview = st.columns([1, 2])

                with col_rec:
                    if st.button("🎙️ Record (15 sec)", type="primary", key="inline_record_btn"):
                        if BOARD_RECORDER_AVAILABLE and BoardRecorder:
                            recorder = BoardRecorder()
                            with st.spinner("Recording... Please read now!"):
                                audio_data = recorder.start_recording(selected_board, duration=15)

                            if audio_data is not None and len(audio_data) > 0:
                                st.session_state["inline_cal_audio"] = audio_data
                                show_toast("Recording captured!", "✅")
                                st.rerun()
                            else:
                                st.error("No audio received. Check board connection.")
                        else:
                            st.error("Board recorder not available.")

                with col_preview:
                    if "inline_cal_audio" in st.session_state:
                        st.audio(st.session_state["inline_cal_audio"], sample_rate=16000)

        else:  # Upload File
            uploaded = st.file_uploader("Upload WAV file", type=["wav", "mp3"], key="inline_cal_upload")
            if uploaded:
                st.audio(uploaded)
                st.session_state["inline_cal_file"] = uploaded

        # Save button
        can_save = "inline_cal_audio" in st.session_state or "inline_cal_file" in st.session_state

        if st.button("✅ Save Voice Profile", type="primary", disabled=not can_save, key="inline_save_btn"):
            with st.spinner("Processing voice profile..."):
                try:
                    import requests

                    VOICE_PROFILING_API = os.getenv("VOICE_PROFILING_API", "http://voice_profiling:8000")

                    # Get user info
                    user_info = get_selected_user_info() or {}
                    user_role = user_info.get("role", "patient")

                    # Save audio to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                        if "inline_cal_audio" in st.session_state:
                            import soundfile as sf
                            sf.write(tmp.name, st.session_state["inline_cal_audio"], 16000)
                        elif "inline_cal_file" in st.session_state:
                            tmp.write(st.session_state["inline_cal_file"].getvalue())
                        tmp_path = tmp.name

                    # Call enrollment API
                    with open(tmp_path, 'rb') as f:
                        files = {'audio_file': ('enrollment.wav', f, 'audio/wav')}
                        data = {
                            'user_id': selected_user,
                            'name': user_display_name,
                            'role': user_role
                        }

                        response = requests.post(
                            f"{VOICE_PROFILING_API}/enrollment/enroll",
                            files=files,
                            data=data,
                            timeout=30
                        )

                    os.remove(tmp_path)

                    if response.status_code == 200:
                        st.success(f"Voice profile created for {user_display_name}!")
                        show_toast("Calibration complete!", "🎉")

                        # Clear session state
                        for key in ["inline_cal_audio", "inline_cal_file"]:
                            if key in st.session_state:
                                del st.session_state[key]

                        st.rerun()
                    else:
                        st.error(f"Enrollment failed: {response.text}")

                except Exception as e:
                    st.error(f"Error: {e}")

    st.stop()  # Block the rest of the page

# =============================================================================
# MAIN DASHBOARD (Calibrated User or Non-Live Mode)
# =============================================================================

# Time window selector
time_window = st.sidebar.selectbox(
    "Time Window",
    options=[1, 5, 15, 30, 60],
    index=1,
    format_func=lambda x: f"Last {x} min",
)

if st.sidebar.button("🔄 Refresh"):
    st.rerun()

st.divider()

# --- DATA LOADING ---
cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=time_window)

# Load scene logs (Live mode)
scene_logs = []
if current_mode == "live":
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
st.subheader("🔴 Live Status")

col_status1, col_status2, col_status3, col_status4 = st.columns(4)

with col_status1:
    if current_mode == "live" and scene_logs:
        latest_log = scene_logs[0]
        age = (datetime.now(timezone.utc) - latest_log.get("timestamp", datetime.now(timezone.utc))).total_seconds()
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
        st.caption("Demo/Dataset mode")

with col_status2:
    if current_mode == "live" and scene_logs:
        df_scene = pd.DataFrame(scene_logs)
        processed = len(df_scene[df_scene["decision"] == "process"])
        total = len(df_scene)
        rate = (processed / total * 100) if total > 0 else 0
        st.metric("Data Quality", f"{rate:.0f}%", delta=f"{processed}/{total} chunks")
    else:
        st.metric("Data Quality", "N/A")

with col_status3:
    if current_mode == "live" and scene_logs:
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
# TABS: INDICATORS | SCENE ANALYSIS | RAW DATA
# =============================================================================
tab_indicators, tab_scene, tab_data = st.tabs([
    "📊 Clinical Indicators",
    "🔬 Scene Analysis" if current_mode == "live" else "🔬 Context (Demo)",
    "📋 Raw Data",
])

# --- CLINICAL INDICATORS TAB ---
with tab_indicators:
    if not indicator_docs:
        st.info("No indicator data available. Run analysis to generate indicators.")
    else:
        latest_doc = indicator_docs[0]
        latest_scores = latest_doc.get("indicator_scores", {})
        latest_ts = latest_doc.get("timestamp")

        # MDD Status calculation
        from utils.DSM5Descriptions import DSM5Descriptions

        active_count = sum(1 for v in latest_scores.values() if v is not None and v >= 0.5)
        has_core = any(
            k in DSM5Descriptions.CORE_INDICATORS and v is not None and v >= 0.5
            for k, v in latest_scores.items()
        )
        status_label, status_color = get_mdd_status(active_count, has_core)

        # Status header
        col_mdd1, col_mdd2 = st.columns([3, 1])
        with col_mdd1:
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <span style="font-size: 1.25rem; font-weight: 600;">Overall Assessment:</span>
                    <span style="background: {status_color}; color: white; padding: 0.5rem 1rem; border-radius: 20px; font-weight: 600;">
                        {status_label}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_mdd2:
            if latest_ts:
                st.caption(f"Updated: {latest_ts.strftime('%H:%M:%S')}")

        st.markdown("<br>", unsafe_allow_html=True)

        # Indicator cards with visual hierarchy
        indicators = sorted(latest_scores.keys())
        cols_per_row = 3

        for i in range(0, len(indicators), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                if i + j < len(indicators):
                    ind = indicators[i + j]
                    score = latest_scores.get(ind)

                    if score is None:
                        score = 0

                    is_active = score >= 0.5
                    display_name = INDICATOR_CLINICAL_NAMES.get(ind, ind)
                    color = get_severity_color(score)

                    # Visual hierarchy: active indicators are prominent
                    opacity = "1" if is_active else "0.6"
                    bg_alpha = "20" if is_active else "08"

                    with col:
                        st.markdown(
                            f"""
                            <div style="
                                padding: 1rem;
                                background: {color}{bg_alpha};
                                border: 2px solid {color}{'60' if is_active else '20'};
                                border-radius: 12px;
                                opacity: {opacity};
                                margin-bottom: 0.5rem;
                            ">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-weight: 600; color: {color if is_active else '#666'};">
                                        {'🔴' if is_active else '⚪'} {display_name}
                                    </span>
                                    <span style="font-size: 1.5rem; font-weight: 700; color: {color};">
                                        {score:.2f}
                                    </span>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

# --- SCENE ANALYSIS TAB ---
with tab_scene:
    if current_mode != "live":
        st.info("Scene analysis is only available in Live mode. Switch to Live mode to see gatekeeper decisions.")
    elif not scene_logs:
        st.info("No scene logs found. Ensure audio is being processed.")
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

        # Decision timeline with visual hierarchy
        st.markdown("### Gatekeeper Decisions")

        # Color by decision with visual hierarchy
        df_sorted = df_scene.sort_values("timestamp")

        fig = px.scatter(
            df_sorted,
            x="timestamp",
            y="classification",
            color="decision",
            color_discrete_map={
                "process": "#22c55e",  # Green - prominent
                "discard": "#9ca3af",  # Gray - faded
            },
            hover_data=["similarity", "context"],
            opacity=[1.0 if d == "process" else 0.4 for d in df_sorted["decision"]],
        )
        fig.update_layout(height=350, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

        # Context distribution with badges
        st.markdown("### Context Classification")

        if "context" in df_scene.columns:
            context_counts = df_scene["context"].value_counts()

            col_ctx1, col_ctx2 = st.columns([1, 2])

            with col_ctx1:
                for ctx, count in context_counts.items():
                    pct = (count / len(df_scene)) * 100
                    ctx_style = {
                        "solo_activity": ("🎤", "#22c55e", "Active"),
                        "social_interaction": ("👥", "#8b5cf6", "Context"),
                        "background_noise_tv": ("📺", "#9ca3af", "Context"),
                        "unknown": ("❓", "#6b7280", "Unknown"),
                    }.get(ctx, ("❓", "#6b7280", "Unknown"))

                    opacity = "1" if ctx_style[2] == "Active" else "0.7"

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
                            opacity: {opacity};
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
                fig_ctx.update_layout(height=250, showlegend=False)
                st.plotly_chart(fig_ctx, use_container_width=True)

# --- RAW DATA TAB ---
with tab_data:
    st.markdown("### Recent Data")

    data_source = st.selectbox(
        "Data Source",
        ["Scene Logs", "Raw Metrics", "Indicator Scores"] if current_mode == "live" else ["Raw Metrics", "Indicator Scores"],
    )

    if data_source == "Scene Logs" and current_mode == "live":
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

    # Export button
    if st.button("📥 Export Data"):
        show_toast("Export functionality coming soon!", "📦")

# --- FOOTER ---
st.divider()
st.caption(f"📡 Live Monitor | {current_mode.upper()} Mode | User: {user_display_name}")
