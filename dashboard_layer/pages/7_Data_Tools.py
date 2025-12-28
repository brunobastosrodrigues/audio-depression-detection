"""
Data Tools page.
Provides debugging tools for audio loading, baseline viewing, data export,
and research validation (hypothesis testing, correlation analysis, classification metrics).
"""

import streamlit as st
import os
import sys
import threading
import time
import contextlib
import io
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.database import get_database, render_mode_selector, get_current_mode
from utils.user_selector import USER_ID_KEY
from utils.validation import (
    load_cohort_data,
    run_all_hypothesis_tests,
    calculate_classification_metrics,
    calculate_correlation_matrix,
    cohens_d,
    interpret_cohens_d,
    fdr_correction,
    DEFAULT_HYPOTHESES,
    PHQ8_TO_INDICATOR_MAPPING,
    HypothesisResult,
)

st.set_page_config(page_title="Data Tools", page_icon="🔧", layout="wide")

# Mode Check
if get_current_mode() != "dataset":
    st.info("This page is only available in Dataset mode.")
    st.stop()

st.title("🔧 Data Tools")
st.markdown("Debug tools for audio loading, baseline viewing, and data export.")

# --- DATABASE CONNECTION ---
db = get_database()

# Add data_ingestion_layer to path
DATA_INGESTION_PATH = "/app/data_ingestion_layer"
if os.path.exists(DATA_INGESTION_PATH):
    if DATA_INGESTION_PATH not in sys.path:
        sys.path.append(DATA_INGESTION_PATH)
else:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    ingestion_path = os.path.join(repo_root, "data_ingestion_layer")
    if os.path.exists(ingestion_path) and ingestion_path not in sys.path:
        sys.path.append(ingestion_path)
        DATA_INGESTION_PATH = ingestion_path

# Try importing VoiceFromFile
try:
    from implementations.VoiceFromFile import VoiceFromFile
    VOICE_FROM_FILE_AVAILABLE = True
except ImportError:
    VoiceFromFile = None
    VOICE_FROM_FILE_AVAILABLE = False


class StoppableVoiceFromFile:
    """Wrapper for VoiceFromFile with start/stop controls."""

    def __init__(self, filepath, topic="voice/mic1", mqtthostname="mqtt", mqttport=1883, user_id="test-user1"):
        if VoiceFromFile is None:
            raise ImportError("VoiceFromFile class is not available.")

        # Suppress output from torch.hub.load or other backend logs
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.device = VoiceFromFile(
                filepath=filepath,
                topic=topic,
                mqtthostname=mqtthostname,
                mqttport=mqttport,
                user_id=user_id,
                system_mode="dataset"
            )
        self.running = False
        self.thread = None
        self.error = None
        self.completed = False

    def _run_loop(self):
        try:
            while self.running:
                raw = self.device.collect()
                if raw is None:
                    self.completed = True
                    break
                filtered = self.device.filter(raw)
                if filtered is not None:
                    self.device.transport(filtered)
                time.sleep(0.01)
        except Exception as e:
            self.error = str(e)
        finally:
            self.running = False
            self.device.stop()

    def start(self):
        if self.running:
            return
        self.running = True
        self.completed = False
        self.error = None
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None


@st.cache_data
def load_users_data_tools():
    """
    Load users for Data Tools page (specific to dataset mode).
    Kept separate from user_selector to maintain caching.
    """
    db = get_database()
    users = set()
    for col_name in ["raw_metrics", "baseline", "indicator_scores"]:
        try:
            users.update(db[col_name].distinct("user_id"))
        except Exception as e:
            # Log the error but continue - some collections may not exist yet
            print(f"Warning: Could not load users from {col_name}: {e}", file=sys.stderr)
    users_list = sorted(list(users))
    if not users_list:
        return ["test-user1"]
    return users_list


# --- SIDEBAR ---
render_mode_selector()

st.sidebar.title("Data Tools")
st.sidebar.markdown("""
**Research Validation Mode**

The validation tabs use pre-loaded data from TESS audio samples.
No user selection required.
""")

st.sidebar.divider()

# Load users for tabs that need them (Audio Loader, Baseline, Export)
users = load_users_data_tools()

# Ensure a user is selected in session state
if USER_ID_KEY not in st.session_state:
    st.session_state[USER_ID_KEY] = users[0] if users else "test-user1"

# Get current user (used by Audio Loader, Baseline Viewer, Data Export tabs)
current_user = st.session_state[USER_ID_KEY]
if current_user not in users:
    st.session_state[USER_ID_KEY] = users[0] if users else "test-user1"
    current_user = st.session_state[USER_ID_KEY]

# Note: User selection is now done within individual tabs that need it
selected_user = current_user  # Default for tabs that use it

# --- TABS ---
tab_audio, tab_baseline, tab_export, tab_hypothesis, tab_correlation, tab_classification, tab_features = st.tabs([
    "🎵 Audio Loader",
    "📊 Baseline Viewer",
    "📥 Data Export",
    "🧪 Hypothesis Testing",
    "📈 PHQ-8 Correlation",
    "🎯 Classification",
    "📉 Feature Explorer"
])

# --- VALIDATION DATA PATHS ---
EVALUATION_DATA_DIR = Path("/app/docs/evaluation/hypothesis_testing_second_attempt")
if not EVALUATION_DATA_DIR.exists():
    # Try relative path from repo root
    repo_root = Path(__file__).parent.parent.parent.parent
    EVALUATION_DATA_DIR = repo_root / "docs" / "evaluation" / "hypothesis_testing_second_attempt"

