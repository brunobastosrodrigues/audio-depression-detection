"""
Research Validation page.

Provides scientific validation tools for evaluating the IHearYou system's accuracy
against labeled datasets.

Research Question: Can acoustic analysis distinguish depressed from non-depressed speech?
"""

import streamlit as st
import os
import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.database import get_database, render_mode_selector, get_current_mode
from utils.user_selector import render_user_selector
from utils.validation import (
    load_cohort_data,
    run_all_hypothesis_tests,
    calculate_classification_metrics,
    cohens_d,
    interpret_cohens_d,
    DEFAULT_HYPOTHESES,
    PHQ8_TO_INDICATOR_MAPPING,
)

st.set_page_config(page_title="Research Validation", page_icon="🔬", layout="wide")

# Mode Check
if get_current_mode() != "dataset":
    st.info("This page is only available in Dataset mode.")
    st.stop()

# Sidebar
render_mode_selector()
render_user_selector()

st.title("Research Validation")
st.caption("Evaluating acoustic-based depression detection against labeled speech datasets")

# --- VALIDATION DATA PATHS ---
EVALUATION_DATA_DIR = Path("/app/docs/evaluation/hypothesis_testing_second_attempt")
if not EVALUATION_DATA_DIR.exists():
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


@st.cache_data
def compute_system_accuracy():
    """
    Compute overall system accuracy metrics.

    Returns a summary of how well the system distinguishes depressed from non-depressed speech.
    """
    depressed_df, nondepressed_df = load_validation_data()

    if depressed_df is None or nondepressed_df is None:
        return None

    # Get common numeric features
    common_features = set(depressed_df.columns) & set(nondepressed_df.columns)
    numeric_features = [f for f in common_features
                       if depressed_df[f].dtype in ['float64', 'int64', 'float32', 'int32']]

    # Run hypothesis tests with default hypotheses
    available_hypotheses = [(f, d) for f, d in DEFAULT_HYPOTHESES if f in numeric_features]

    if not available_hypotheses:
        return None

    results = run_all_hypothesis_tests(depressed_df, nondepressed_df, available_hypotheses, 0.05)

    if not results:
        return None

    # Calculate summary metrics
    significant_count = sum(1 for r in results if r.significant)
    direction_correct_count = sum(1 for r in results if r.direction_correct)
    total_tests = len(results)

    # Effect sizes
    effect_sizes = [abs(r.cohens_d) for r in results if not np.isnan(r.cohens_d)]
    large_effects = sum(1 for d in effect_sizes if d >= 0.8)
    medium_effects = sum(1 for d in effect_sizes if 0.5 <= d < 0.8)

    # Classification accuracy using best features
    best_feature = max(results, key=lambda r: abs(r.cohens_d) if not np.isnan(r.cohens_d) else 0)

    if best_feature.feature in depressed_df.columns:
        dep_vals = depressed_df[best_feature.feature].dropna().values
        nondep_vals = nondepressed_df[best_feature.feature].dropna().values
        all_vals = np.concatenate([dep_vals, nondep_vals])
        y_true = np.concatenate([np.ones(len(dep_vals)), np.zeros(len(nondep_vals))])

        # Use median threshold
        threshold = np.median(all_vals)
        dep_mean = np.mean(dep_vals)
        nondep_mean = np.mean(nondep_vals)

        if dep_mean > nondep_mean:
            y_pred = (all_vals >= threshold).astype(int)
        else:
            y_pred = (all_vals < threshold).astype(int)

        metrics = calculate_classification_metrics(y_true, y_pred, all_vals)
        best_accuracy = metrics.accuracy
        best_auc = metrics.auc_roc
    else:
        best_accuracy = 0
        best_auc = 0

    return {
        "total_features_tested": total_tests,
        "significant_differences": significant_count,
        "direction_correct": direction_correct_count,
        "large_effects": large_effects,
        "medium_effects": medium_effects,
        "avg_effect_size": np.mean(effect_sizes) if effect_sizes else 0,
        "best_feature": best_feature.feature,
        "best_feature_d": best_feature.cohens_d,
        "best_accuracy": best_accuracy,
        "best_auc": best_auc or 0,
        "agreement_score": direction_correct_count / total_tests * 100 if total_tests > 0 else 0,
    }


