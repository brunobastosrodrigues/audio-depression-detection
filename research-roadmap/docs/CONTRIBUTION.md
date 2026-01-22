# Research Contribution: Zero-Cloud Paralinguistic Sensing

## One-Sentence Pitch

**We demonstrate that clinically-relevant paralinguistic features for mental health monitoring can be extracted entirely within a household using commodity edge hardware, achieving <5% accuracy loss compared to cloud-based systems while guaranteeing that no audio data ever leaves the home.**

---

## The Problem

Current voice-based mental health monitoring systems face a fundamental tension:

1. **Privacy Concern:** Users are reluctant to send continuous voice recordings to cloud servers
2. **Clinical Need:** Longitudinal acoustic features are valuable for depression/anxiety monitoring
3. **Technical Reality:** State-of-the-art feature extraction requires significant compute

**Result:** Systems either sacrifice privacy (cloud processing) or capability (limited on-device features).

---

## Our Solution: Hierarchical Zero-Cloud Architecture

We propose a **three-tier hierarchy** that keeps all data within the household:

```
Tier 1 (Edge): ESP32-S3 devices extract basic features locally
    ↓ (features only, ~200 bytes per utterance)
Tier 2 (Hub): Raspberry Pi 5 completes feature extraction + analysis
    ↓ (nothing)
Tier 3: NO CLOUD - by design
```

### Key Innovation: Feature Partitioning

We systematically partition the 25+ paralinguistic feature set across tiers based on:
- **Computational complexity:** What can ESP32-S3 handle?
- **Quantization tolerance:** What survives INT8?
- **Privacy sensitivity:** What reveals speech content?

| Tier | Features | Rationale |
|------|----------|-----------|
| Edge (ESP32) | MFCC, F0, energy, ZCR | Survives INT8, low-complexity |
| Hub (Pi 5) | Jitter, shimmer, HNR, formants | Requires float32, moderate complexity |
| Hub (Pi 5) | Speaker verification | Model too large for edge |

### Key Insight: XVF3800 as Computational Multiplier

The XVF3800's hardware DSP (AEC, beamforming, noise suppression) **preprocesses audio before the ESP32-S3 sees it**. This means:
- Higher SNR input → better edge feature extraction
- Less edge compute needed for noise robustness
- DoA provides spatial context for free

---

## What Makes This Novel?

### 1. First Zero-Cloud Paralinguistic System
- No heuristic privacy ("we promise not to store audio")
- **Architectural guarantee:** raw audio physically cannot leave ESP32

### 2. Systematic Feature Partitioning Study
- Which features tolerate INT8 quantization?
- What's the accuracy/compute tradeoff per feature?
- How does edge SNR affect feature reliability?

### 3. Heterogeneous Edge Hardware Fusion
- ReSpeaker Lite (simple, cheap) + XVF3800 (advanced DSP)
- Characterize when hardware DSP matters
- Cost-performance tradeoff analysis

### 4. Clinical Validity Under Constraints
- Prove that constrained processing maintains clinical utility
- Correlation with PHQ-9/DSM-5 indicators
- Comparison to cloud baseline

---

## Technical Claims (To Be Validated)

| Claim | Metric | Target |
|-------|--------|--------|
| **C1: Edge extraction is accurate** | MFCC correlation (INT8 vs float32) | r > 0.95 |
| **C2: System is real-time** | End-to-end latency | <6 seconds |
| **C3: Privacy is guaranteed** | Audio reconstruction quality | Unintelligible (STOI < 0.5) |
| **C4: Clinical validity preserved** | AUC-ROC vs cloud baseline | Our 8-feature extractor achieves AUC=0.990 (95% CI: [0.964, 1.000]) compared to eGeMAPS AUC=0.982 (95% CI: [0.940, 1.000]).<br><br>*Note: These results are from a mock dataset and will be updated with results from the TESS dataset.* |
| **C5: Runs on commodity hardware** | Total system cost | <$500 |

---

## Comparison to Prior Work

