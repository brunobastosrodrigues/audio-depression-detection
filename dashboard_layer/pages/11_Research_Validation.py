"""
Research Validation page.

Provides scientific validation tools for evaluating the IHearYou system's accuracy
against labeled datasets. Designed to answer: "Does this approach capture reality?"

Key Question: Can IHearYou correctly distinguish between depressed and non-depressed speech?
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

st.title("🔬 Research Validation")

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
    # Find the feature with highest effect size
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
# MAIN QUESTION: DOES THE SYSTEM WORK?
# ============================================================================
st.markdown("""
<div style="
    padding: 1.5rem;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 12px;
    color: white;
    margin-bottom: 2rem;
">
    <h2 style="margin: 0 0 0.5rem 0; color: white;">The Key Question</h2>
    <p style="font-size: 1.2rem; margin: 0; opacity: 0.95;">
        Can IHearYou correctly distinguish between depressed and non-depressed speech patterns?
    </p>
</div>
""", unsafe_allow_html=True)

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
# PLAIN-LANGUAGE SUMMARY
# ============================================================================
st.markdown("## The Short Answer")

# Determine overall verdict
agreement = accuracy_data["agreement_score"]
if agreement >= 80:
    verdict = "YES"
    verdict_color = "#27AE60"
    verdict_icon = "✅"
    verdict_text = "The system shows **strong agreement** with expected patterns."
elif agreement >= 60:
    verdict = "MOSTLY"
    verdict_color = "#F39C12"
    verdict_icon = "⚠️"
    verdict_text = "The system shows **moderate agreement** with expected patterns."
else:
    verdict = "NEEDS WORK"
    verdict_color = "#E74C3C"
    verdict_icon = "❌"
    verdict_text = "The system shows **limited agreement** with expected patterns."

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.markdown(f"""
    <div style="
        text-align: center;
        padding: 2rem;
        background: {verdict_color}15;
        border: 3px solid {verdict_color};
        border-radius: 16px;
    ">
        <div style="font-size: 3rem; margin-bottom: 0.5rem;">{verdict_icon}</div>
        <div style="font-size: 2rem; font-weight: bold; color: {verdict_color};">{verdict}</div>
        <div style="font-size: 1.1rem; color: #555; margin-top: 0.5rem;">{verdict_text}</div>
        <div style="font-size: 2.5rem; font-weight: bold; color: {verdict_color}; margin-top: 1rem;">
            {agreement:.0f}% Agreement
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Plain language explanation
with st.container():
    st.markdown("""
    ### What This Means (In Plain English)

    We tested the IHearYou system against labeled audio samples where we **already know**
    which recordings came from sad speech (simulating depression) and which came from
    happy speech (simulating non-depression).
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        #### What We Found

        - **{accuracy_data['direction_correct']}/{accuracy_data['total_features_tested']}** acoustic features
          showed the expected differences between groups
        - **{accuracy_data['significant_differences']}** features had statistically significant differences
        - **{accuracy_data['large_effects'] + accuracy_data['medium_effects']}** features showed
          medium-to-large effect sizes (meaningful real-world differences)
        """)

    with col2:
        st.markdown(f"""
        #### Best Individual Feature

        The most discriminating feature was **`{accuracy_data['best_feature']}`**:
        - Cohen's d: **{accuracy_data['best_feature_d']:.2f}** ({interpret_cohens_d(accuracy_data['best_feature_d'])})
        - Classification accuracy: **{accuracy_data['best_accuracy']*100:.1f}%**
        - AUC-ROC: **{accuracy_data['best_auc']:.2f}** {"(good discrimination)" if accuracy_data['best_auc'] >= 0.7 else "(moderate discrimination)"}
        """)

st.divider()

# ============================================================================
# VISUAL SUMMARY
# ============================================================================
st.markdown("## Visual Summary")

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
        "Significant Differences",
        f"{accuracy_data['significant_differences']}",
        f"{pct:.0f}%",
        help="Features with p < 0.05 after FDR correction"
    )

with col3:
    st.metric(
        "Large Effects",
        accuracy_data['large_effects'],
        help="Features with |Cohen's d| ≥ 0.8"
    )

with col4:
    st.metric(
        "Avg Effect Size",
        f"{accuracy_data['avg_effect_size']:.2f}",
        interpret_cohens_d(accuracy_data['avg_effect_size']),
        help="Mean absolute Cohen's d across all features"
    )

# Agreement gauge
st.markdown("### Agreement with Expected Patterns")