# ============================================================================
# RESEARCH QUESTION
# ============================================================================
st.markdown("""
**Research Question:** Can acoustic speech features reliably distinguish between
depressed and non-depressed speech patterns, validating the IHearYou system's
approach to depression detection?
""")

st.divider()

# Load data and compute accuracy
depressed_df, nondepressed_df = load_validation_data()

if depressed_df is None or nondepressed_df is None:
    st.error("""
    **Validation data not found.**

    Please ensure the TESS dataset has been processed and the JSON files exist:
    - `docs/evaluation/hypothesis_testing_second_attempt/depressed.json`
    - `docs/evaluation/hypothesis_testing_second_attempt/nondepressed.json`

    Run the seeding script: `python scripts/seed_dataset_mode.py`
    """)
    st.stop()

# Compute system accuracy
accuracy_data = compute_system_accuracy()

if accuracy_data is None:
    st.error("Could not compute validation metrics. Check data format.")
    st.stop()

# ============================================================================
# SUMMARY METRICS
# ============================================================================
st.markdown("## Summary of Findings")

agreement = accuracy_data["agreement_score"]
if agreement >= 80:
    finding = "Strong support"
    finding_desc = "Acoustic features show expected directional differences consistent with depression research literature."
elif agreement >= 60:
    finding = "Moderate support"
    finding_desc = "Most acoustic features show expected differences, though some behave unexpectedly."
else:
    finding = "Limited support"
    finding_desc = "Many features do not show expected directional differences. Further investigation needed."

# Key metrics in a structured layout
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Features Tested",
        accuracy_data['total_features_tested'],
        help="Number of acoustic features analyzed"
    )

with col2:
    pct = accuracy_data['significant_differences'] / accuracy_data['total_features_tested'] * 100
    st.metric(
        "Significant (p<0.05)",
        f"{accuracy_data['significant_differences']}",
        f"{pct:.0f}%",
        help="Features with statistically significant differences after FDR correction"
    )

with col3:
    st.metric(
        "Direction Correct",
        f"{accuracy_data['direction_correct']}/{accuracy_data['total_features_tested']}",
        f"{agreement:.0f}%",
        help="Features showing expected directional differences per literature"
    )

with col4:
    st.metric(
        "Avg Effect Size (|d|)",
        f"{accuracy_data['avg_effect_size']:.2f}",
        interpret_cohens_d(accuracy_data['avg_effect_size']),
        help="Mean absolute Cohen's d across all features"
    )

st.markdown(f"""
**Interpretation:** {finding} — {finding_desc}
""")

st.divider()

# ============================================================================
# BEST DISCRIMINATING FEATURE
# ============================================================================
st.markdown("### Top Discriminating Feature")

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown(f"""
    The feature with highest discriminative power:

    | Metric | Value |
    |--------|-------|
    | **Feature** | `{accuracy_data['best_feature']}` |
    | **Cohen's d** | {accuracy_data['best_feature_d']:.2f} ({interpret_cohens_d(accuracy_data['best_feature_d'])}) |
    | **Accuracy** | {accuracy_data['best_accuracy']*100:.1f}% |
    | **AUC-ROC** | {accuracy_data['best_auc']:.2f} |
    """)

with col2:
    # Effect size breakdown
    st.markdown("""
    **Effect Size Distribution:**
    """)
    st.markdown(f"""
    - Large effects (|d| ≥ 0.8): **{accuracy_data['large_effects']}**
    - Medium effects (0.5 ≤ |d| < 0.8): **{accuracy_data['medium_effects']}**
    - Small/negligible: **{accuracy_data['total_features_tested'] - accuracy_data['large_effects'] - accuracy_data['medium_effects']}**
    """)

st.divider()

# ============================================================================
# DATASET DESCRIPTION
# ============================================================================
st.markdown("## Dataset & Methodology")

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("""
    ### TESS Dataset

    The Toronto Emotional Speech Set (TESS) provides acted emotional speech samples.

    | Cohort | Emotion | N samples | Purpose |
    |--------|---------|-----------|---------|
    | Depressed proxy | Sad | varies | Depression-like acoustic patterns |
    | Non-depressed | Happy | varies | Healthy control patterns |

    **Rationale:** Sad speech shares acoustic characteristics with depressed speech
    (reduced pitch variability, slower rate, lower energy), making it a reasonable
    proxy for initial system validation.
    """)

