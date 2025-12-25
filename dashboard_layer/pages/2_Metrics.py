import streamlit as st
from pymongo import MongoClient
import pandas as pd
from utils.refresh_procedure import refresh_procedure

st.title("Metrics")

client = MongoClient("mongodb://mongodb:27017")
db = client["iotsensing"]
collection_raw_metrics = db["raw_metrics"]

collections = {
    "Raw Metrics": "raw_metrics",
    "Aggregated Metrics": "aggregated_metrics",
    "Contextual Metrics": "contextual_metrics",
    "Analyzed Metrics": "analyzed_metrics",
}


@st.cache_data
def load_users():
    df = pd.DataFrame(collection_raw_metrics.find())
    return df["user_id"].unique()


st.sidebar.title("Actions")

if st.sidebar.button("🔄 Refresh Analysis"):
    refresh_procedure()

st.sidebar.subheader("Select User")
selected_user = st.sidebar.selectbox("User", load_users(), key="user_id")

st.markdown(
    "This view shows the collected metrics through three different stages of the analysis process.  \n"
    "**Raw metrics:** Collected directly from the sensors.  \n"
    "**Aggregated metrics:** Daily averages computed per metric.  \n"
    "**Contextual metrics:** Daily averages in temporal context per metric. or processed metrics that consider baseline and variability."
)

selected_view = st.radio("Select:", list(collections.keys()), horizontal=True)

collection_name = collections[selected_view]
collection = db[collection_name]
docs = list(collection.find({"user_id": selected_user}))

st.header(selected_view)

if not docs:
    st.info(f"No {selected_view.lower()} found for this user.")
else:
    df = pd.DataFrame(docs)

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        if collection_name == "raw_metrics":
            chart_data = df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="metric_value",
            )
        if collection_name == "aggregated_metrics":
            chart_data = df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="aggregated_value",
            )
        if collection_name == "contextual_metrics":
            chart_data = df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="contextual_value",
            )
        if collection_name == "analyzed_metrics":
            chart_data = df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="analyzed_value",
            )

        available_metrics = list(chart_data.columns)
        selected_metrics = st.multiselect(
            "Select:",
            options=available_metrics,
            default=available_metrics,
        )

        if selected_metrics:
            # Prepare display dataframe (pivoted)
            display_df = chart_data[selected_metrics].sort_index(ascending=False).reset_index()
            
            # Sanitize data: Replace Infinite values with NaN
            display_df = display_df.replace([float('inf'), float('-inf')], None)

            # Clean column names for display (optional, but metric names usually technical)
            clean_names = {col: col.replace("_", " ").title() for col in selected_metrics}

            # --- LATEST STATUS ---
            st.subheader("Latest Status")
            if not display_df.empty:
                latest_row = display_df.iloc[0]
                prev_row = display_df.iloc[1] if len(display_df) > 1 else None
                
                cols_per_row = 4
                metric_cols = st.columns(cols_per_row)
                
                for i, metric in enumerate(selected_metrics):
                    col_index = i % cols_per_row
                    if i > 0 and col_index == 0:
                        metric_cols = st.columns(cols_per_row)
                    
                    current_val = latest_row[metric]
                    
                    if pd.isna(current_val):
                        display_val = "N/A"
                        delta_str = None
                    else:
                        display_val = f"{current_val:.2f}"
                        if prev_row is not None and not pd.isna(prev_row[metric]):
                            delta_val = current_val - prev_row[metric]
                            delta_str = f"{delta_val:.2f}"
                        else:
                            delta_str = None
                    
                    with metric_cols[col_index]:
                        st.metric(
                            label=clean_names[metric],
                            value=display_val,
                            delta=delta_str,
                            help=f"Metric: {metric}"
                        )

            st.divider()

            # --- VISUALIZATION ---
            st.subheader("Trends")
            st.line_chart(display_df.set_index("timestamp")[selected_metrics])

            # --- DETAILED DATA ---
            st.subheader("Detailed Data")
            
            column_config = {
                "timestamp": st.column_config.DatetimeColumn(
                    "Timestamp",
                    format="D MMM YYYY, HH:mm",
                )
            }

            for metric in selected_metrics:
                # Determine dynamic min/max for the progress bar
                series_max = display_df[metric].max()
                series_min = display_df[metric].min()
                
                if pd.isna(series_max):
                    max_val = 1.0
                    min_val = 0.0
                else:
                    max_val = float(series_max)
                    min_val = float(series_min)
                
                # Add buffer
                safe_max = max_val + (abs(max_val) * 0.1) if max_val != 0 else 1.0
                safe_min = min_val - (abs(min_val) * 0.1)
                
                # Ensure min < max
                if safe_min >= safe_max:
                    safe_max = safe_min + 1.0

                column_config[metric] = st.column_config.ProgressColumn(
                    label=clean_names[metric],
                    format="%.2f",
                    min_value=safe_min,
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
                stats_df = display_df[selected_metrics].describe().T
                stats_df = stats_df[["mean", "std", "min", "max"]]
                stats_df.index = [clean_names.get(idx, idx) for idx in stats_df.index]
                st.dataframe(stats_df.style.format("{:.2f}"))
        else:
             st.info("Please select at least one metric to display.")