fig_gauge = go.Figure(go.Indicator(
    mode="gauge+number+delta",
    value=accuracy_data['agreement_score'],
    domain={'x': [0, 1], 'y': [0, 1]},
    title={'text': "Direction Agreement (%)"},
    delta={'reference': 50, 'increasing': {'color': "#27AE60"}},
    gauge={
        'axis': {'range': [0, 100]},
        'bar': {'color': verdict_color},
        'steps': [
            {'range': [0, 50], 'color': "#FADBD8"},
            {'range': [50, 70], 'color': "#FCF3CF"},
            {'range': [70, 100], 'color': "#D5F5E3"}
        ],
        'threshold': {
            'line': {'color': "black", 'width': 4},
            'thickness': 0.75,
            'value': 80
        }
    }
))
fig_gauge.update_layout(height=300)
st.plotly_chart(fig_gauge, use_container_width=True)

st.caption("""
**How to interpret**: "Direction Agreement" measures whether features change in the expected direction
between depressed and non-depressed speech. For example, if research suggests depressed speech has
*lower* pitch, we check if our system also finds lower pitch in the sad/depressed samples.
- **≥80%**: Strong agreement with research literature
- **60-80%**: Moderate agreement, some features behave unexpectedly
- **<60%**: Limited agreement, the model may need refinement
""")

st.divider()

# ============================================================================
# DATASET CONTEXT
# ============================================================================
st.markdown("## About the Test Data")

with st.expander("📖 Understanding the TESS Dataset", expanded=True):
    st.markdown("""
    ### What We're Testing Against

    The validation uses the **TESS (Toronto Emotional Speech Set)** - a well-known
    research dataset of recorded emotional speech.

    | Dataset File | Emotion | Used As | Why |
    |--------------|---------|---------|-----|
    | `long_depressed_sample_nobreak.wav` | **Sad** | Depression proxy | Sad speech shares acoustic patterns with depressed speech (lower pitch, slower rate, less energy) |
    | `long_nondepressed_sample_nobreak.wav` | **Happy** | Healthy control | Happy speech represents typical non-depressed patterns |

    ### Important Caveats

    1. **Acted vs. Real**: TESS uses *acted* emotions from voice actors, not recordings
       from clinically diagnosed patients. Real depression may have more subtle differences.

    2. **Single Speaker Per Cohort**: Each audio file comes from one speaker, limiting
       how well these results generalize to other voices.

    3. **Emotion ≠ Depression**: Sadness is a mood; Major Depressive Disorder is a
       clinical condition. They correlate but aren't equivalent.

    ### What This Validation Shows

    This test answers: *"Can our acoustic analysis pipeline detect known emotional differences?"*

    - **If YES** (high agreement): The system's feature extraction and analysis are working correctly
    - **If NO** (low agreement): There may be bugs or calibration issues to investigate

    ### Future Clinical Validation

    For true clinical validity, we need the **DAIC-WOZ dataset** which contains:
    - Real clinical interviews (not acted)
    - PHQ-8 depression scores (ground truth)
    - Multiple speakers with varying depression severity

    *(Access pending - results will be added when available)*
    """)

st.divider()

# ============================================================================
# DETAILED ANALYSIS TABS
# ============================================================================
st.markdown("## Detailed Analysis")

tab_hypothesis, tab_classification, tab_features = st.tabs([
    "🧪 Statistical Tests",
    "🎯 Classification Performance",
    "📊 Feature Explorer"
])

# ============================================================================
# HYPOTHESIS TESTING TAB
# ============================================================================
with tab_hypothesis:
    st.markdown("""
    ### Hypothesis Testing

    We test whether each acoustic feature differs significantly between the two groups,
    using the direction predicted by depression research literature.
    """)

    # Get available features
    common_features = set(depressed_df.columns) & set(nondepressed_df.columns)
    numeric_features = [f for f in common_features
                       if depressed_df[f].dtype in ['float64', 'int64', 'float32', 'int32']]

    available_hypotheses = [(f, d) for f, d in DEFAULT_HYPOTHESES if f in numeric_features]

    if st.button("🔬 Run Full Hypothesis Tests", type="primary"):
        with st.spinner("Running statistical tests..."):
            results = run_all_hypothesis_tests(depressed_df, nondepressed_df, available_hypotheses, 0.05)

        if results:
            # Results table
            results_data = []
            for r in results:
                results_data.append({
                    "Feature": r.feature,
                    "Expected": f"Dep {r.direction} NonDep",
                    "Actual Direction": "✅ Correct" if r.direction_correct else "❌ Wrong",
                    "Dep Mean": f"{r.depressed_mean:.3f}",
                    "NonDep Mean": f"{r.nondepressed_mean:.3f}",
                    "Effect Size": f"{r.cohens_d:.2f} ({interpret_cohens_d(r.cohens_d)})",
                    "p-value (FDR)": f"{r.p_value_corrected:.4f}" if r.p_value_corrected else "N/A",
                    "Significant": "✅" if r.significant else "❌",
                })

            st.dataframe(pd.DataFrame(results_data), use_container_width=True, hide_index=True)

            # Effect size chart
            st.subheader("Effect Sizes by Feature")

            effect_data = [
                {"Feature": r.feature, "Cohen's d": r.cohens_d,
                 "Direction Correct": "Correct" if r.direction_correct else "Wrong"}
                for r in results if not np.isnan(r.cohens_d)
            ]
            effect_df = pd.DataFrame(effect_data).sort_values("Cohen's d")

            fig = px.bar(
                effect_df, x="Cohen's d", y="Feature", orientation="h",
                color="Direction Correct",
                color_discrete_map={"Correct": "#27AE60", "Wrong": "#E74C3C"},
                template="plotly_white"
            )
            fig.add_vline(x=0.8, line_dash="dash", annotation_text="Large")
            fig.add_vline(x=0.5, line_dash="dash", annotation_text="Medium")
            fig.add_vline(x=0.2, line_dash="dash", annotation_text="Small")
            fig.update_layout(height=max(400, len(effect_data) * 25))
            st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# CLASSIFICATION TAB
