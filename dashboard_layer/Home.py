"""
Home page - Main entry point for the IHearYou dashboard.
Provides project overview and quick status card.
"""

import streamlit as st
import pandas as pd
import os

from utils.refresh_procedure import refresh_procedure
from utils.setup_db import setup_indexes
from utils.database import get_database, render_mode_selector, render_mode_badge, get_current_mode, MODE_CONFIG
from utils.user_selector import render_user_selector, get_user_display_name, load_users_with_status
from utils.dataset_users import get_dataset_users, get_dataset_user_info, DATASET_USERS

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

# --- SIDEBAR ---
# Mode selector MUST be called first to initialize session state with default mode
render_mode_selector()

# --- DATABASE CONNECTION ---
# Now get database AFTER mode is initialized (defaults to "demo")
db = get_database()

st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()

# Render user selector
selected_user = render_user_selector()

# --- MAIN CONTENT ---
st.title("IHearYou")
st.markdown("### Linking Acoustic Speech Features with Major Depressive Disorder Symptoms")

# Get current mode
current_mode = get_current_mode()

# Mode-specific overview section
mode_config = MODE_CONFIG.get(current_mode, MODE_CONFIG["demo"])

# Show mode description
st.markdown(
    f"""
    <div style="
        padding: 1rem 1.5rem;
        background: {mode_config['color']}10;
        border-left: 4px solid {mode_config['color']};
        border-radius: 0 8px 8px 0;
        margin-bottom: 1.5rem;
    ">
        <div style="font-weight: 600; color: {mode_config['color']}; margin-bottom: 0.25rem;">
            {mode_config['icon']} {mode_config['label']} Mode Active
        </div>
        <div style="color: #555; font-size: 0.9rem;">
            {mode_config['description']}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# In Live mode, show multi-user overview
if current_mode == "live":
    all_users = load_users_with_status()

    if all_users:
        # Calculate status for each user
        user_statuses = {"normal": 0, "monitoring": 0, "attention": 0, "no_data": 0}

        for user in all_users:
            uid = user["user_id"]
            latest_doc = db["indicator_scores"].find_one(
                {"user_id": uid}, sort=[("timestamp", -1)]
            )
            if latest_doc:
                scores = latest_doc.get("indicator_scores", {})
                active = sum(1 for v in scores.values() if v is not None and v >= 0.5)
                has_core = any(
                    k.startswith("1_") or k.startswith("2_")
                    for k, v in scores.items() if v is not None and v >= 0.5
                )
                if active >= 5 and has_core:
                    user_statuses["attention"] += 1
                elif active >= 3:
                    user_statuses["monitoring"] += 1
                else:
                    user_statuses["normal"] += 1
            else:
                user_statuses["no_data"] += 1

        # Display multi-user overview
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: #3b82f615; border-radius: 8px; border-left: 4px solid #3b82f6;">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Tracked Users</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: #3b82f6;">{len(all_users)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col2:
            attention_color = "#E74C3C" if user_statuses["attention"] > 0 else "#27AE60"
            st.markdown(
                f"""
                <div style="padding: 1rem; background: {attention_color}15; border-radius: 8px; border-left: 4px solid {attention_color};">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Needs Attention</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: {attention_color};">{user_statuses["attention"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col3:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: #F39C1215; border-radius: 8px; border-left: 4px solid #F39C12;">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Monitoring</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: #F39C12;">{user_statuses["monitoring"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col4:
            st.markdown(
                f"""
                <div style="padding: 1rem; background: #27AE6015; border-radius: 8px; border-left: 4px solid #27AE60;">
                    <div style="color: #7F8C8D; font-size: 0.9rem;">Normal</div>
                    <div style="font-size: 1.5rem; font-weight: 600; color: #27AE60;">{user_statuses["normal"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.info("No users registered. Go to User Management to add users.")

# In Dataset mode, show available datasets
elif current_mode == "dataset":
    st.markdown("### Available Datasets")
    st.markdown("Each dataset represents a cohort of audio samples that can be analyzed as a virtual 'user'.")

    cols = st.columns(len(DATASET_USERS))
    for i, du in enumerate(DATASET_USERS):
        with cols[i]:
            cohort_icon = "🔴" if du.cohort_type == "depressed" else "🟢"
            st.markdown(
                f"""
                <div style="padding: 1rem; background: {du.color}15; border-radius: 8px; border-left: 4px solid {du.color};">
                    <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">{cohort_icon}</div>
                    <div style="font-weight: 600; color: #2C3E50; margin-bottom: 0.25rem;">{du.name}</div>
                    <div style="font-size: 0.8rem; color: #7F8C8D; margin-bottom: 0.5rem;">{du.source_dataset} Dataset</div>
                    <div style="font-size: 0.75rem; color: #999;">{du.description[:80]}...</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("About Dataset Mode"):
        st.markdown(
            """
            **Dataset Mode** allows you to analyze pre-loaded research datasets using the same
            visualization and analysis tools as live monitoring.

            **Current Datasets:**
            - **TESS (Toronto Emotional Speech Set):** Acted emotional speech samples.
              Sad emotion is used as a proxy for depressed speech patterns,
              while happy emotion represents non-depressed controls.

            **Limitations:**
            - Acted emotions differ from clinical depression manifestations
            - PHQ-9 self-report is not applicable (hidden in this mode)
            - Results should be interpreted as research validation, not clinical diagnosis

            **Future Datasets:**
            - DAIC-WOZ (pending access) - Clinical interviews with PHQ-8 scores
            """
        )

# Show selected user details (for all modes)
if selected_user:
    # Get user display name
    user_display_name = get_user_display_name(selected_user)

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

        # Section header for selected user
        if current_mode == "live":
            st.markdown(f"### Selected User: {user_display_name}")

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
                    <div style="font-size: 1.5rem; font-weight: 600; color: #2C3E50;">{user_display_name}</div>
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

# Define all available cards with page paths
cards = [
    {
        "icon": "🏠",
        "title": "Overview",
        "desc": "Simple wellness summary with patient-friendly indicators",
        "color": "#EBF5FB",
        "page": "pages/1_Overview.py",
        "visible": True
    },
    {
        "icon": "📊",
        "title": "Indicators",
        "desc": "Detailed DSM-5 analysis with clinical drill-down",
        "color": "#FEF9E7",
        "page": "pages/2_Indicators.py",
        "visible": True
    },
    {
        "icon": "📈",
        "title": "Trends",
        "desc": "Track symptom progression over time",
        "color": "#E8F8F5",
        "page": "pages/3_Trends.py",
        "visible": True
    },
]

# Self-Report only for non-dataset modes
if current_mode != "dataset":
    cards.append({
        "icon": "📋",
        "title": "Self-Report",
        "desc": "PHQ-9 questionnaire and history",
        "color": "#FDEDEC",
        "page": "pages/4_Self_Report.py",
        "visible": True
    })

# Add mode-specific cards
if current_mode == "live":
    cards.append({
        "icon": "📡",
        "title": "Boards",
        "desc": "Configure ReSpeaker IoT boards",
        "color": "#F4ECF7",
        "page": "pages/5_Boards.py",
        "visible": True
    })
    cards.append({
        "icon": "👥",
        "title": "User Management",
        "desc": "Manage authorized users for voice recognition",
        "color": "#FEF5E7",
        "page": "pages/8_User_Management.py",
        "visible": True
    })

if current_mode == "dataset":
    cards.append({
        "icon": "💾",
        "title": "Data Tools",
        "desc": "Research validation, hypothesis testing, data export",
        "color": "#E8DAEF",
        "page": "pages/7_Data_Tools.py",
        "visible": True
    })

# Render clickable cards in rows of 3
cols_per_row = 3
for i in range(0, len(cards), cols_per_row):
    row_cards = cards[i:i + cols_per_row]
    cols = st.columns(cols_per_row)

    for j, card in enumerate(row_cards):
        with cols[j]:
            # Create a container with hover effect styling
            st.markdown(
                f"""
                <style>
                    .nav-card-{i+j} {{
                        padding: 1.5rem;
                        background: {card['color']};
                        border-radius: 8px;
                        height: 100%;
                        transition: transform 0.2s, box-shadow 0.2s;
                        cursor: pointer;
                    }}
                    .nav-card-{i+j}:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    }}
                </style>
                """,
                unsafe_allow_html=True,
            )
            # Use page_link for navigation
            with st.container():
                st.page_link(
                    card["page"],
                    label=f"{card['icon']} **{card['title']}**\n\n{card['desc']}",
                    use_container_width=True,
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
