"""
Centralized database connection with multi-mode support.

Usage:
    from utils.database import get_database, render_mode_selector

    # In your page:
    render_mode_selector()  # Add mode selector to sidebar
    db = get_database()      # Get database for current mode
"""

import os
import streamlit as st
from pymongo import MongoClient

# Database routing map
DB_MAP = {
    "live": "iotsensing_live",
    "dataset": "iotsensing_dataset",
    "demo": "iotsensing_demo",
}

# Mode display configuration
MODE_CONFIG = {
    "live": {
        "label": "Live",
        "color": "#22c55e",  # Green
        "icon": "🟢",
        "description": "Real patient data from physical boards",
    },
    "dataset": {
        "label": "Dataset",
        "color": "#3b82f6",  # Blue
        "icon": "🔵",
        "description": "Research data from file injections",
    },
    "demo": {
        "label": "Demo",
        "color": "#f97316",  # Orange
        "icon": "🟠",
        "description": "Golden demo data for showcases",
    },
}

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
_client = None


def get_client() -> MongoClient:
    """Get or create MongoDB client (singleton)."""
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client


def get_database(mode: str = None):
    """
    Get MongoDB database for the specified mode.

    Args:
        mode: System mode ('live', 'dataset', 'demo').
              If None, uses st.session_state.system_mode or defaults to 'live'.

    Returns:
        MongoDB database object
    """
    if mode is None:
        mode = st.session_state.get("system_mode", "live")

    db_name = DB_MAP.get(mode, "iotsensing_live")
    return get_client()[db_name]


def get_current_mode() -> str:
    """Get current system mode from session state."""
    return st.session_state.get("system_mode", "live")


def set_mode(mode: str):
    """Set system mode in session state."""
    if mode in DB_MAP:
        st.session_state.system_mode = mode


def render_mode_selector():
    """
    Render mode selector in sidebar with visual badge.

    This should be called at the top of each dashboard page.
    """
    # Initialize session state if not set
    if "system_mode" not in st.session_state:
        st.session_state.system_mode = "live"

    current_mode = st.session_state.system_mode
    config = MODE_CONFIG.get(current_mode, MODE_CONFIG["live"])

    # Add mode badge to sidebar
    st.sidebar.markdown(
        f"""
        <div style="
            display: flex;
            align-items: center;
            padding: 0.5rem 0.75rem;
            background: {config['color']}15;
            border: 1px solid {config['color']}40;
            border-radius: 8px;
            margin-bottom: 1rem;
        ">
            <span style="font-size: 1.2rem; margin-right: 0.5rem;">{config['icon']}</span>
            <div>
                <div style="font-weight: 600; color: {config['color']};">
                    {config['label']} Mode
                </div>
                <div style="font-size: 0.75rem; color: #666;">
                    {config['description']}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mode selector dropdown
    st.sidebar.markdown("### System Mode")

    mode_options = list(DB_MAP.keys())
    mode_labels = [f"{MODE_CONFIG[m]['icon']} {MODE_CONFIG[m]['label']}" for m in mode_options]

    current_index = mode_options.index(current_mode) if current_mode in mode_options else 0

    selected_label = st.sidebar.selectbox(
        "Select Mode",
        options=mode_labels,
        index=current_index,
        key="mode_selector",
        label_visibility="collapsed",
    )

    # Extract mode from selected label
    selected_index = mode_labels.index(selected_label)
    selected_mode = mode_options[selected_index]

    # Handle mode change
    if selected_mode != current_mode:
        st.session_state.system_mode = selected_mode
        st.rerun()

    st.sidebar.divider()


def render_mode_badge():
    """
    Render a compact mode badge (for use in page headers).

    Returns:
        HTML string for the badge
    """
    mode = get_current_mode()
    config = MODE_CONFIG.get(mode, MODE_CONFIG["live"])

    return f"""
    <span style="
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.5rem;
        background: {config['color']}20;
        border: 1px solid {config['color']}40;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        color: {config['color']};
        margin-left: 0.5rem;
    ">
        {config['icon']} {config['label']}
    </span>
    """
