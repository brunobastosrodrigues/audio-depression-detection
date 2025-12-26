"""
Board Configuration page.
Manage IoT boards (ReSpeaker) and environments.
"""

import streamlit as st
from pymongo import MongoClient
import pandas as pd
import requests
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="Boards", page_icon="📡", layout="wide")

st.title("📡 Board Configuration")
st.markdown("Manage IoT boards (ReSpeaker) and environments for audio capture.")

# --- DATABASE CONNECTION ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
client = MongoClient(MONGO_URI)
db = client["iotsensing"]
boards_collection = db["boards"]
environments_collection = db["environments"]
raw_metrics_collection = db["raw_metrics"]

ANALYSIS_LAYER_URL = "http://analysis_layer:8083"


@st.cache_data
def load_users():
    users = set()
    for col_name in ["raw_metrics", "boards"]:
        try:
            users.update(db[col_name].distinct("user_id"))
        except Exception:
            pass
    if not users:
        users.add(1)  # Default user
    return sorted(list(users))


# --- SIDEBAR ---
st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.subheader("Select User")
users = load_users()
selected_user = st.sidebar.selectbox("User", users, key="user_id")

st.divider()

# ============================================================================
# ENVIRONMENTS SECTION
# ============================================================================
st.header("Environments")
st.markdown("Environments represent physical locations where boards are placed (e.g., Living Room, Bedroom).")

environments = list(environments_collection.find({"user_id": selected_user}))

if environments:
    env_data = []
    for e in environments:
        created = e.get("created_at")
        if created and isinstance(created, datetime):
            created_str = created.strftime("%Y-%m-%d %H:%M")
        else:
            created_str = "-"

        env_data.append({
            "ID": str(e.get("environment_id", ""))[:8] + "...",
            "Name": e.get("name", ""),
            "Description": e.get("description", "") or "-",
            "Created": created_str,
        })
    st.dataframe(pd.DataFrame(env_data), use_container_width=True, hide_index=True)
else:
    st.info("No environments configured. Add one below.")

with st.expander("➕ Add Environment", expanded=len(environments) == 0):
    with st.form("add_environment"):
        env_name = st.text_input("Name", placeholder="e.g., Living Room")
        env_description = st.text_area("Description (optional)")
        submitted = st.form_submit_button("Add Environment", type="primary")
        if submitted and env_name:
            try:
                response = requests.post(
                    f"{ANALYSIS_LAYER_URL}/environments/",
                    json={
                        "user_id": selected_user,
                        "name": env_name,
                        "description": env_description or None,
                    },
                    timeout=10,
                )
                if response.status_code == 200:
                    st.success(f"Environment '{env_name}' added!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Failed: {response.text}")
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error: {e}")

# Environment management
if environments:
    with st.expander("✏️ Manage Environments"):
        for env in environments:
            st.markdown(f"**{env['name']}**")
            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                new_name = st.text_input(
                    "Name",
                    value=env["name"],
                    key=f"env_name_{env['environment_id']}",
                    label_visibility="collapsed",
                )

            with col2:
                new_desc = st.text_input(
                    "Description",
                    value=env.get("description") or "",
                    key=f"env_desc_{env['environment_id']}",
                    label_visibility="collapsed",
                    placeholder="Description",
                )

            with col3:
                col_update, col_delete = st.columns(2)
                with col_update:
                    if st.button("💾", key=f"env_update_{env['environment_id']}", help="Save"):
                        try:
                            response = requests.put(
                                f"{ANALYSIS_LAYER_URL}/environments/{env['environment_id']}",
                                json={"name": new_name, "description": new_desc or None},
                                timeout=10,
                            )
                            if response.status_code == 200:
                                st.success("Updated!")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"Failed: {response.text}")
                        except requests.exceptions.RequestException as e:
                            st.error(f"Error: {e}")

                with col_delete:
                    if st.button("🗑️", key=f"env_delete_{env['environment_id']}", help="Delete"):
                        try:
                            response = requests.delete(
                                f"{ANALYSIS_LAYER_URL}/environments/{env['environment_id']}",
                                timeout=10,
                            )
                            if response.status_code == 200:
                                st.success("Deleted!")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"Failed: {response.text}")
                        except requests.exceptions.RequestException as e:
                            st.error(f"Error: {e}")

            st.markdown("---")

st.divider()

# ============================================================================
# BOARDS SECTION
# ============================================================================
st.header("Boards")
st.markdown("Boards are IoT devices (e.g., ReSpeaker) that capture and stream audio data.")

boards = list(boards_collection.find({"user_id": selected_user}))

