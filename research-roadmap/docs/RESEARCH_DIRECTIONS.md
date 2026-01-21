# Research Directions: Depression Detection from Voice

**Date:** 2026-01-21
**Status:** Exploration Phase
**Perspective:** Computer Science (Technical, Non-Clinical)

---

## Current System Status

| Component | Status | Research Value |
|-----------|--------|----------------|
| 42 handcrafted acoustic features | Implemented | Established (not novel) |
| DSM-5 indicator mapping | Heuristic | Unvalidated |
| Edge deployment (ESP32-S3) | Engineering | Not publishable alone |
| Zero-cloud architecture | Privacy feature | Implementation, not research |
| Speaker verification (D-vector) | Working | Standard technique |

**Honest Assessment:** The current system is a **demo/prototype**, not a research contribution.

---

## What Makes Research vs Engineering

| Engineering (Weak) | Research (Strong) |
|-------------------|------------------|
| "First ESP32 depression detector" | "Systematic analysis of feature fidelity under compute constraints" |
| "We ported X to MCU" | "We quantify the accuracy-cost tradeoff curve" |
| "It works on ESP32" | "We identify which constraints hurt most and propose mitigations" |
| "Privacy-preserving" | "Information-theoretic bounds on minimal data for detection" |

---

## Potential Research Directions

### Direction 1: Feature Degradation Analysis (Systems/ML)

**Research Question:**
> What is the accuracy cost of edge-constrained acoustic feature extraction for depression detection?

**Sub-questions:**
- Which features degrade most under INT16 fixed-point arithmetic?
- What is the minimum FFT size that preserves F0 tracking accuracy?
- Can we predict classification accuracy drop from feature MAPE?

**Methodology:**
1. Python baseline with 6 validated features (Praat/parselmouth)
2. C implementation with progressive simplifications
3. Train on Python features, test on C features
4. Plot F1-score vs. {FFT size, bit-depth, buffer length}

**Contribution Type:** Empirical study, reproducible methodology
**Venue Fit:** MobiSys, SenSys, IMWUT
**Feasibility:** High (no IRB, public datasets)
**Novelty Risk:** Medium (incremental if framed poorly)

---

### Direction 2: Longitudinal vs Snapshot Detection (Clinical Science)

**Research Question:**
> Does continuous passive monitoring with simple features detect depression earlier than periodic clinical assessment?

**Hypothesis:**
Longitudinal trends (e.g., F0 variance declining over 2 weeks) may be more predictive than single-session feature magnitude.

**Methodology:**
1. Collect multi-week data from consenting participants
2. Compare: (a) single-session features vs (b) temporal trend features
3. Evaluate against PHQ-9 administered at study end

**Contribution Type:** Clinical validation study
**Venue Fit:** JMIR, npj Digital Medicine, CHI
**Feasibility:** Low (requires IRB, months of data collection)
**Novelty Risk:** Low (high impact if successful)

---

### Direction 3: Cross-Cultural Acoustic Markers (Scientific Discovery)

**Research Question:**
> Do acoustic depression markers generalize across languages and cultures?

**Hypothesis:**
Some features (F0, pause patterns) may be universal; others (speech rate, formants) may be language-dependent.

**Methodology:**
1. Train on DAIC-WOZ (English, 189 sessions)
2. Test on MODMA (Chinese, 53 subjects)
3. Collect Portuguese dataset (your population)
4. Analyze per-feature transfer performance

**Contribution Type:** Cross-cultural validation
**Venue Fit:** AAAI, IJCAI, Interspeech
**Feasibility:** Medium (need Portuguese data collection)
**Novelty Risk:** Low (fundamental question, underexplored)

---

### Direction 4: Interpretability as Clinical Requirement (Health Informatics)

**Research Question:**
> Does feature interpretability affect clinician trust and intervention decisions?

**Hypothesis:**
Clinicians may prefer lower-accuracy interpretable models over higher-accuracy black boxes for mental health screening.

**Methodology:**
1. Build two systems: (a) handcrafted features + decision tree, (b) wav2vec2 black box
2. User study with clinicians (n=20-30)
3. Measure: trust, willingness to act, perceived utility

**Contribution Type:** Human-AI interaction study
**Venue Fit:** CHI, CSCW, AMIA
**Feasibility:** Medium (requires clinician recruitment)
**Novelty Risk:** Low (important gap in health AI adoption)

---

### Direction 5: Information-Theoretic Feature Bounds (ML Theory)

**Research Question:**
> What is the minimum information needed to detect depression from voice?

**Formalization:**
- Let X = raw audio, Y = depression label
- What is I(f(X); Y) for various feature extractors f?
- Can we derive lower bounds on feature dimensionality?

**Methodology:**
1. Compute mutual information estimates for feature sets
2. Apply rate-distortion theory to feature compression
3. Derive theoretical minimum for given accuracy target

