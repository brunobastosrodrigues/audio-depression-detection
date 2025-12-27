"""
Home page - Main entry point for the IHearYou dashboard.
Provides project overview and quick status card.
"""

import streamlit as st
import pandas as pd
import os

from utils.refresh_procedure import refresh_procedure
from utils.setup_db import setup_indexes
from utils.database import get_database, render_mode_selector, render_mode_badge, get_current_mode
from utils.user_selector import render_user_selector

# Initialize database indexes
try:
    setup_indexes()
except Exception as e:
    print(f"Index setup failed (expected if DB is not ready): {e}")

st.set_page_config(
    page_title="IHearYou - Depression Detection",
    page_icon="🧠",
    layout="wide",
)

# --- DATABASE CONNECTION ---
db = get_database()


# --- SIDEBAR ---
# Mode selector at top of sidebar
render_mode_selector()

st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()

# Render user selector
selected_user = render_user_selector()

# --- MAIN CONTENT ---
st.title("IHearYou")
st.markdown("### Linking Acoustic Speech Features with Major Depressive Disorder Symptoms")

# Quick status card if user is selected
if selected_user:
    # Get latest indicator data
    latest_doc = db["indicator_scores"].find_one(
        {"user_id": selected_user}, sort=[("timestamp", -1)]
    )

    if latest_doc:
        indicator_scores = latest_doc.get("indicator_scores", {})
        timestamp = latest_doc.get("timestamp")

        # Calculate status (handle None values)
        active_count = sum(1 for v in indicator_scores.values() if v is not None and v >= 0.5)
        has_core = any(
            k.startswith("1_") or k.startswith("2_")
            for k, v in indicator_scores.items()
            if v is not None and v >= 0.5
        )

        if active_count >= 5 and has_core:
            status = "Needs Attention"
            status_color = "#E74C3C"
        elif active_count >= 3:
            status = "Monitoring"
            status_color = "#F39C12"
        else:
            status = "Normal"
            status_color = "#27AE60"

        # Display status card
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: {status_color}15; border-radius: 8px; border-left: 4px solid {status_color};">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Status</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: {status_color};">{status}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: #F8F9FA; border-radius: 8px;">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Active Indicators</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: #2C3E50;">{active_count} / 9</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col3:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: #F8F9FA; border-radius: 8px;">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">User</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: #2C3E50;">{selected_user}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col4:
            last_update = timestamp.strftime("%b %d, %H:%M") if timestamp else "N/A"
            st.markdown(
                f"""
                <div style="padding: 1rem; background: #F8F9FA; border-radius: 8px;">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Last Updated</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: #2C3E50;">{last_update}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

    else:
        st.info("No analysis data available. Click 'Refresh Analysis' to process voice data.")

st.divider()

# Navigation hints
st.markdown("### Quick Navigation")

# Define all available cards
cards = [
    {
        "icon": "🏠", 
        "title": "Overview", 
        "desc": "Simple wellness summary with patient-friendly indicators", 
        "color": "#EBF5FB",
        "visible": True
    },
    {
        "icon": "📊", 
        "title": "Indicators", 
        "desc": "Detailed DSM-5 analysis with clinical drill-down", 
        "color": "#FEF9E7",
        "visible": True
    },
    {
        "icon": "📈", 
        "title": "Trends", 
        "desc": "Track symptom progression over time", 
        "color": "#E8F8F5",
        "visible": True
    },
    {
        "icon": "📋", 
        "title": "Self-Report", 
        "desc": "PHQ-9 questionnaire and history", 
        "color": "#FDEDEC",
        "visible": True
    },
]

# Add mode-specific cards
current_mode = get_current_mode()

if current_mode == "live":
    cards.append({
        "icon": "📡", 
        "title": "Boards", 
        "desc": "Configure ReSpeaker IoT boards", 
        "color": "#F4ECF7",
        "visible": True
    })
    cards.append({
        "icon": "👥", 
        "title": "User Management", 
        "desc": "Manage authorized users for voice recognition", 
        "color": "#FEF5E7",
        "visible": True
    })

if current_mode == "dataset":
    cards.append({
        "icon": "💾",
        "title": "Data Tools",
        "desc": "Audio loader, baseline viewer, export",
        "color": "#E8DAEF",
        "visible": True
    })

# Render cards in rows of 3
cols_per_row = 3
for i in range(0, len(cards), cols_per_row):
    row_cards = cards[i:i + cols_per_row]
    cols = st.columns(cols_per_row)
    
    for j, card in enumerate(row_cards):
        with cols[j]:
            st.markdown(
                f"""
                <div style="padding: 1.5rem; background: {card['color']}; border-radius: 8px; height: 100%;">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">{card['icon']}</div>
                    <div style="font-weight: 600; margin-bottom: 0.5rem;">{card['title']}</div>
                    <div style="color: #7F8C8D; font-size: 0.9rem;">{card['desc']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("<br>", unsafe_allow_html=True)

st.divider()

# Project information (collapsible)
with st.expander("About This Project", expanded=False):
    st.markdown(
        """
        This master's thesis introduces a novel approach for automated mental health monitoring.
        Particularly designed around an acoustic-based approach for depression detection, designed
        specifically as a software application for IoT-enabled private households.

        Using passive sensing techniques, the system focuses on the detection of potential depressive
        behavior to allow timely intervention. By constructing a direct mapping between behavioral
        patterns and observable clinical symptoms, users can gain insight into their mental health
        state, helping to overcome the limitations of traditional methods.
        """
    )

    st.image("assets/conceptual_idea.png", caption="Conceptual project idea.")

with st.expander("Data Pipeline", expanded=False):
    st.markdown(
        """
        The proposed System Architecture is a platform-based architectural design that supports
        modular development along a pre-defined data processing pipeline. The architecture
        promotes reusability, encapsulation of complexity, and independent integration of
        components.
        """
    )

    st.image("assets/highlevel_data_pipeline.png", caption="High-level Data Pipeline.")
