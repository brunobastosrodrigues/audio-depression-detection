"""
Board Configuration page.
Manage IoT boards (ReSpeaker) and environments.
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import os

from utils.database import get_database, render_mode_selector, get_current_mode

st.set_page_config(page_title="Boards", page_icon="📡", layout="wide")

# Mode Check
if get_current_mode() != "live":
    st.info("This page is only available in Live mode.")
    st.stop()

st.title("📡 Board Configuration")
st.markdown("Manage IoT boards (ReSpeaker) and environments for audio capture.")

# --- DATABASE CONNECTION ---
db = get_database()
boards_collection = db["boards"]
environments_collection = db["environments"]
raw_metrics_collection = db["raw_metrics"]

ANALYSIS_LAYER_URL = "http://analysis_layer:8083"


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
render_mode_selector()

st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

st.sidebar.subheader("Select User")
users = load_users()
selected_user = st.sidebar.selectbox("User", users, key="user_id")

st.divider()

# ============================================================================
# SYSTEM STATUS OVERVIEW
# ============================================================================
boards = list(boards_collection.find({"user_id": selected_user}))
five_mins_ago = datetime.utcnow() - timedelta(minutes=5)

if boards:
    st.header("🌐 System Status Overview")
    
    # Calculate global metrics
    total_boards = len(boards)
    active_boards = sum(1 for b in boards if b.get("is_active", False))
    
    # Count boards actually streaming data recently
    streaming_board_ids = raw_metrics_collection.distinct(
        "board_id", 
        {"user_id": selected_user, "timestamp": {"$gte": five_mins_ago}}
    )
    streaming_count = len(streaming_board_ids)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Boards", total_boards)
    col2.metric("Active Connections", f"{active_boards} / {total_boards}")
    col3.metric("Streaming Now", f"{streaming_count} Boards")

    # Multi-board Activity Chart
    st.markdown("##### Recent Activity (All Boards - Last 15m)")
    fifteen_mins_ago = datetime.utcnow() - timedelta(minutes=15)
    
    # Fetch recent counts for all boards
    pipeline = [
        {"$match": {"user_id": selected_user, "timestamp": {"$gte": fifteen_mins_ago}}},
        {"$group": {"_id": "$board_id", "count": {"$sum": 1}}}
    ]
    activity_data = list(raw_metrics_collection.aggregate(pipeline))
    
    if activity_data:
        # Map board_ids to names
        board_name_map = {b["board_id"]: b["name"] for b in boards}
        df_activity = pd.DataFrame([
            {"Board": board_name_map.get(d["_id"], d["_id"]), "Packets": d["count"]}
            for d in activity_data
        ])
        
        import plotly.express as px
        fig = px.bar(
            df_activity, 
            x="Board", 
            y="Packets", 
            color="Board",
            template="plotly_white",
            labels={"Packets": "Samples Captured"}
        )
        fig.update_layout(height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data packets received from any board in the last 15 minutes.")

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

    st.divider()

    # ============================================================================
    # LIVE MONITOR SECTION
    # ============================================================================
    st.header("🔍 Individual Board Verification")
    st.markdown("Select a specific board to verify its audio quality and manually inspect the stream.")

    # Select board for monitoring
    monitor_options = {f"{b['name']} ({b['mac_address']})": b for b in boards}
    selected_monitor_name = st.selectbox("Select Board to Monitor", list(monitor_options.keys()))
    
    if selected_monitor_name:
        selected_board = monitor_options[selected_monitor_name]
        monitor_board_id = selected_board["board_id"]
        
        # Determine topic
        # Logic matches ReSpeakerService: voice/{user_id}/{board_id}/{env_name}
        env_id = selected_board.get("environment_id", "")
        env_name_raw = env_lookup.get(env_id, "unknown")
        env_name_fmt = env_name_raw.lower().replace(" ", "_")
        mqtt_topic = f"voice/{selected_board['user_id']}/{monitor_board_id}/{env_name_fmt}"

        col_listen, col_info = st.columns([1, 2])
        
        with col_info:
            st.info(f"**Topic:** `{mqtt_topic}`")

        with col_listen:
            if st.button("🎤 Capture Recent Sample", type="primary", use_container_width=True):
                with st.spinner("Listening for audio stream (10s timeout)..."):
                    try:
                        import paho.mqtt.client as mqtt
                        import queue
                        import json
                        import base64
                        
                        # Helper to capture one message with timeout
                        def capture_single_message(topic, hostname="mqtt", port=1883, timeout=10):
                            q = queue.Queue()
                            
                            def on_message(client, userdata, msg):
                                q.put(msg)
                                
                            client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
                            client.on_message = on_message
                            client.connect(hostname, port, 60)
                            client.subscribe(topic)
                            client.loop_start()
                            
                            try:
                                msg = q.get(timeout=timeout)
                                return msg
                            except queue.Empty:
                                return None
                            finally:
                                client.loop_stop()
                                client.disconnect()

                        # Capture
                        msg = capture_single_message(mqtt_topic, hostname="mqtt", port=1883, timeout=10)
                        
                        if msg:
                            payload = json.loads(msg.payload.decode())
                            audio_b64 = payload.get("data")
                            timestamp = payload.get("timestamp")
                            
                            if audio_b64:
                                st.session_state["captured_audio"] = {
                                    "board_id": monitor_board_id,
                                    "audio": base64.b64decode(audio_b64),
                                    "timestamp": timestamp,
                                    "topic": mqtt_topic
                                }
                                st.rerun()
                            else:
                                st.error("Received payload but no audio data found.")
                        else:
                            st.warning("No data received. Is the board active?")
                            
                    except Exception as e:
                        st.error(f"Error capturing audio: {e}")

        # Display captured audio if exists and matches current selection
        if "captured_audio" in st.session_state:
            cap = st.session_state["captured_audio"]
            if cap["board_id"] == monitor_board_id:
                st.success(f"✅ Captured sample from {datetime.fromtimestamp(cap['timestamp']).strftime('%H:%M:%S')}")
                
                # Audio Player
                st.audio(cap["audio"], format="audio/wav", sample_rate=16000)
                
                # Discard Logic
                st.markdown("##### Actions")
                col_discard, col_keep = st.columns(2)
                
                with col_discard:
                    if st.button("🗑️ Discard Data", type="secondary", help="Delete metrics associated with this sample"):
                        try:
                            # Delete from raw_metrics where timestamp is within small window
                            # payload timestamp is float seconds.
                            ts = cap["timestamp"]
                            # Use a window of +/- 0.1s to be safe, or exact match if stored exactly
                            # In MongoDB timestamps might be stored as datetime or float.
                            # Checking simple_receiver or similar might reveal format, 
                            # but usually we can match closely.
                            
                            # Let's try exact float match first, then range if needed.
                            # Actually, raw_metrics usually stores datetime objects.
                            # We need to convert timestamp (float) to datetime.
                            ts_dt = datetime.utcfromtimestamp(ts)
                            
                            # Range query (1 second window to be safe)
                            window_start = ts_dt - timedelta(seconds=0.5)
                            window_end = ts_dt + timedelta(seconds=5.5) # The chunk is 5s long, metrics might be anywhere in that range
                            
                            result = raw_metrics_collection.delete_many({
                                "board_id": monitor_board_id,
                                "timestamp": {"$gte": window_start, "$lte": window_end}
                            })
                            
                            st.success(f"Discarded {result.deleted_count} metric records.")
                            del st.session_state["captured_audio"]
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error discarding data: {e}")

                with col_keep:
                    if st.button("💾 Keep & Clear", type="primary"):
                        del st.session_state["captured_audio"]
                        st.rerun()

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
            
            tab_settings, tab_analytics = st.tabs(["⚙️ Settings", "📊 Analytics"])

            # --- SETTINGS TAB ---
            with tab_settings:
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
            
            # --- ANALYTICS TAB ---
            with tab_analytics:
                st.caption("Activity over the last 24 hours")
                
                # Fetch recent metrics
                try:
                    last_24h = datetime.utcnow() - timedelta(hours=24)
                    
                    # We only need timestamps to count activity
                    cursor = raw_metrics_collection.find(
                        {
                            "board_id": board["board_id"],
                            "timestamp": {"$gte": last_24h}
                        },
                        {"timestamp": 1, "_id": 0}
                    )
                    
                    timestamps = [doc["timestamp"] for doc in cursor]
                    count = len(timestamps)
                    
                    col_metric, col_chart = st.columns([1, 3])
                    
                    with col_metric:
                        st.metric("Packets Processed", count)
                        
                        if count > 0:
                            # Estimate uptime based on 5s chunks
                            # 24h = 86400s. Max chunks = 17280
                            uptime_pct = min(100.0, (count * 5 / 86400) * 100)
                            st.metric("Est. Uptime (24h)", f"{uptime_pct:.1f}%")
                    
                    with col_chart:
                        if count > 0:
                            import plotly.express as px
                            
                            # Create hourly bins
                            df_activity = pd.DataFrame(timestamps, columns=["timestamp"])
                            df_activity["hour"] = df_activity["timestamp"].dt.floor("H")
                            hourly_counts = df_activity.groupby("hour").size().reset_index(name="count")
                            
                            fig = px.bar(
                                hourly_counts, 
                                x="hour", 
                                y="count",
                                title="Packets per Hour",
                                template="plotly_white"
                            )
                            fig.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20))
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No data received in the last 24 hours.")
                            
                except Exception as e:
                    st.error(f"Error loading analytics: {e}")

            st.markdown("---")