# ============================================================================
with tab_classification:
    st.markdown("""
    ### Classification Performance

    How accurately can individual features distinguish between the two groups?
    This simulates using the feature as a simple screening tool.
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
            direction_text = "Higher = Depressed"
        else:
            y_pred = (all_vals < threshold).astype(int)
            direction_text = "Lower = Depressed"

        metrics = calculate_classification_metrics(y_true, y_pred, all_vals)

        # Display metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Accuracy", f"{metrics.accuracy:.1%}")
        with col2:
            st.metric("Sensitivity", f"{metrics.sensitivity:.1%}", help="Catch rate for depression")
        with col3:
            st.metric("Specificity", f"{metrics.specificity:.1%}", help="Correct rejection rate")
        with col4:
            auc = metrics.auc_roc or 0
            st.metric("AUC-ROC", f"{auc:.2f}", help="0.5=random, 1.0=perfect")

        # Distribution plot
        st.subheader("Feature Distribution")

        fig = go.Figure()
        fig.add_trace(go.Histogram(x=nondep_vals, name="Non-Depressed (Happy)",
                                   opacity=0.7, marker_color="#27AE60"))
        fig.add_trace(go.Histogram(x=dep_vals, name="Depressed (Sad)",
                                   opacity=0.7, marker_color="#E74C3C"))
        fig.add_vline(x=threshold, line_dash="dash", line_color="black",
                      annotation_text=f"Threshold: {threshold:.3f}")
        fig.update_layout(barmode="overlay", template="plotly_white",
                         xaxis_title=selected_feature, yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)

        st.caption(f"**Decision rule**: {direction_text} (based on group means)")

# ============================================================================
# FEATURE EXPLORER TAB
# ============================================================================
with tab_features:
    st.markdown("""
    ### Feature Explorer

    Visually compare how acoustic features differ between the two groups.
    """)

    selected_features = st.multiselect(
        "Select Features to Compare",
        sorted(numeric_features),
        default=sorted(numeric_features)[:5]
    )

    plot_type = st.radio("Plot Type", ["Violin", "Box", "Histogram"], horizontal=True)

    for feature in selected_features:
        dep_vals = depressed_df[feature].dropna()
        nondep_vals = nondepressed_df[feature].dropna()

        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.markdown(f"#### {feature}")
        with col2:
            d = cohens_d(dep_vals.values, nondep_vals.values)
            st.metric("Effect Size", f"{d:.2f}", interpret_cohens_d(d))
        with col3:
            diff_pct = (dep_vals.mean() - nondep_vals.mean()) / nondep_vals.mean() * 100 if nondep_vals.mean() != 0 else 0
            st.metric("Difference", f"{diff_pct:+.1f}%")

        combined = pd.DataFrame({
            feature: pd.concat([dep_vals, nondep_vals]),
            "Group": ["Depressed (Sad)"] * len(dep_vals) + ["Non-Depressed (Happy)"] * len(nondep_vals)
        })

        if plot_type == "Violin":
            fig = px.violin(combined, x="Group", y=feature, color="Group", box=True,
                           color_discrete_map={"Depressed (Sad)": "#E74C3C", "Non-Depressed (Happy)": "#27AE60"})
        elif plot_type == "Box":
            fig = px.box(combined, x="Group", y=feature, color="Group",
                        color_discrete_map={"Depressed (Sad)": "#E74C3C", "Non-Depressed (Happy)": "#27AE60"})
        else:
            fig = go.Figure()
            fig.add_trace(go.Histogram(x=nondep_vals, name="Non-Depressed", opacity=0.7, marker_color="#27AE60"))
            fig.add_trace(go.Histogram(x=dep_vals, name="Depressed", opacity=0.7, marker_color="#E74C3C"))
            fig.update_layout(barmode="overlay")

        fig.update_layout(height=300, template="plotly_white", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.divider()
