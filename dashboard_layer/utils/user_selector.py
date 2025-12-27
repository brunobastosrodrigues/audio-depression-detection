"""
Centralized user selection utility for consistent behavior across all dashboard pages.

This module provides functions to load users and render a user selector that properly
maintains the selected user across page navigation using Streamlit session state.

User Loading Strategy by Mode:
- Live mode: Load from 'users' collection (registered/enrolled users only)
- Demo/Dataset mode: Load from data collections (raw_metrics, indicator_scores, etc.)
"""

import sys
import streamlit as st
from utils.database import get_database, get_current_mode

# Session state key for user selection
# This constant ensures consistent user selection persistence across all dashboard pages.
# All pages use this same key to share the selected user in st.session_state.
USER_ID_KEY = "user_id"


def load_users():
    """
    Load all available users from the database based on current mode.

    - Live mode: Returns registered users from 'users' collection
    - Demo/Dataset mode: Returns distinct user_ids from data collections

    Returns:
        list: List of dicts with 'user_id' and 'name' (live mode) or
              list of user_ids (demo/dataset mode)
    """
    db = get_database()
    mode = get_current_mode()

    if mode == "live":
        # In live mode, only show registered users from the users collection
        try:
            registered_users = list(db["users"].find(
                {"status": "active"},
                {"_id": 0, "user_id": 1, "name": 1}
            ))
            return registered_users
        except Exception as e:
            print(f"Warning: Could not load registered users: {e}", file=sys.stderr)
            return []
    else:
        # In demo/dataset mode, load from data collections
        users = set()
        for col_name in ["raw_metrics", "indicator_scores", "analyzed_metrics"]:
            try:
                users.update(db[col_name].distinct("user_id"))
            except Exception as e:
                print(f"Warning: Could not load users from {col_name}: {e}", file=sys.stderr)
        # Return as list of dicts for consistency
        return [{"user_id": uid, "name": str(uid)} for uid in sorted(users)]


def render_user_selector(sidebar=True, label="Select User"):
    """
    Render a user selector that maintains selection across page navigation.

    This function ensures that the selected user persists when navigating between
    pages by properly initializing the selectbox index from session state.

    In live mode, displays user names but returns user_ids.
    In demo/dataset mode, displays and returns user_ids.

    Args:
        sidebar: If True, render in sidebar. If False, render in main area.
        label: Label for the selectbox

    Returns:
        str or None: Selected user ID, or None if no users available
    """
    users = load_users()

    if not users:
        mode = get_current_mode()
        msg = "No registered users found. Go to User Management to register users." if mode == "live" else "No users found in data."
        if sidebar:
            st.sidebar.warning(msg)
        else:
            st.warning(msg)
        return None

    # Extract user_ids and create display labels
    user_ids = [u["user_id"] for u in users]
    user_labels = [f"{u.get('name', u['user_id'])}" for u in users]

    # Create mapping for display
    id_to_label = dict(zip(user_ids, user_labels))
    label_to_id = dict(zip(user_labels, user_ids))

    # Initialize session state for user_id if not set
    if USER_ID_KEY not in st.session_state:
        st.session_state[USER_ID_KEY] = user_ids[0]

    # Determine the index for the selectbox
    current_user_id = st.session_state[USER_ID_KEY]
    if current_user_id in user_ids:
        default_index = user_ids.index(current_user_id)
    else:
        # Current user not in list (e.g., after mode change), default to first
        default_index = 0
        st.session_state[USER_ID_KEY] = user_ids[0]

    # Render the selectbox with user names as labels
    if sidebar:
        st.sidebar.subheader(label)
        selected_label = st.sidebar.selectbox(
            label,
            user_labels,
            index=default_index,
            key="user_selector_label",  # Use separate key for the widget
            label_visibility="collapsed"
        )
    else:
        selected_label = st.selectbox(
            label,
            user_labels,
            index=default_index,
            key="user_selector_label"
        )

    # Convert label back to user_id
    selected_user_id = label_to_id.get(selected_label, user_ids[0])

    # Update session state with the actual user_id
    st.session_state[USER_ID_KEY] = selected_user_id

    return selected_user_id


def get_user_display_name(user_id: str) -> str:
    """
    Get the display name for a user ID.

    Args:
        user_id: The user's ID

    Returns:
        str: The user's name if found, otherwise the user_id itself
    """
    db = get_database()
    mode = get_current_mode()

    if mode == "live":
        try:
            user = db["users"].find_one(
                {"user_id": user_id},
                {"_id": 0, "name": 1}
            )
            if user and "name" in user:
                return user["name"]
        except Exception:
            pass

    return str(user_id)