# Build environment lookup
env_lookup = {e["environment_id"]: e["name"] for e in environments}
env_options = {e["name"]: e["environment_id"] for e in environments}

if boards:
    board_data = []
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)

    for b in boards:
        is_active = b.get("is_active", False)
        board_id = b.get("board_id")

        has_recent_data = raw_metrics_collection.find_one({
            "board_id": board_id,
            "timestamp": {"$gte": five_mins_ago}
        }) is not None

        last_seen = b.get("last_seen")
        if last_seen and isinstance(last_seen, datetime):
            last_seen_str = last_seen
        else:
            last_seen_str = None

        board_data.append({
            "board_id": board_id,
            "Status": "🟢 Active" if is_active else "⚪ Inactive",
            "Data": "📡 Streaming" if has_recent_data else "💤 Idle",
            "Name": b.get("name", ""),
            "MAC": b.get("mac_address", ""),
            "Environment": env_lookup.get(b.get("environment_id", ""), "Unknown"),
            "Last Seen": last_seen_str,
        })

    df_boards = pd.DataFrame(board_data)

    st.dataframe(
        df_boards,
        column_config={
            "board_id": None,
            "Last Seen": st.column_config.DatetimeColumn(
                "Last Seen",
                format="D MMM YYYY, HH:mm:ss",
            ),
        },
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "**Status:** TCP connection to server | **Data:** Audio processed in last 5 minutes"
    )

else:
    st.info("No boards configured. Boards auto-register when they connect, or add one manually below.")

with st.expander("➕ Add Board Manually"):
    if not environments:
        st.warning("Please add an environment first before adding a board.")
    else:
        with st.form("add_board"):
            board_name = st.text_input("Name", placeholder="e.g., Kitchen Mic")
            mac_address = st.text_input("MAC Address", placeholder="AA:BB:CC:DD:EE:FF")
            selected_env = st.selectbox("Environment", list(env_options.keys()))
            submitted = st.form_submit_button("Add Board", type="primary")
            if submitted and board_name and mac_address:
                try:
                    response = requests.post(
                        f"{ANALYSIS_LAYER_URL}/boards/",
                        json={
                            "user_id": selected_user,
                            "name": board_name,
                            "mac_address": mac_address.upper(),
                            "environment_id": env_options.get(selected_env, "default"),
                        },
                        timeout=10,
                    )
                    if response.status_code == 200:
                        st.success(f"Board '{board_name}' added!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Failed: {response.text}")
                except requests.exceptions.RequestException as e:
                    st.error(f"Connection error: {e}")

# Board management
if boards:
    with st.expander("✏️ Manage Boards"):
        for board in boards:
            status_icon = "🟢" if board.get("is_active") else "⚪"
            st.markdown(f"**{status_icon} {board['name']}** ({board['mac_address']})")

            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                new_name = st.text_input(
                    "Name",
                    value=board["name"],
                    key=f"board_name_{board['board_id']}",
                    label_visibility="collapsed",
                )

            with col2:
                if env_options:
                    current_env_name = env_lookup.get(board.get("environment_id", ""), "")
                    env_names = list(env_options.keys())
                    current_idx = env_names.index(current_env_name) if current_env_name in env_names else 0
                    new_env = st.selectbox(
                        "Environment",
                        env_names,
                        index=current_idx,
                        key=f"board_env_{board['board_id']}",
                        label_visibility="collapsed",
                    )
                else:
                    new_env = None

            with col3:
                col_update, col_delete = st.columns(2)
                with col_update:
                    if st.button("💾", key=f"board_update_{board['board_id']}", help="Save"):
                        try:
                            update_data = {"name": new_name}
                            if new_env and env_options:
                                update_data["environment_id"] = env_options[new_env]
                            response = requests.put(
                                f"{ANALYSIS_LAYER_URL}/boards/{board['board_id']}",
                                json=update_data,
                                timeout=10,
                            )
                            if response.status_code == 200:
                                st.success("Updated!")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"Failed: {response.text}")
                        except requests.exceptions.RequestException as e:
                            st.error(f"Error: {e}")

                with col_delete:
                    if st.button("🗑️", key=f"board_delete_{board['board_id']}", help="Delete"):
                        try:
                            response = requests.delete(
                                f"{ANALYSIS_LAYER_URL}/boards/{board['board_id']}",
                                timeout=10,
                            )
                            if response.status_code == 200:
                                st.success("Deleted!")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"Failed: {response.text}")
                        except requests.exceptions.RequestException as e:
                            st.error(f"Error: {e}")

            st.caption(f"Board ID: {board['board_id']} | Port: {board.get('port', 'N/A')}")
            st.markdown("---")