DEPRESSED_JSON = EVALUATION_DATA_DIR / "depressed.json"
NONDEPRESSED_JSON = EVALUATION_DATA_DIR / "nondepressed.json"


@st.cache_data
def load_validation_data():
    """Load and cache the cohort data for validation."""
    if not DEPRESSED_JSON.exists() or not NONDEPRESSED_JSON.exists():
        return None, None
    return load_cohort_data(str(DEPRESSED_JSON), str(NONDEPRESSED_JSON))

# ============================================================================
# AUDIO LOADER TAB
# ============================================================================
with tab_audio:
    st.header("Audio Data Loader")
    st.markdown("Stream pre-recorded audio files into the system for testing and debugging.")

    # User selection for this tab
    col_user, col_spacer = st.columns([1, 2])
    with col_user:
        selected_user = st.selectbox(
            "Stream as User",
            users,
            index=users.index(current_user) if current_user in users else 0,
            key="audio_loader_user"
        )

    st.divider()

    if not VOICE_FROM_FILE_AVAILABLE:
        st.error("VoiceFromFile module is not available. This feature requires the data ingestion layer.")
        st.stop()

    # Dataset Directory
    DATASETS_DIR = "/app/datasets"
    if not os.path.exists(DATASETS_DIR):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        DATASETS_DIR = os.path.join(repo_root, "datasets")

    if not os.path.exists(DATASETS_DIR):
        st.warning(f"Datasets directory not found at {DATASETS_DIR}")
    else:
        try:
            files = [f for f in os.listdir(DATASETS_DIR) if f.endswith(".wav")]
        except Exception as e:
            st.error(f"Error reading datasets directory: {e}")
            files = []

        if not files:
            st.warning("No .wav files found in datasets directory.")
        else:
            # Select File
            default_index = 0
            if "long_depressed_sample_nobreak.wav" in files:
                default_index = files.index("long_depressed_sample_nobreak.wav")
            elif "performance_test.wav" in files:
                default_index = files.index("performance_test.wav")

            selected_file = st.selectbox("Select Audio File", files, index=default_index)
            filepath = os.path.join(DATASETS_DIR, selected_file)

            st.code(filepath, language=None)

            # Initialize session state for streamer
            if "streamer" not in st.session_state:
                st.session_state.streamer = None

            col1, col2, col3 = st.columns([1, 1, 2])
            
            # Check streaming state
            is_streaming = st.session_state.streamer is not None and st.session_state.streamer.running

            with col1:
                # Use a placeholder to ensure clean button rendering
                start_placeholder = st.empty()
                if start_placeholder.button(
                    "▶️ Start", 
                    type="primary", 
                    use_container_width=True, 
                    disabled=is_streaming,
                    key="start_stream_btn"
                ):
                    try:
                        mqtthost = os.getenv("MQTT_HOST", "mqtt")
                        st.session_state.streamer = StoppableVoiceFromFile(
                            filepath=filepath, 
                            mqtthostname=mqtthost,
                            user_id=selected_user
                        )
                        st.session_state.streamer.start()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to start: {e}")

            with col2:
                stop_placeholder = st.empty()
                if stop_placeholder.button(
                    "⏹️ Stop", 
                    use_container_width=True,
                    disabled=not is_streaming,
                    key="stop_stream_btn"
                ):
                    if st.session_state.streamer:
                        st.session_state.streamer.stop()
                        st.session_state.streamer = None
                        st.rerun()


            # Status Display
            if st.session_state.streamer:
                if st.session_state.streamer.running:
                    st.success(f"🔊 Streaming Active: {os.path.basename(filepath)}")
                    st.caption("ℹ️ Streaming runs in the background. You can navigate to other pages.")
                elif st.session_state.streamer.completed:
                    st.success("✅ Playback completed.")
                    # Optional: clean up the streamer object if you want to reset UI
                    # st.session_state.streamer = None
                elif st.session_state.streamer.error:
                    st.error(f"Error: {st.session_state.streamer.error}")
                    st.session_state.streamer = None

