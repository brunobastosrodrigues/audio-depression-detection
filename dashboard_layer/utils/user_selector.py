"""
Centralized user selection utility for consistent behavior across all dashboard pages.

This module provides functions to load users and render a user selector that properly
maintains the selected user across page navigation using Streamlit session state.
"""

import sys
import streamlit as st
from utils.database import get_database

# Session state key for user selection - used across all dashboard pages
USER_ID_KEY = "user_id"


def load_users():
    """
    Load all available users from the database.
    
    Returns:
        list: Sorted list of unique user IDs
    """
    db = get_database()
    users = set()
    for col_name in ["raw_metrics", "indicator_scores", "analyzed_metrics"]:
        try:
            users.update(db[col_name].distinct("user_id"))
        except Exception as e:
            # Log the error but continue - some collections may not exist yet
            # This is expected during initial setup or when collections are empty
            print(f"Warning: Could not load users from {col_name}: {e}", file=sys.stderr)
    return sorted(list(users))


def render_user_selector(sidebar=True, label="Select User"):
    """
    Render a user selector that maintains selection across page navigation.
    
    This function ensures that the selected user persists when navigating between
    pages by properly initializing the selectbox index from session state.
    
    Args:
        sidebar: If True, render in sidebar. If False, render in main area.
        label: Label for the selectbox
        
    Returns:
        str or None: Selected user ID, or None if no users available
    """
    users = load_users()
    
    if not users:
        if sidebar:
            st.sidebar.warning("No users found")
        else:
            st.warning("No users found")
        return None
    
    # Initialize session state for user_id if not set
    if USER_ID_KEY not in st.session_state:
        st.session_state[USER_ID_KEY] = users[0]
    
    # Determine the index for the selectbox
    # If the current session state value is in the users list, use its index
    # Otherwise, default to the first user
    current_user = st.session_state[USER_ID_KEY]
    if current_user in users:
        default_index = users.index(current_user)
    else:
        # Current user not in list (e.g., after mode change), default to first
        default_index = 0
        st.session_state[USER_ID_KEY] = users[0]
    
    # Render the selectbox
    if sidebar:
        st.sidebar.subheader(label)
        selected_user = st.sidebar.selectbox(
            "User", 
            users, 
            index=default_index,
            key=USER_ID_KEY
        )
    else:
        selected_user = st.selectbox(
            label, 
            users, 
            index=default_index,
            key=USER_ID_KEY
        )
    
    return selected_user