with col2:
    st.markdown("""
    ### Limitations

    1. **Acted vs. Clinical:** TESS uses acted emotions, not clinically diagnosed patients
    2. **Single speaker per cohort:** Limited generalizability
    3. **Emotion ≠ Disorder:** Sadness is transient; MDD is chronic

    ### Future Work

    Clinical validation requires the **DAIC-WOZ dataset** with:
    - Real clinical interviews
    - PHQ-8 ground truth scores
    - Multiple speakers with varying severity

    *(Access pending)*
    """)

st.divider()

# ============================================================================
# DETAILED ANALYSIS TABS
# ============================================================================
st.markdown("## Detailed Analysis")

tab_hypothesis, tab_classification, tab_features = st.tabs([
    "Statistical Tests",
    "Classification Metrics",
    "Feature Explorer"
])

# ============================================================================
# HYPOTHESIS TESTING TAB
# ============================================================================
with tab_hypothesis:
    st.markdown("""
    ### Hypothesis Testing Results

    For each acoustic feature, we test whether the depressed cohort differs
    from the non-depressed cohort in the direction predicted by literature.

    - **Test:** Mann-Whitney U (non-parametric)
    - **Correction:** Benjamini-Hochberg FDR (α = 0.05)
    - **Effect size:** Cohen's d
    """)

    # Get available features
    common_features = set(depressed_df.columns) & set(nondepressed_df.columns)
    numeric_features = [f for f in common_features
                       if depressed_df[f].dtype in ['float64', 'int64', 'float32', 'int32']]

    available_hypotheses = [(f, d) for f, d in DEFAULT_HYPOTHESES if f in numeric_features]

    if st.button("Run Hypothesis Tests", type="primary"):
        with st.spinner("Running statistical tests..."):
            results = run_all_hypothesis_tests(depressed_df, nondepressed_df, available_hypotheses, 0.05)

        if results:
            # Results table
            results_data = []
            for r in results:
                results_data.append({
                    "Feature": r.feature,
                    "Expected": f"Dep {r.direction} NonDep",
                    "Direction": "Correct" if r.direction_correct else "Incorrect",
                    "Dep Mean": f"{r.depressed_mean:.3f}",
                    "NonDep Mean": f"{r.nondepressed_mean:.3f}",
                    "Cohen's d": f"{r.cohens_d:.2f}",
                    "Effect": interpret_cohens_d(r.cohens_d),
                    "p (FDR)": f"{r.p_value_corrected:.4f}" if r.p_value_corrected else "N/A",
                    "Sig.": "Yes" if r.significant else "No",
                })

            df_results = pd.DataFrame(results_data)
            st.dataframe(df_results, use_container_width=True, hide_index=True)

            # Effect size chart
            st.subheader("Effect Sizes by Feature")

            effect_data = [
                {"Feature": r.feature, "Cohen's d": r.cohens_d,
                 "Direction": "Correct" if r.direction_correct else "Incorrect"}
                for r in results if not np.isnan(r.cohens_d)
            ]
            effect_df = pd.DataFrame(effect_data).sort_values("Cohen's d")

            fig = px.bar(
                effect_df, x="Cohen's d", y="Feature", orientation="h",
                color="Direction",
                color_discrete_map={"Correct": "#2E7D32", "Incorrect": "#C62828"},
                template="plotly_white"
            )
            fig.add_vline(x=0.8, line_dash="dash", annotation_text="Large", line_color="#666")
            fig.add_vline(x=0.5, line_dash="dash", annotation_text="Medium", line_color="#666")
            fig.add_vline(x=0.2, line_dash="dash", annotation_text="Small", line_color="#666")
            fig.update_layout(height=max(400, len(effect_data) * 25))
            st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# CLASSIFICATION TAB