# ============================================================================
# BASELINE VIEWER TAB
# ============================================================================
with tab_baseline:
    st.header("Baseline Viewer")
    st.markdown("View baseline statistics computed for the selected user.")

    # User selection for this tab
    col_user, col_spacer = st.columns([1, 2])
    with col_user:
        baseline_user = st.selectbox(
            "Select User",
            users,
            index=users.index(current_user) if current_user in users else 0,
            key="baseline_viewer_user"
        )

    st.divider()

    if not baseline_user:
        st.warning("Please select a user.")
    else:
        selected_user = baseline_user  # Use for this tab
        collection_baseline = db["baseline"]
        baseline_docs = list(collection_baseline.find({"user_id": selected_user}).sort("timestamp", -1))

        if not baseline_docs:
            st.info("No baseline data found for this user.")
        else:
            st.success(f"Found {len(baseline_docs)} baseline records.")

            # Get latest baseline
            latest_baseline = baseline_docs[0]

            # Check schema version
            schema_version = latest_baseline.get("schema_version", 1)

            if schema_version == 2:
                # New schema with context partitions
                context_partitions = latest_baseline.get("context_partitions", {})

                context_options = list(context_partitions.keys())
                if context_options:
                    selected_context = st.selectbox("Context Partition", context_options)
                    baseline_data = context_partitions.get(selected_context, {})
                else:
                    baseline_data = {}
            else:
                # Old schema
                baseline_data = latest_baseline.get("baseline", {})

            if baseline_data:
                # Convert to DataFrame
                metrics = []
                for metric_name, stats in baseline_data.items():
                    if isinstance(stats, dict):
                        metrics.append({
                            "Metric": metric_name,
                            "Mean": stats.get("mean", 0),
                            "Std": stats.get("std", 0),
                            "Count": stats.get("count", 0),
                        })

                if metrics:
                    df_baseline = pd.DataFrame(metrics)

                    # Display table
                    st.dataframe(
                        df_baseline.style.format({"Mean": "{:.4f}", "Std": "{:.4f}"}),
                        use_container_width=True,
                        hide_index=True,
                    )

                    # Visualization
                    st.subheader("Baseline Means")
                    fig = px.bar(
                        df_baseline,
                        x="Metric",
                        y="Mean",
                        error_y="Std",
                        template="plotly_white",
                    )
                    fig.update_layout(height=400, xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)

            # Show baseline history
            with st.expander("📜 Baseline History"):
                history_data = []
                for doc in baseline_docs[:10]:
                    history_data.append({
                        "Timestamp": doc.get("timestamp"),
                        "Schema Version": doc.get("schema_version", 1),
                        "Metrics Count": len(doc.get("baseline", doc.get("context_partitions", {}))),
                    })

                st.dataframe(
                    pd.DataFrame(history_data),
                    use_container_width=True,
                    hide_index=True,
                )

