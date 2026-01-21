# Research Roadmap: Zero-Cloud Paralinguistic Sensing

## Overview

**Goal:** Demonstrate that clinically-relevant paralinguistic features for mental health monitoring can be extracted entirely within a household using commodity hardware, with no cloud dependency.

**Timeline:** 6 months (January - June 2026)

---

## Phase 1: Foundation (Weeks 1-4)
### Objective: Validate Pi 5 as capable home hub

#### Week 1-2: Pi 5 Baseline Setup
- [ ] Set up Raspberry Pi 5 with Raspberry Pi OS 64-bit
- [ ] Install Docker + Docker Compose
- [ ] Port current IHearYou Docker stack to Pi 5
- [ ] Benchmark baseline performance:
  - [ ] Feature extraction latency (25 features)
  - [ ] MongoDB query performance
  - [ ] Streamlit dashboard responsiveness
  - [ ] Memory usage under load

**Deliverable:** Performance report comparing Pi 5 vs current cloud server

#### Week 3-4: Optimize for Pi 5
- [ ] Profile bottlenecks (CPU, memory, I/O)
- [ ] Optimize OpenSMILE configuration for ARM64
- [ ] Evaluate alternative extractors (librosa vs opensmile vs custom)
- [ ] Implement model quantization for Resemblyzer (speaker verification)
- [ ] Test with 4 simultaneous audio streams

**Deliverable:** Optimized Docker stack achieving <500ms feature extraction

**Success Criteria:**
- Feature extraction: <500ms per 5-second chunk
- 4 concurrent streams without dropped frames
- Memory usage <4GB sustained
- Dashboard responsive (<2s page load)

---

## Phase 2: Edge Feature Extraction (Weeks 5-10)
### Objective: Move basic features to ESP32-S3

#### Week 5-6: ESP32-S3 Development Environment
- [ ] Set up ESP-IDF 5.x development environment
- [ ] Flash test firmware to ReSpeaker Lite
- [ ] Flash test firmware to XVF3800
- [ ] Establish MQTT communication with Pi 5
- [ ] Benchmark ESP32-S3 capabilities:
  - [ ] Memory available for ML models
  - [ ] CPU cycles for audio processing
  - [ ] Power consumption

**Deliverable:** Working ESP32-S3 development pipeline

#### Week 7-8: TinyML Feature Extractors
- [ ] Implement VAD on ESP32-S3 (Silero or custom)
- [ ] Implement MFCC extraction (13 coefficients, INT8)
  - [ ] Use TensorFlow Lite Micro or Edge Impulse
  - [ ] Benchmark accuracy vs float32 server extraction
- [ ] Implement F0 (pitch) extraction
  - [ ] Evaluate YIN algorithm in fixed-point
  - [ ] Alternative: autocorrelation-based approach
- [ ] Implement RMS energy computation

**Deliverable:** Edge feature extraction running on ESP32-S3

#### Week 9-10: Feature Validation
- [ ] Compare edge-extracted features vs server-extracted features
- [ ] Dataset: RAVDESS, TESS, or custom recordings
- [ ] Metrics:
  - [ ] Pearson correlation (target: r > 0.95)
  - [ ] Mean absolute error
  - [ ] Clinical validity (correlation with PHQ-9)
- [ ] Characterize which features degrade under quantization
- [ ] Document feature-specific accuracy tradeoffs

**Deliverable:** Validation report with accuracy measurements

**Success Criteria:**
- MFCC correlation: r > 0.95 (INT8 vs float32)
- F0 correlation: r > 0.90
- Edge extraction latency: <100ms per 5-second chunk
- Memory footprint: <200KB for all edge models

---

## Phase 3: Hierarchical Integration (Weeks 11-14)
### Objective: Integrate edge and hub processing

#### Week 11-12: Protocol Design
- [ ] Define edge-to-hub message format (protobuf or msgpack)
- [ ] Implement feature aggregation on Pi 5
- [ ] Handle missing features gracefully (edge extraction failed)
- [ ] Implement feature fusion logic:
  - [ ] Edge features: MFCC, F0, energy
  - [ ] Hub features: jitter, shimmer, HNR, formants
- [ ] Test with heterogeneous hardware (ReSpeaker + XVF3800)

**Deliverable:** Working hierarchical pipeline

#### Week 13-14: End-to-End Validation
- [ ] Full pipeline test: speech → edge → hub → indicator scores
- [ ] Measure end-to-end latency
- [ ] Validate clinical output against current server-based system
- [ ] Stress test: 8 devices simultaneously
- [ ] Document failure modes and recovery

**Deliverable:** Integrated system demonstration

**Success Criteria:**
- End-to-end latency: <6 seconds (including 5s audio chunk)
- 8 concurrent devices without data loss
- Indicator score correlation: r > 0.98 vs server baseline

---

## Phase 4: Privacy Hardening (Weeks 15-18)
### Objective: Formalize and validate privacy guarantees

