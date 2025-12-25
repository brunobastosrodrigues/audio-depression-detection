import streamlit as st
from pymongo import MongoClient
import pandas as pd
import requests
from datetime import datetime

st.title("Board Configuration")

client = MongoClient("mongodb://mongodb:27017")
db = client["iotsensing"]
boards_collection = db["boards"]
environments_collection = db["environments"]
raw_metrics_collection = db["raw_metrics"]

ANALYSIS_LAYER_URL = "http://analysis_layer:8083"

# Sidebar: User selection
st.sidebar.title("Actions")

# Try to get users from existing data
@st.cache_data
def load_users():
    # Try raw_metrics first
    if raw_metrics_collection.count_documents({}) > 0:
        df = pd.DataFrame(raw_metrics_collection.find())
        return sorted(df["user_id"].unique().tolist())
    # Fall back to boards collection
    if boards_collection.count_documents({}) > 0:
        df = pd.DataFrame(boards_collection.find())
        return sorted(df["user_id"].unique().tolist())
    return [1]  # Default user


users = load_users()
st.sidebar.subheader("Select User")
selected_user = st.sidebar.selectbox("User", users, key="user_id")

if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ----- Environments Section -----
st.header("Environments")

environments = list(environments_collection.find({"user_id": selected_user}))

if environments:
    env_data = []
    for e in environments:
        env_data.append({
            "ID": e.get("environment_id", "")[:8] + "...",
            "Name": e.get("name", ""),
            "Description": e.get("description", "") or "-",
            "Created": e.get("created_at", "").strftime("%Y-%m-%d %H:%M") if e.get("created_at") else "-",
        })
    st.dataframe(pd.DataFrame(env_data), use_container_width=True)
else:
    st.info("No environments configured. Add one below.")

with st.expander("Add Environment", expanded=len(environments) == 0):
    with st.form("add_environment"):
        env_name = st.text_input("Name", placeholder="e.g., Living Room")
        env_description = st.text_area("Description (optional)")
        submitted = st.form_submit_button("Add Environment")
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
    st.subheader("Manage Environments")
    for env in environments:
        with st.expander(f"{env['name']}"):
            col1, col2 = st.columns([3, 1])
            with col1:
                new_name = st.text_input(
                    "Name",
                    value=env["name"],
                    key=f"env_name_{env['environment_id']}",
                )
                new_desc = st.text_area(
                    "Description",
                    value=env.get("description") or "",
                    key=f"env_desc_{env['environment_id']}",
                )
            with col2:
                st.write("")  # Spacer
                st.write("")
                if st.button("Update", key=f"env_update_{env['environment_id']}"):
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

                if st.button("Delete", key=f"env_delete_{env['environment_id']}", type="secondary"):
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

st.divider()

# ----- Boards Section -----
st.header("Boards")

boards = list(boards_collection.find({"user_id": selected_user}))

# Build environment lookup
env_lookup = {e["environment_id"]: e["name"] for e in environments}
env_options = {e["name"]: e["environment_id"] for e in environments}

if boards:
    board_data = []
    for b in boards:
        status = "Active" if b.get("is_active") else "Inactive"
        last_seen = b.get("last_seen")
        if last_seen:
            if isinstance(last_seen, datetime):
                last_seen_str = last_seen.strftime("%Y-%m-%d %H:%M")
            else:
                last_seen_str = str(last_seen)
        else:
            last_seen_str = "Never"

        board_data.append({
            "Status": status,
            "Name": b.get("name", ""),
            "MAC Address": b.get("mac_address", ""),
            "Environment": env_lookup.get(b.get("environment_id", ""), "Unknown"),
            "Port": b.get("port", 0) or "-",
            "Last Seen": last_seen_str,
        })

    st.dataframe(pd.DataFrame(board_data), use_container_width=True)
else:
    st.info("No boards configured. Boards will auto-register when they connect, or add one manually below.")

with st.expander("Add Board Manually"):
    if not environments:
        st.warning("Please add an environment first before adding a board.")
    else:
        with st.form("add_board"):
            board_name = st.text_input("Name", placeholder="e.g., Kitchen Mic")
            mac_address = st.text_input("MAC Address", placeholder="AA:BB:CC:DD:EE:FF")
            selected_env = st.selectbox("Environment", list(env_options.keys()))
            submitted = st.form_submit_button("Add Board")
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
    st.subheader("Manage Boards")
    for board in boards:
        status_icon = "" if board.get("is_active") else ""
        with st.expander(f"{status_icon} {board['name']} ({board['mac_address']})"):
            col1, col2 = st.columns([3, 1])
            with col1:
                new_name = st.text_input(
                    "Name",
                    value=board["name"],
                    key=f"board_name_{board['board_id']}",
                )
                if env_options:
                    current_env_name = env_lookup.get(board.get("environment_id", ""), "")
                    env_names = list(env_options.keys())
                    current_idx = env_names.index(current_env_name) if current_env_name in env_names else 0
                    new_env = st.selectbox(
                        "Environment",
                        env_names,
                        index=current_idx,
                        key=f"board_env_{board['board_id']}",
                    )
                else:
                    new_env = None
                    st.warning("No environments available")

            with col2:
                st.write("")  # Spacer
                st.write("")
                if st.button("Update", key=f"board_update_{board['board_id']}"):
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

                if st.button("Delete", key=f"board_delete_{board['board_id']}", type="secondary"):
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

            # Show additional info
            st.caption(f"Board ID: {board['board_id']}")
            st.caption(f"Port: {board.get('port', 0) or 'Not assigned'}")