| System | Architecture | Privacy | Edge Processing | Clinical Validity |
|--------|--------------|---------|-----------------|-------------------|
| Cloud ASR + Features | Cloud only | ❌ Audio uploaded | None | ✅ Full features |
| On-device ASR (Whisper) | Edge only | ✅ Local | Speech-to-text only | ❌ No paralinguistics |
| AudioSense (MobiSys'19) | Hybrid | ⚠️ Some audio | Event detection | ❌ Not clinical |
| **IHearYou (Ours)** | **Hierarchical** | **✅ Zero-cloud** | **Paralinguistic features** | **✅ DSM-5 aligned** |

---

## Framing for Different Venues

### PerCom / IMWUT (Recommended)
**Title:** "Zero-Cloud Paralinguistic Sensing: Hierarchical Edge Processing for Privacy-Preserving Mental Health Monitoring"

**Emphasis:**
- Pervasive computing in the home
- Longitudinal health monitoring
- Privacy-by-architecture
- Real-world deployment

### SenSys / IPSN
**Title:** "Hierarchical Feature Partitioning for Acoustic Sensing on Commodity Edge Hardware"

**Emphasis:**
- Systems contribution: how to partition ML pipelines
- Benchmarking ESP32-S3 capabilities
- Multi-device coordination
- Latency/accuracy tradeoffs

### IEEE IoT Journal
**Title:** "A Zero-Cloud IoT Architecture for Privacy-Preserving Voice-Based Health Monitoring"

**Emphasis:**
- IoT system design
- Complete architecture description
- Security analysis
- Deployment case study

---

## Contribution Bullets (For Paper Abstract)

1. **A hierarchical edge architecture** that enables continuous paralinguistic monitoring with zero cloud dependency, processing all audio within the household boundary.

2. **A systematic feature partitioning framework** that identifies which paralinguistic features can be reliably extracted on INT8-quantized ESP32-S3 microcontrollers versus requiring Raspberry Pi 5 processing.

3. **An empirical characterization** of heterogeneous edge hardware (2-mic ReSpeaker Lite vs 4-mic XVF3800 with hardware DSP) for acoustic feature extraction under real-world noise conditions.

4. **A privacy analysis** demonstrating that transmitted features cannot be used to reconstruct intelligible speech, providing architectural (not policy-based) privacy guarantees.

5. **A deployment study** in N real homes over M weeks, validating system reliability and clinical utility compared to cloud-based baselines.

---

## Why Reviewers Should Care

### For Systems Reviewers
- Novel partitioning problem: how to split ML pipelines across heterogeneous edge tiers
- Real hardware constraints (ESP32-S3 memory, compute, power)
- Practical deployment on commodity hardware (<$500 total)

### For Health/Ubicomp Reviewers
- Addresses #1 barrier to voice-based health monitoring: privacy
- Maintains clinical validity despite constraints
- Deployable in real homes (not just lab demos)

### For Privacy/Security Reviewers
- Architectural guarantee, not policy promise
- Formal analysis of feature reconstruction attacks
- No trusted cloud component

---

## Potential Weaknesses (Acknowledge in Paper)

1. **Accuracy tradeoff exists:** ~5% worse than cloud baseline (but privacy gained)
2. **Limited feature set at edge:** Can't extract all 25+ features on ESP32-S3
3. **Requires local hub:** Pi 5 is still needed (can't do fully edge-only)
4. **Single-household scope:** Doesn't address multi-home or population-level analysis

### Mitigation
- Frame accuracy tradeoff as acceptable for privacy gain
- Show which features matter most for clinical validity
- Pi 5 is cheap (<$100) and stays in home
- Population analysis is future work (federated learning)

---

## Related Work Categories

1. **Edge Speech Processing**
   - TinyML for keyword spotting
   - On-device ASR (Whisper, etc.)
   - Acoustic event detection

2. **Privacy-Preserving Voice Systems**
   - Federated learning for ASR
   - Differential privacy for voice
   - Speaker anonymization

3. **Mental Health Monitoring**
   - Depression detection from speech
   - Longitudinal mood tracking
   - Passive sensing systems

4. **Hierarchical/Split Computing**
   - DNN partitioning for mobile
   - Edge-cloud collaboration
   - Latency-aware inference

**Our position:** At the intersection of (1), (2), and (3), using techniques from (4).