**Contribution Type:** Theoretical analysis with empirical validation
**Venue Fit:** NeurIPS, ICML, AISTATS
**Feasibility:** High (no new data collection)
**Novelty Risk:** Medium (requires novel theoretical framing)

---

### Direction 6: Privacy-Utility Tradeoffs (Security/Privacy)

**Research Question:**
> What is the privacy-utility frontier for voice-based depression detection?

**Formalization:**
- Utility: F1-score for depression classification
- Privacy: Reconstruction error of raw audio from features

**Methodology:**
1. Train audio reconstruction network from features
2. Measure reconstruction quality vs classification accuracy
3. Apply differential privacy to feature extraction
4. Plot Pareto frontier

**Contribution Type:** Privacy analysis framework
**Venue Fit:** USENIX Security, IEEE S&P, PETS
**Feasibility:** High (no new data collection)
**Novelty Risk:** Low (privacy in health is hot topic)

---

## Resource Requirements by Direction

| Direction | IRB | New Data | Clinical Partners | Timeline |
|-----------|-----|----------|-------------------|----------|
| 1. Feature Degradation | No | No (DAIC-WOZ) | No | 3-6 months |
| 2. Longitudinal | Yes | Yes (weeks) | Recommended | 12+ months |
| 3. Cross-Cultural | Maybe | Yes (Portuguese) | No | 6-9 months |
| 4. Interpretability | Yes (user study) | No | Yes (clinicians) | 6-9 months |
| 5. Info-Theoretic | No | No | No | 4-6 months |
| 6. Privacy-Utility | No | No | No | 4-6 months |

---

## Recommended Starting Point

**For a CS lab without clinical resources:**

1. **Direction 1 (Feature Degradation)** - Pure technical, fast
2. **Direction 6 (Privacy-Utility)** - Timely, no IRB
3. **Direction 5 (Info-Theoretic)** - Theory contribution

**For building toward clinical impact:**

1. Start with Direction 1 (technical foundation)
2. Add Direction 3 (Portuguese data collection)
3. Eventually Direction 2 (longitudinal study with clinical partners)

---

## Baselines and Benchmarks

### DAIC-WOZ Performance (Official Benchmark)

| System | Year | Features | Metric | Value |
|--------|------|----------|--------|-------|
| AVEC 2019 Baseline | 2019 | eGeMAPS (88) | CCC | 0.120 |
| AVEC 2019 Winner | 2019 | Text + Audio | CCC | 0.67 |
| wav2vec 2.0 | 2024 | Self-supervised | Accuracy | 96.49% |
| CNN-to-SNN | 2024 | Spectrograms | F1 | 0.825 |

### Validated Acoustic Features (Clinical Evidence)

| Feature | Finding | p-value | Source |
|---------|---------|---------|--------|
| Jitter | Higher in depressed | <0.001 | Cummins 2015 |
| Shimmer | Higher in depressed | <0.001, η²=0.066 | Scherer 2013 |
| F0 mean | Lower in depressed | <0.01 | Cannizzaro 2004 |
| F0 std | Reduced variability | <0.01 | Mundt 2012 |
| Pause ratio | Increased pauses | <0.05 | Low 2011 |
| Speech rate | Reduced | <0.05 | Ooi 2014 |

---

## Datasets Available

| Dataset | Size | Labels | Language | Access |
|---------|------|--------|----------|--------|
| DAIC-WOZ | 189 sessions | PHQ-8 | English | Request |
| E-DAIC | 275 sessions | PHQ-8, PCL-C | English | Request |
| MODMA | 53 subjects | PHQ-9, clinical | Chinese | Free (EULA) |
| CMDC | 78 participants | Clinical MDD | Chinese | IEEE DataPort |
| TESS | 2800 samples | Emotions (not depression) | English | Open |

**Note:** TESS contains acted emotions, NOT clinical depression. Not suitable for depression detection validation.

---

## Next Steps

1. [ ] Choose primary research direction
2. [ ] Request DAIC-WOZ dataset access (if using)
3. [ ] Define specific hypotheses and success metrics
4. [ ] Identify target venue and format (conference vs journal)
5. [ ] Create detailed experimental protocol
6. [ ] Assign responsibilities (if multi-author)

---

## References

### Key Papers
- Cummins et al. 2015 - "A review of depression and suicide risk assessment using speech analysis"
- AVEC 2019 Workshop - "Audio/Visual Emotion Challenge and Workshop"
- Wav2vec 2.0 for Depression - "Improving speech depression detection using transfer learning"
- CNN-to-SNN - "From Convolution to Spikes for DAIC-WOZ"
- Federated Learning - "Privacy Sensitive Speech Analysis Using Federated Learning"

### Tools
- openSMILE: Feature extraction (C++, runs on Pi)
- Praat/parselmouth: Clinical standard for voice analysis
- TensorFlow Lite Micro: Edge ML deployment
- Edge Impulse: End-to-end TinyML platform

---

*Document maintained by: IHearYou Research Team*