# ============================================================================
with tab_classification:
    st.markdown("""
    ### Classification Performance

    Evaluating single-feature classifiers using median-split thresholds.
    This simulates using each acoustic feature as a simple screening indicator.
    """)

    # Feature selection
    selected_feature = st.selectbox(
        "Select Feature",
        sorted(numeric_features),
        index=sorted(numeric_features).index("pause_duration") if "pause_duration" in numeric_features else 0
    )

    if selected_feature:
        dep_vals = depressed_df[selected_feature].dropna().values
        nondep_vals = nondepressed_df[selected_feature].dropna().values
        all_vals = np.concatenate([dep_vals, nondep_vals])
        y_true = np.concatenate([np.ones(len(dep_vals)), np.zeros(len(nondep_vals))])

        # Threshold
        threshold = np.median(all_vals)
        dep_mean = np.mean(dep_vals)
        nondep_mean = np.mean(nondep_vals)

        if dep_mean > nondep_mean:
            y_pred = (all_vals >= threshold).astype(int)
            direction_text = "Higher values → Depressed"
        else:
            y_pred = (all_vals < threshold).astype(int)
            direction_text = "Lower values → Depressed"

        metrics = calculate_classification_metrics(y_true, y_pred, all_vals)

        # Display metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Accuracy", f"{metrics.accuracy:.1%}")
        with col2:
            st.metric("Sensitivity", f"{metrics.sensitivity:.1%}", help="True positive rate")
        with col3:
            st.metric("Specificity", f"{metrics.specificity:.1%}", help="True negative rate")
        with col4:
            auc = metrics.auc_roc or 0
            st.metric("AUC-ROC", f"{auc:.2f}", help="Area under ROC curve")

        # Distribution plot
        st.subheader("Feature Distribution")

        fig = go.Figure()
        fig.add_trace(go.Histogram(x=nondep_vals, name="Non-Depressed",
                                   opacity=0.7, marker_color="#2E7D32"))
        fig.add_trace(go.Histogram(x=dep_vals, name="Depressed",
                                   opacity=0.7, marker_color="#C62828"))
        fig.add_vline(x=threshold, line_dash="dash", line_color="black",
                      annotation_text=f"Threshold: {threshold:.3f}")
        fig.update_layout(barmode="overlay", template="plotly_white",
                         xaxis_title=selected_feature, yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)

        st.caption(f"**Decision rule:** {direction_text}")

# ============================================================================
# FEATURE EXPLORER TAB
# ============================================================================
with tab_features:
    st.markdown("""
    ### Feature Explorer

    Compare acoustic feature distributions between cohorts.
    """)

    selected_features = st.multiselect(
        "Select Features",
        sorted(numeric_features),
        default=sorted(numeric_features)[:5]
    )

    plot_type = st.radio("Plot Type", ["Violin", "Box", "Histogram"], horizontal=True)

    for feature in selected_features:
        dep_vals = depressed_df[feature].dropna()
        nondep_vals = nondepressed_df[feature].dropna()

        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.markdown(f"**{feature}**")
        with col2:
            d = cohens_d(dep_vals.values, nondep_vals.values)
            st.metric("Cohen's d", f"{d:.2f}", interpret_cohens_d(d))
        with col3:
            diff_pct = (dep_vals.mean() - nondep_vals.mean()) / nondep_vals.mean() * 100 if nondep_vals.mean() != 0 else 0
            st.metric("Difference", f"{diff_pct:+.1f}%")

        combined = pd.DataFrame({
            feature: pd.concat([dep_vals, nondep_vals]),
            "Group": ["Depressed"] * len(dep_vals) + ["Non-Depressed"] * len(nondep_vals)
        })

        if plot_type == "Violin":
            fig = px.violin(combined, x="Group", y=feature, color="Group", box=True,
                           color_discrete_map={"Depressed": "#C62828", "Non-Depressed": "#2E7D32"})
        elif plot_type == "Box":
            fig = px.box(combined, x="Group", y=feature, color="Group",
                        color_discrete_map={"Depressed": "#C62828", "Non-Depressed": "#2E7D32"})
        else:
            fig = go.Figure()
            fig.add_trace(go.Histogram(x=nondep_vals, name="Non-Depressed", opacity=0.7, marker_color="#2E7D32"))
            fig.add_trace(go.Histogram(x=dep_vals, name="Depressed", opacity=0.7, marker_color="#C62828"))
            fig.update_layout(barmode="overlay")

        fig.update_layout(height=300, template="plotly_white", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.divider()