# ============================================================================
# DATA EXPORT TAB
# ============================================================================
with tab_export:
    st.header("Data Export")
    st.markdown("Export data for external analysis.")

    # User selection for this tab
    col_user, col_spacer = st.columns([1, 2])
    with col_user:
        export_user = st.selectbox(
            "Select User",
            users,
            index=users.index(current_user) if current_user in users else 0,
            key="data_export_user"
        )

    st.divider()

    if not export_user:
        st.warning("Please select a user.")
    else:
        selected_user = export_user  # Use for this tab
        export_collection = st.selectbox(
            "Select Collection",
            ["raw_metrics", "aggregated_metrics", "contextual_metrics", "analyzed_metrics", "indicator_scores"],
        )

        # Count documents
        count = db[export_collection].count_documents({"user_id": selected_user})
        st.info(f"Found {count} documents for user '{selected_user}'.")

        if count > 0:
            limit = st.number_input("Limit (0 for all)", min_value=0, max_value=10000, value=1000)

            if st.button("📥 Export to CSV", type="primary"):
                with st.spinner("Exporting..."):
                    query = {"user_id": selected_user}
                    cursor = db[export_collection].find(query).sort("timestamp", -1)

                    if limit > 0:
                        cursor = cursor.limit(limit)

                    docs = list(cursor)

                    # Handle Grouped Metrics Unpacking for Export
                    if export_collection == "raw_metrics":
                        unpacked_docs = []
                        for doc in docs:
                            if "metrics" in doc and isinstance(doc["metrics"], dict):
                                # It's a grouped document, unpack it
                                base_info = {
                                    k: v for k, v in doc.items()
                                    if k not in ["metrics", "_id"]
                                }
                                for metric_name, metric_value in doc["metrics"].items():
                                    row = base_info.copy()
                                    row["metric_name"] = metric_name
                                    row["metric_value"] = metric_value
                                    unpacked_docs.append(row)
                            else:
                                # Legacy or already flat
                                unpacked_docs.append(doc)
                        docs = unpacked_docs

                    df = pd.DataFrame(docs)

                    # Remove MongoDB _id if it slipped through
                    if "_id" in df.columns:
                        df = df.drop(columns=["_id"])

                    # Convert to CSV
                    csv = df.to_csv(index=False)

                    st.download_button(
                        label="⬇️ Download CSV",
                        data=csv,
                        file_name=f"{selected_user}_{export_collection}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                    )

                    st.success(f"Exported {len(docs)} records.")

        # Database health check
        with st.expander("🔧 Database Health"):
            st.markdown("**Collection Statistics:**")

            stats = []
            for col_name in ["raw_metrics", "aggregated_metrics", "contextual_metrics", "analyzed_metrics", "indicator_scores", "baseline"]:
                try:
                    total = db[col_name].count_documents({})
                    user_count = db[col_name].count_documents({"user_id": selected_user})
                    stats.append({
                        "Collection": col_name,
                        "Total Documents": total,
                        "User Documents": user_count,
                    })
                except Exception:
                    stats.append({
                        "Collection": col_name,
                        "Total Documents": "Error",
                        "User Documents": "Error",
                    })

            st.dataframe(pd.DataFrame(stats), use_container_width=True, hide_index=True)

# ============================================================================
# HYPOTHESIS TESTING TAB
# ============================================================================
with tab_hypothesis:
    st.header("🧪 Hypothesis Testing")

    # --- DATA SOURCE EXPLANATION ---
    with st.expander("📖 About This Validation Data", expanded=True):
        st.markdown("""
        ### Data Source: TESS-Derived Audio Samples

        The validation data comes from **two pre-processed audio files** that were streamed
        through the IHearYou pipeline to extract acoustic features:

        | Audio File | Source | Description |
        |------------|--------|-------------|
        | `long_depressed_sample_nobreak.wav` | TESS Dataset (Sad emotion) | ~24 MB, concatenated sad speech samples |
        | `long_nondepressed_sample_nobreak.wav` | TESS Dataset (Happy emotion) | ~19 MB, concatenated happy speech samples |

        **How the data was generated:**
        1. Audio files from the [TESS (Toronto Emotional Speech Set)](https://tspace.library.utoronto.ca/handle/1807/24487) were grouped by emotion
        2. "Sad" emotion clips were concatenated to simulate depressive speech patterns
        3. "Happy" emotion clips were concatenated to simulate non-depressive speech patterns
        4. Each audio file was streamed through the IHearYou pipeline (via Audio Loader tab)
        5. The pipeline extracted acoustic features at regular intervals (time points)
        6. Results were exported to JSON files for reproducible validation

        **Important Limitations:**
        - ⚠️ This is **not clinical data** - TESS uses acted emotions, not diagnosed depression
        - ⚠️ Single speaker per cohort - limited generalizability
        - ⚠️ Emotion ≠ Depression - sadness is a proxy, not equivalent to MDD

        **Future: DAIC-WOZ Dataset**

        Once access is granted, this validation will be extended with the
        [DAIC-WOZ dataset](https://dcapswoz.ict.usc.edu/) which contains:
        - 189 clinical interview sessions
        - PHQ-8 depression scores (ground truth)
        - Balanced gender distribution
        - Real clinical assessments (not acted)
        """)

    st.divider()

    # --- METHODOLOGY EXPLANATION ---
    st.subheader("Methodology")
    st.markdown("""
    This tab performs **directional hypothesis testing** to validate whether acoustic features
    differ significantly between depressed and non-depressed speech samples.

    **Statistical Approach:**
    1. **Mann-Whitney U Test** - Non-parametric test comparing distributions (robust to non-normality)
    2. **Directional Hypotheses** - Tests are one-tailed based on depression literature predictions
    3. **FDR Correction** - Benjamini-Hochberg procedure controls false discovery rate across multiple tests
    4. **Effect Size (Cohen's d)** - Quantifies practical significance: |d| < 0.2 (negligible), 0.2-0.5 (small), 0.5-0.8 (medium), > 0.8 (large)
    """)

    st.divider()

    depressed_df, nondepressed_df = load_validation_data()

    if depressed_df is None or nondepressed_df is None:
        st.warning("Validation data not found. Please ensure the cohort JSON files exist.")
        st.code(f"Expected paths:\n- {DEPRESSED_JSON}\n- {NONDEPRESSED_JSON}")

        st.info("""
        **How to generate validation data:**
        1. Go to the **Audio Loader** tab
        2. Select `long_depressed_sample_nobreak.wav` and stream it
        3. Select `long_nondepressed_sample_nobreak.wav` and stream it
        4. Export the metrics from the **Data Export** tab
        5. Save as JSON files in the expected paths
        """)
    else:
        # Data summary
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Depressed Samples", f"{len(depressed_df)} time points",
                     help="From: long_depressed_sample_nobreak.wav (TESS Sad)")
        with col2:
            st.metric("Non-Depressed Samples", f"{len(nondepressed_df)} time points",
                     help="From: long_nondepressed_sample_nobreak.wav (TESS Happy)")

        # Get available features from both datasets
        common_features = set(depressed_df.columns) & set(nondepressed_df.columns)
        numeric_features = [f for f in common_features if depressed_df[f].dtype in ['float64', 'int64', 'float32', 'int32']]
        numeric_features = sorted(numeric_features)

        st.subheader("Configure Hypotheses")

        col1, col2 = st.columns([2, 1])

        with col1:
            # Filter hypotheses to those with available features
            available_hypotheses = [(f, d) for f, d in DEFAULT_HYPOTHESES if f in numeric_features]

            if available_hypotheses:
                st.info(f"Found **{len(available_hypotheses)}** testable hypotheses from default set.")
                use_defaults = st.checkbox("Use default hypotheses", value=True)
            else:
                use_defaults = False
                st.warning("No default hypotheses match available features. Select features manually.")

        with col2:
            alpha = st.slider("Significance Level (α)", 0.01, 0.10, 0.05, 0.01)

        if not use_defaults:
            # Manual feature selection
            selected_features = st.multiselect(
                "Select Features to Test",
                options=numeric_features,
                default=numeric_features[:10] if len(numeric_features) > 10 else numeric_features
            )
            # Default direction for manual selection
            hypotheses_to_test = [(f, "<") for f in selected_features]
        else:
            hypotheses_to_test = available_hypotheses

        if st.button("🔬 Run Hypothesis Tests", type="primary"):
            if not hypotheses_to_test:
                st.error("No hypotheses to test. Select features or ensure default hypotheses match available data.")
            else:
                with st.spinner("Running statistical tests..."):
                    results = run_all_hypothesis_tests(
                        depressed_df, nondepressed_df,
                        hypotheses_to_test, alpha
                    )

                if results:
                    st.subheader("Results Summary")

                    # Count significant results
                    significant_count = sum(1 for r in results if r.significant)
                    direction_correct_count = sum(1 for r in results if r.direction_correct)

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Tests Run", len(results))
                    with col2:
                        st.metric("Significant (FDR)", significant_count)
                    with col3:
                        st.metric("Direction Correct", f"{direction_correct_count}/{len(results)}")
                    with col4:
                        pct = (significant_count / len(results) * 100) if results else 0
                        st.metric("Discovery Rate", f"{pct:.1f}%")

                    st.divider()

                    # Detailed results table
                    st.subheader("Detailed Results")

                    results_data = []
                    for r in results:
                        results_data.append({
                            "Feature": r.feature,
                            "Direction": f"Dep {r.direction} NonDep",
                            "Dep Mean": f"{r.depressed_mean:.4f}" if not np.isnan(r.depressed_mean) else "N/A",
                            "NonDep Mean": f"{r.nondepressed_mean:.4f}" if not np.isnan(r.nondepressed_mean) else "N/A",
                            "Cohen's d": f"{r.cohens_d:.3f}" if not np.isnan(r.cohens_d) else "N/A",
                            "Effect Size": interpret_cohens_d(r.cohens_d) if not np.isnan(r.cohens_d) else "N/A",
                            "p-value": f"{r.p_value:.4f}" if r.p_value < 0.0001 else f"{r.p_value:.4f}",
                            "p (FDR)": f"{r.p_value_corrected:.4f}" if r.p_value_corrected else "N/A",
                            "Significant": "✅" if r.significant else "❌",
                            "Dir. Correct": "✅" if r.direction_correct else "❌",
                            "n (Dep)": r.n_depressed,
                            "n (NonDep)": r.n_nondepressed,
                        })

                    results_df = pd.DataFrame(results_data)
                    st.dataframe(results_df, use_container_width=True, hide_index=True)

                    # Effect size visualization
                    st.subheader("Effect Size Distribution")

                    effect_data = [
                        {"Feature": r.feature, "Cohen's d": r.cohens_d, "Significant": r.significant}
                        for r in results if not np.isnan(r.cohens_d)
                    ]
                    if effect_data:
                        effect_df = pd.DataFrame(effect_data)
                        effect_df = effect_df.sort_values("Cohen's d", ascending=True)

                        fig = px.bar(
                            effect_df,
                            x="Cohen's d",
                            y="Feature",
                            orientation="h",
                            color="Significant",
                            color_discrete_map={True: "#27AE60", False: "#E74C3C"},
                            template="plotly_white"
                        )
                        fig.add_vline(x=0.2, line_dash="dash", line_color="gray", annotation_text="Small")
                        fig.add_vline(x=0.5, line_dash="dash", line_color="gray", annotation_text="Medium")
                        fig.add_vline(x=0.8, line_dash="dash", line_color="gray", annotation_text="Large")
                        fig.add_vline(x=-0.2, line_dash="dash", line_color="gray")
                        fig.add_vline(x=-0.5, line_dash="dash", line_color="gray")
                        fig.add_vline(x=-0.8, line_dash="dash", line_color="gray")
                        fig.update_layout(height=max(400, len(effect_data) * 25))
                        st.plotly_chart(fig, use_container_width=True)

                    # Download results
                    csv = results_df.to_csv(index=False)
                    st.download_button(
                        "📥 Download Results CSV",
                        csv,
                        f"hypothesis_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        "text/csv"
                    )

