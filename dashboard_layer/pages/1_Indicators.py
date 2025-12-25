import streamlit as st
from pymongo import MongoClient
import pandas as pd
import plotly.graph_objects as go

from utils.refresh_procedure import refresh_procedure
from utils.SunburstAdapter import SunburstAdapter

st.title("DSM-5 Indicators")

client = MongoClient("mongodb://mongodb:27017")
db = client["iotsensing"]
collection = db["indicator_scores"]
collection_metrics = db["analyzed_metrics"]

if collection.count_documents({}) == 0:
    st.warning("No data available.")
    st.stop()


@st.cache_data
def load_users():
    df = pd.DataFrame(collection.find())
    return df["user_id"].unique()


st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()

st.sidebar.subheader("Select User")
selected_user = st.sidebar.selectbox("User", load_users(), key="user_id")

df = pd.DataFrame(collection.find())
df["timestamp"] = pd.to_datetime(df["timestamp"])

selected_user = st.session_state.get("user_id", None)

if selected_user:
    user_df = df[df["user_id"] == selected_user]

    if user_df.empty:
        st.info("No DSM-5 indicator scores available for this user.")
        st.stop()

    indicators_df = user_df[["timestamp", "indicator_scores"]].copy()
    indicators_df = pd.concat(
        [
            indicators_df.drop(columns=["indicator_scores"]),
            indicators_df["indicator_scores"].apply(pd.Series),
        ],
        axis=1,
    )

    indicators = sorted([col for col in indicators_df.columns if col != "timestamp"])

    selected_indicators = st.multiselect(
        "Select:",
        options=indicators,
        default=indicators,
    )

    if selected_indicators:
        # --- PREPARE DATA ---
        # Sort by timestamp descending
        display_df = indicators_df[["timestamp"] + selected_indicators].sort_values(
            "timestamp", ascending=False
        )
        
        # Clean column names for better readability
        clean_names = {col: col.replace("_", " ").title() for col in selected_indicators}

        # Sanitize data: Replace Infinite values with NaN to avoid JSON errors
        display_df = display_df.replace([float('inf'), float('-inf')], None)

        # --- LATEST STATUS ---
        st.subheader("Latest Status")
        if not display_df.empty:
            latest_row = display_df.iloc[0]
            prev_row = display_df.iloc[1] if len(display_df) > 1 else None
            
            # Create a grid layout for metrics
            cols_per_row = 4
            metric_cols = st.columns(cols_per_row)
            
            for i, indicator in enumerate(selected_indicators):
                col_index = i % cols_per_row
                
                # Check if we need a new row of columns (when wrapping)
                if i > 0 and col_index == 0:
                    metric_cols = st.columns(cols_per_row)
                
                current_val = latest_row[indicator]
                
                # Handle potential NaN in current_val
                if pd.isna(current_val):
                    display_val = "N/A"
                    delta_str = None
                else:
                    display_val = f"{current_val:.2f}"
                    
                    if prev_row is not None and not pd.isna(prev_row[indicator]):
                        delta_val = current_val - prev_row[indicator]
                        delta_str = f"{delta_val:.2f}"
                    else:
                        delta_str = None
                
                with metric_cols[col_index]:
                    st.metric(
                        label=clean_names[indicator],
                        value=display_val,
                        delta=delta_str,
                        delta_color="inverse",  # Assuming higher is worse (depression indicators)
                        help=f"Original key: {indicator}"
                    )

        st.divider()

        # --- SUNBURST VISUALIZATION ---
        st.subheader("Clinical Status Hierarchy")

        # Get the latest Indicator Record
        latest_ind_doc = collection.find_one(
            {"user_id": selected_user},
            sort=[("timestamp", -1)]
        )

        if latest_ind_doc:
            # Get the corresponding Metric Records (matching timestamp)
            timestamp = latest_ind_doc["timestamp"]

            metric_cursor = collection_metrics.find({
                "user_id": selected_user,
                "timestamp": timestamp
            })
            metric_records = list(metric_cursor)

            # Process with Adapter
            try:
                adapter = SunburstAdapter("/app/core/mapping/config.json")
                plot_data = adapter.process(latest_ind_doc, metric_records)

                # Render Chart
                fig = go.Figure(go.Sunburst(
                    ids=plot_data['ids'],
                    labels=plot_data['labels'],
                    parents=plot_data['parents'],
                    values=plot_data['values'],
                    marker=dict(colors=plot_data['colors']),
                    branchvalues="total",
                    hovertemplate='<b>%{label}</b><br>Impact: %{value:.2f}<extra></extra>'
                ))

                fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=500)
                st.plotly_chart(fig, use_container_width=True)

            except FileNotFoundError:
                st.error("Config file not found. Please check 'core/mapping/config.json' path.")
            except Exception as e:
                st.error(f"Error generating hierarchy: {e}")

        st.divider()

        # --- VISUALIZATION ---
        st.subheader("Trends")
        st.line_chart(display_df.set_index("timestamp")[selected_indicators])

        # --- DETAILED DATA ---
        st.subheader("Detailed Data")
        
        # Configure columns for the dataframe
        column_config = {
            "timestamp": st.column_config.DatetimeColumn(
                "Timestamp",
                format="D MMM YYYY, HH:mm",
            )
        }

        for indicator in selected_indicators:
            # Determine dynamic max for the progress bar to avoid clipping
            # Handle cases where column might be all NaNs
            series_max = display_df[indicator].max()
            
            if pd.isna(series_max):
                 max_val = 1.0
            else:
                 max_val = float(series_max)
            
            safe_max = max(max_val, 1.0) * 1.2  # Add buffer
            
            column_config[indicator] = st.column_config.ProgressColumn(
                label=clean_names[indicator],
                format="%.2f",
                min_value=0,
                max_value=safe_max,
            )

        st.dataframe(
            display_df,
            column_config=column_config,
            use_container_width=True,
            hide_index=True
        )

        # --- STATISTICS ---
        with st.expander("View Summary Statistics"):
            stats_df = display_df[selected_indicators].describe().T
            stats_df = stats_df[["mean", "std", "min", "max"]]
            stats_df.index = [clean_names.get(idx, idx) for idx in stats_df.index]
            st.dataframe(stats_df.style.format("{:.2f}"))

    else:
        st.info("Please select at least one indicator to display.")
else:
    st.warning("Please select a user in the Home tab.")