#### Week 15-16: Privacy Analysis
- [ ] Formal data flow documentation
- [ ] Audio reconstruction attack evaluation:
  - [ ] Can MFCC + F0 reconstruct intelligible speech?
  - [ ] Literature review on MFCC inversion
  - [ ] Empirical test with vocoder-based reconstruction
- [ ] Implement additional privacy mechanisms (optional):
  - [ ] Local differential privacy on features
  - [ ] Feature perturbation for speaker anonymization

**Deliverable:** Privacy analysis report

#### Week 17-18: Security Implementation
- [ ] Implement Pi 5 air-gap configuration
- [ ] Full disk encryption on Pi 5
- [ ] Local-only dashboard authentication
- [ ] MQTT encryption (TLS) within home network
- [ ] Document threat model and mitigations

**Deliverable:** Security hardened deployment configuration

**Success Criteria:**
- Documented proof that raw audio never leaves ESP32
- MFCC reconstruction produces unintelligible audio
- Pi 5 passes security audit (no internet connectivity)

---

## Phase 5: Evaluation & Paper (Weeks 19-24)
### Objective: Rigorous evaluation and paper writing

#### Week 19-20: Deployment Study
- [ ] Deploy in 3-5 real homes (or simulated home environments)
- [ ] Collect 1-2 weeks of continuous data per home
- [ ] Measure:
  - [ ] Hours of usable speech captured per day
  - [ ] Gatekeeper rejection rates
  - [ ] System uptime and reliability
  - [ ] User experience feedback

**Deliverable:** Deployment study data

#### Week 21-22: Benchmarking
- [ ] Comparative evaluation:
  - [ ] Zero-cloud (proposed) vs cloud-based (baseline)
  - [ ] Latency comparison
  - [ ] Accuracy comparison
  - [ ] Power consumption
- [ ] Ablation study:
  - [ ] Edge-only vs hierarchical vs hub-only
  - [ ] Feature subset analysis
- [ ] Create benchmark dataset and release

**Deliverable:** Comprehensive benchmark results

#### Week 23-24: Paper Writing
- [ ] Target: IEEE PerCom 2026 or ACM IMWUT
- [ ] Sections:
  - [ ] Introduction: Privacy-first mental health monitoring
  - [ ] Related Work: Edge ML, speech sensing, privacy
  - [ ] Architecture: Three-tier hierarchical design
  - [ ] Implementation: Hardware and software details
  - [ ] Evaluation: Accuracy, latency, privacy, deployment
  - [ ] Discussion: Limitations and future work
- [ ] Figures:
  - [ ] System architecture diagram
  - [ ] Feature partitioning analysis
  - [ ] Latency breakdown
  - [ ] Privacy analysis

**Deliverable:** Paper draft ready for submission

---

## Milestones Summary

| Week | Milestone | Deliverable |
|------|-----------|-------------|
| 4 | Pi 5 validated | Performance report |
| 8 | Edge features working | ESP32 firmware |
| 10 | Features validated | Accuracy report |
| 14 | System integrated | Demo video |
| 18 | Privacy hardened | Security audit |
| 22 | Evaluation complete | Benchmark data |
| 24 | Paper submitted | PerCom/IMWUT submission |

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ESP32-S3 memory insufficient | Medium | High | Use XVF3800's XMOS for heavy DSP; simplify edge models |
| F0 extraction degrades significantly | Medium | Medium | Accept hub-only F0 extraction as fallback |
| Pi 5 cannot handle 8 streams | Low | High | Reduce feature set; optimize parallelization |
| MFCC inversion attack succeeds | Low | High | Add differential privacy; increase compression |
| Real-home deployment blocked (IRB) | Medium | Medium | Use lab simulation; synthetic data |

---

## Resources Required

### Hardware
- 1x Raspberry Pi 5 8GB + NVMe SSD + cooling
- 4x ReSpeaker Lite (already available)
- 4x XVF3800 (already available)
- Local WiFi router
- Test microphones for validation

### Software/Services
- Edge Impulse account (free tier sufficient)
- No cloud services required (by design)

### Time
- Estimated: 20-30 hours/week for 24 weeks
- Peak effort: Weeks 7-10 (edge development), 23-24 (paper writing)

---

## Success Metrics (Paper-Ready)

| Metric | Target | Stretch Goal |
|--------|--------|--------------|
| Edge extraction latency | <100ms | <50ms |
| Hub processing latency | <500ms | <200ms |
| End-to-end latency | <6s | <2s |
| Feature accuracy (MFCC) | r > 0.95 | r > 0.98 |
| Feature accuracy (F0) | r > 0.90 | r > 0.95 |
| Clinical validity | within 5% of cloud | within 2% |
| Concurrent devices | 8 | 16 |
| Memory (Pi 5) | <4GB | <2GB |
| Deployment duration | 1 week | 4 weeks |
| Homes deployed | 3 | 10 |