# ============================================================================
# PHQ-8 CORRELATION TAB
# ============================================================================
with tab_correlation:
    st.header("📈 PHQ-8 Correlation Analysis")

    # --- EXPLANATION ---
    with st.expander("📖 About PHQ-8 Correlation Analysis", expanded=False):
        st.markdown("""
        ### Purpose

        This tab validates the **Linkage Framework** - the mapping between acoustic features
        and DSM-5 depression criteria. When PHQ-8 ground truth is available, we can measure
        how well each acoustic indicator correlates with its corresponding clinical symptom.

        ### PHQ-8 → DSM-5 Mapping

        | PHQ-8 Item | DSM-5 Indicator | Acoustic Markers |
        |------------|-----------------|------------------|
        | Q1: Little interest or pleasure | Loss of Interest | Reduced prosody, flat affect |
        | Q2: Feeling down, depressed | Depressed Mood | Lower F0, reduced variability |
        | Q3: Sleep problems | Sleep Disturbance | Fatigue markers, slower speech |
        | Q4: Feeling tired | Fatigue | Reduced energy, longer pauses |
        | Q5: Poor appetite or overeating | Weight Changes | (Not acoustically measurable) |
        | Q6: Feeling bad about yourself | Worthlessness | Hesitation, self-correction |
        | Q7: Trouble concentrating | Concentration | Speech disfluency, pausing |
        | Q8: Moving/speaking slowly | Psychomotor Changes | Rate of speech, articulation |

        ### Current Data Limitation

        ⚠️ **The current TESS-derived data does not include PHQ-8 scores.**

        PHQ-8 correlation analysis requires clinical ground truth labels, which will be
        available once the **DAIC-WOZ dataset** is integrated. For now, this tab shows
        feature-to-feature correlations within the combined cohort.
        """)

    st.divider()

    depressed_df, nondepressed_df = load_validation_data()

    if depressed_df is None:
        st.warning("Validation data not found.")
    else:
        # Combine datasets with labels
        dep_df_copy = depressed_df.copy()
        nondep_df_copy = nondepressed_df.copy()
        dep_df_copy["cohort"] = "depressed"
        nondep_df_copy["cohort"] = "nondepressed"
        combined_df = pd.concat([dep_df_copy, nondep_df_copy], ignore_index=True)

        # Check for PHQ-8 columns
        phq8_cols = [col for col in combined_df.columns if col.startswith("PHQ") or "phq" in col.lower()]

        if not phq8_cols:
            st.info("""
            **No PHQ-8 columns found in the current dataset.**

            The TESS-derived samples don't include clinical depression scores.
            Once DAIC-WOZ is integrated, you'll see correlations between acoustic features and PHQ-8 items.

            For now, we show **feature-to-feature correlations** to identify which acoustic markers co-vary.
            """)

            # Show feature-to-feature correlations
            numeric_cols = combined_df.select_dtypes(include=[np.number]).columns.tolist()
            numeric_cols = [c for c in numeric_cols if c not in ["_id"]]

            if len(numeric_cols) > 2:
                st.subheader("Feature Correlation Matrix")

                # Limit to top features for visualization
                if len(numeric_cols) > 20:
                    selected_cols = st.multiselect(
                        "Select Features (max 20)",
                        numeric_cols,
                        default=numeric_cols[:15]
                    )
                else:
                    selected_cols = numeric_cols

                if selected_cols:
                    corr_matrix = combined_df[selected_cols].corr(method='spearman')

                    fig = px.imshow(
                        corr_matrix,
                        text_auto=".2f",
                        color_continuous_scale="RdBu_r",
                        aspect="auto",
                        zmin=-1, zmax=1
                    )
                    fig.update_layout(height=max(500, len(selected_cols) * 25))
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.success(f"Found PHQ-8 columns: {phq8_cols}")

            # Get acoustic features
            acoustic_cols = [c for c in combined_df.columns
                           if c not in phq8_cols + ["cohort", "_id", "user_id", "timestamp"]
                           and combined_df[c].dtype in ['float64', 'int64', 'float32', 'int32']]

            st.subheader("Indicator → PHQ-8 Mapping Validation")

            # Display expected mapping
            with st.expander("Expected DSM-5 → PHQ-8 Mapping"):
                mapping_df = pd.DataFrame([
                    {"Indicator": k, "PHQ-8 Item": v}
                    for k, v in PHQ8_TO_INDICATOR_MAPPING.items()
                ])
                st.dataframe(mapping_df, use_container_width=True, hide_index=True)

            # Calculate correlation matrix
            if acoustic_cols and phq8_cols:
                st.subheader("Acoustic Features × PHQ-8 Correlation")

                # Select subset of features
                selected_acoustic = st.multiselect(
                    "Select Acoustic Features",
                    acoustic_cols,
                    default=acoustic_cols[:10] if len(acoustic_cols) > 10 else acoustic_cols
                )

                if selected_acoustic:
                    corr_data = combined_df[selected_acoustic + phq8_cols].corr(method='spearman')
                    cross_corr = corr_data.loc[selected_acoustic, phq8_cols]

                    fig = px.imshow(
                        cross_corr,
                        text_auto=".2f",
                        color_continuous_scale="RdBu_r",
                        aspect="auto",
                        zmin=-1, zmax=1,
                        labels=dict(x="PHQ-8 Item", y="Acoustic Feature", color="Spearman ρ")
                    )
                    fig.update_layout(height=max(400, len(selected_acoustic) * 25))
                    st.plotly_chart(fig, use_container_width=True)

                    # Download correlation matrix
                    csv = cross_corr.to_csv()
                    st.download_button(
                        "📥 Download Correlation Matrix",
                        csv,
                        f"correlation_matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        "text/csv"
                    )

# ============================================================================
# CLASSIFICATION METRICS TAB
# ============================================================================
with tab_classification:
    st.header("🎯 Classification Performance")

    # --- EXPLANATION ---
    with st.expander("📖 About Classification Metrics", expanded=False):
        st.markdown("""
        ### Purpose

        This tab evaluates how well individual acoustic features can **discriminate**
        between depressed and non-depressed speech samples. It provides clinical-style
        diagnostic metrics commonly used in medical screening.

        ### Key Metrics Explained

        | Metric | Formula | Interpretation |
        |--------|---------|----------------|
        | **Sensitivity** | TP / (TP + FN) | "Catch rate" - % of depressed correctly identified |
        | **Specificity** | TN / (TN + FP) | "Exclusion rate" - % of non-depressed correctly identified |
        | **PPV (Precision)** | TP / (TP + FP) | When we predict "depressed", how often are we right? |
        | **NPV** | TN / (TN + FN) | When we predict "not depressed", how often are we right? |
        | **Accuracy** | (TP + TN) / All | Overall correctness (can be misleading with imbalanced data) |
        | **F1 Score** | 2 × (PPV × Sens) / (PPV + Sens) | Harmonic mean of precision and recall |
        | **AUC-ROC** | Area under ROC curve | Overall discriminative ability (0.5 = random, 1.0 = perfect) |

        ### Current Data Context

        - **Ground Truth**: Cohort membership (depressed.json = 1, nondepressed.json = 0)
        - **Source**: TESS dataset (acted sad vs. happy emotion)
        - **Limitation**: Single speaker per cohort, acted emotions ≠ clinical depression

        ### Interpretation Guidelines

        For clinical screening tools, common targets are:
        - Sensitivity ≥ 0.80 (catch most cases)
        - Specificity ≥ 0.70 (limit false alarms)
        - AUC ≥ 0.70 (acceptable discrimination)
        """)

    st.divider()

    depressed_df, nondepressed_df = load_validation_data()

    if depressed_df is None:
        st.warning("Validation data not found.")
    else:
        # Data source reminder
        st.info("""
        **Classification Task**: Distinguish depressed vs. non-depressed speech samples.

        | Cohort | Source File | Label |
        |--------|-------------|-------|
        | Depressed | `long_depressed_sample_nobreak.wav` (TESS Sad) | 1 |
        | Non-Depressed | `long_nondepressed_sample_nobreak.wav` (TESS Happy) | 0 |
        """)

        # Create labels
        y_true_dep = np.ones(len(depressed_df))
        y_true_nondep = np.zeros(len(nondepressed_df))
        y_true = np.concatenate([y_true_dep, y_true_nondep])

        # Get common numeric features
        common_features = set(depressed_df.columns) & set(nondepressed_df.columns)
        numeric_features = sorted([f for f in common_features
                                  if depressed_df[f].dtype in ['float64', 'int64', 'float32', 'int32']])

        st.subheader("Single Feature Classification")

        col1, col2 = st.columns([2, 1])

        with col1:
            selected_feature = st.selectbox(
                "Select Feature for Classification",
                numeric_features,
                index=numeric_features.index("pause_duration") if "pause_duration" in numeric_features else 0
            )

        with col2:
            threshold_method = st.radio("Threshold", ["Median", "Mean", "Custom"])

        if selected_feature:
            # Extract feature values
            dep_values = depressed_df[selected_feature].dropna().values
            nondep_values = nondepressed_df[selected_feature].dropna().values
            all_values = np.concatenate([dep_values, nondep_values])
            y_true_filtered = np.concatenate([
                np.ones(len(dep_values)),
                np.zeros(len(nondep_values))
            ])

            # Determine threshold
            if threshold_method == "Median":
                threshold = np.median(all_values)
            elif threshold_method == "Mean":
                threshold = np.mean(all_values)
            else:
                threshold = st.slider(
                    "Custom Threshold",
                    float(np.min(all_values)),
                    float(np.max(all_values)),
                    float(np.median(all_values))
                )

            # Determine prediction direction (higher or lower = depressed)
            dep_mean = np.mean(dep_values)
            nondep_mean = np.mean(nondep_values)

            if dep_mean > nondep_mean:
                # Higher values = depressed
                y_pred = (all_values >= threshold).astype(int)
                direction = "≥"
            else:
                # Lower values = depressed
                y_pred = (all_values < threshold).astype(int)
                direction = "<"

            # Calculate metrics
            metrics = calculate_classification_metrics(y_true_filtered, y_pred, all_values)

            st.subheader("Performance Metrics")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Sensitivity (Recall)", f"{metrics.sensitivity:.3f}")
                st.caption("TP / (TP + FN)")

            with col2:
                st.metric("Specificity", f"{metrics.specificity:.3f}")
                st.caption("TN / (TN + FP)")

            with col3:
                st.metric("PPV (Precision)", f"{metrics.ppv:.3f}")
                st.caption("TP / (TP + FP)")

            with col4:
                st.metric("NPV", f"{metrics.npv:.3f}")
                st.caption("TN / (TN + FN)")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Accuracy", f"{metrics.accuracy:.3f}")

            with col2:
                st.metric("F1 Score", f"{metrics.f1_score:.3f}")

            with col3:
                if metrics.auc_roc:
                    st.metric("AUC-ROC", f"{metrics.auc_roc:.3f}")
                else:
                    st.metric("AUC-ROC", "N/A")

            with col4:
                st.metric("Threshold", f"{threshold:.4f}")

            # Confusion Matrix
            st.subheader("Confusion Matrix")

            cm_data = [
                ["", "Predicted Negative", "Predicted Positive"],
                ["Actual Negative", metrics.tn, metrics.fp],
                ["Actual Positive", metrics.fn, metrics.tp]
            ]

            cm_fig = go.Figure(data=go.Heatmap(
                z=[[metrics.tn, metrics.fp], [metrics.fn, metrics.tp]],
                x=["Predicted Negative", "Predicted Positive"],
                y=["Actual Negative", "Actual Positive"],
                colorscale="Blues",
                showscale=False,
                text=[[f"TN\n{metrics.tn}", f"FP\n{metrics.fp}"],
                      [f"FN\n{metrics.fn}", f"TP\n{metrics.tp}"]],
                texttemplate="%{text}",
                textfont={"size": 16}
            ))
            cm_fig.update_layout(height=300)
            st.plotly_chart(cm_fig, use_container_width=True)

            # Feature distribution
            st.subheader("Feature Distribution by Cohort")

            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(
                x=nondep_values, name="Non-Depressed",
                opacity=0.7, marker_color="#27AE60"
            ))
            fig_dist.add_trace(go.Histogram(
                x=dep_values, name="Depressed",
                opacity=0.7, marker_color="#E74C3C"
            ))
            fig_dist.add_vline(
                x=threshold, line_dash="dash", line_color="black",
                annotation_text=f"Threshold ({direction})"
            )
            fig_dist.update_layout(
                barmode="overlay",
                xaxis_title=selected_feature,
                yaxis_title="Count",
                template="plotly_white"
            )
            st.plotly_chart(fig_dist, use_container_width=True)

# ============================================================================
# FEATURE EXPLORER TAB
# ============================================================================
with tab_features:
    st.header("📉 Feature Distribution Explorer")

    # --- EXPLANATION ---
    with st.expander("📖 About Feature Exploration", expanded=False):
        st.markdown("""
        ### Purpose

        This tab provides **visual inspection** of how acoustic features differ between
        depressed and non-depressed speech samples. Visual analysis complements statistical
        testing by revealing distribution shapes, outliers, and overlap patterns.

        ### Visualization Options

        | Plot Type | Best For |
        |-----------|----------|
        | **Box Plot** | Comparing medians, quartiles, and outliers |
        | **Violin Plot** | Seeing full distribution shape + summary stats |
        | **Histogram** | Understanding frequency distributions and overlap |

        ### Key Acoustic Feature Categories

        | Category | Features | Expected in Depression |
        |----------|----------|------------------------|
        | **Pitch (F0)** | f0_avg, f0_std, f0_range | Lower, less variable |
        | **Speech Rate** | articulation_rate, speaking_rate | Slower |
        | **Pausing** | pause_duration, pause_rate | Longer, more frequent |
        | **Energy** | intensity_mean, energy_std | Lower, less dynamic |
        | **Voice Quality** | jitter, shimmer, hnr | More perturbation |
        | **Spectral** | spectral_centroid, mfcc_* | Variable patterns |

        ### Current Data

        - **Depressed cohort**: TESS Sad emotion samples (simulated depression)
        - **Non-depressed cohort**: TESS Happy emotion samples (simulated healthy)
        - Each "sample" is one time window from the audio stream
        """)

    st.divider()

    depressed_df, nondepressed_df = load_validation_data()

    if depressed_df is None:
        st.warning("Validation data not found.")
    else:
        # Get common numeric features
        common_features = set(depressed_df.columns) & set(nondepressed_df.columns)
        numeric_features = sorted([f for f in common_features
                                  if depressed_df[f].dtype in ['float64', 'int64', 'float32', 'int32']])

        st.subheader("Feature Selection")

        col1, col2 = st.columns([3, 1])

        with col1:
            selected_features = st.multiselect(
                "Select Features to Explore",
                numeric_features,
                default=numeric_features[:5] if len(numeric_features) > 5 else numeric_features
            )

        with col2:
            plot_type = st.selectbox("Plot Type", ["Box Plot", "Violin Plot", "Histogram"])

        if selected_features:
            for feature in selected_features:
                st.subheader(f"📊 {feature}")

                dep_vals = depressed_df[feature].dropna()
                nondep_vals = nondepressed_df[feature].dropna()

                # Quick stats
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("Dep. Mean", f"{dep_vals.mean():.4f}")
                with col2:
                    st.metric("NonDep. Mean", f"{nondep_vals.mean():.4f}")
                with col3:
                    d = cohens_d(dep_vals.values, nondep_vals.values)
                    st.metric("Cohen's d", f"{d:.3f}")
                with col4:
                    st.metric("Effect Size", interpret_cohens_d(d))

                # Create plot
                combined = pd.DataFrame({
                    feature: pd.concat([dep_vals, nondep_vals]),
                    "Cohort": ["Depressed"] * len(dep_vals) + ["Non-Depressed"] * len(nondep_vals)
                })

                if plot_type == "Box Plot":
                    fig = px.box(
                        combined, x="Cohort", y=feature,
                        color="Cohort",
                        color_discrete_map={"Depressed": "#E74C3C", "Non-Depressed": "#27AE60"},
                        template="plotly_white"
                    )
                elif plot_type == "Violin Plot":
                    fig = px.violin(
                        combined, x="Cohort", y=feature,
                        color="Cohort",
                        color_discrete_map={"Depressed": "#E74C3C", "Non-Depressed": "#27AE60"},
                        box=True,
                        template="plotly_white"
                    )
                else:
                    fig = go.Figure()
                    fig.add_trace(go.Histogram(
                        x=nondep_vals, name="Non-Depressed",
                        opacity=0.7, marker_color="#27AE60"
                    ))
                    fig.add_trace(go.Histogram(
                        x=dep_vals, name="Depressed",
                        opacity=0.7, marker_color="#E74C3C"
                    ))
                    fig.update_layout(barmode="overlay", template="plotly_white")

                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

                st.divider()

            # Summary table
            st.subheader("Summary Statistics")

            summary_data = []
            for feature in selected_features:
                dep_vals = depressed_df[feature].dropna()
                nondep_vals = nondepressed_df[feature].dropna()
                d = cohens_d(dep_vals.values, nondep_vals.values)

                summary_data.append({
                    "Feature": feature,
                    "Dep. Mean": dep_vals.mean(),
                    "Dep. Std": dep_vals.std(),
                    "NonDep. Mean": nondep_vals.mean(),
                    "NonDep. Std": nondep_vals.std(),
                    "Cohen's d": d,
                    "Effect Size": interpret_cohens_d(d),
                    "n (Dep)": len(dep_vals),
                    "n (NonDep)": len(nondep_vals)
                })

            summary_df = pd.DataFrame(summary_data)
            st.dataframe(
                summary_df.style.format({
                    "Dep. Mean": "{:.4f}",
                    "Dep. Std": "{:.4f}",
                    "NonDep. Mean": "{:.4f}",
                    "NonDep. Std": "{:.4f}",
                    "Cohen's d": "{:.3f}"
                }),
                use_container_width=True,
                hide_index=True
            )

            csv = summary_df.to_csv(index=False)
            st.download_button(
                "📥 Download Summary",
                csv,
                f"feature_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv"
            )
