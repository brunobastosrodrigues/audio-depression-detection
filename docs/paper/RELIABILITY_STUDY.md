# Redundant Heterogeneous Acoustic Arrays for Reliable In-Home Vocal Biomarkers
## Study Design — One-Page Overview

---

### 1. Thesis

We measure the **measurement reliability** of vocal acoustic features (jitter, shimmer, MFCCs, energy statistics, speech timing) captured by a redundant heterogeneous microphone array deployed in a real home — not clinical depression detection, not biomarker efficacy; exclusively reliability and confidence estimation of the sensing pipeline itself.

---

### 2. Contributions

1. **System & Deployment** — End-to-end open-source deployment: ReSpeaker Lite + XVF3800 nodes, ESP32-S3 gateway, MQTT plug-and-play, Docker Compose server stack with VAD, feature extraction, and MongoDB timeseries storage.

2. **On-the-fly Cross-Device Feature Validation (Sensor Jury / Calibrated Confidence)** — At inference time, features from all co-located nodes are compared; a calibrated confidence score flags unreliable captures without requiring any ground-truth label from the environment.

3. **Empirical Reliability & Heterogeneity Study via Hardware-in-the-Loop (HIL) Replay** — TESS/DAIC-WOZ audio clips are played through in-situ speakers and simultaneously captured across the full array, providing absolute error ground truth that is independent of speaker behavior and environmental confounds.

4. **Open Dataset & Reproducible Deployment** — Anonymized multi-node feature logs (no raw audio), full firmware + server source code, and Docker Compose one-command deployment released publicly.

---

### 3. Hardware

| Component | Model | Mics | Role |
|---|---|---|---|
| Near-field array node | ReSpeaker Lite (x4) | 2-mic | Co-located + multi-room coverage |
| Far-field array node | XVF3800 (x4) | 4-mic beamforming | Multi-room coverage |
| Gateway / edge MCU | ESP32-S3 | — | MQTT broker relay, VAD pre-gate |
| Transport | MQTT over LAN | — | Plug-and-play node discovery |
| Server | Docker Compose (Raspberry Pi / NUC) | — | VAD, feature extraction, MongoDB |

**Placement:** co-located cluster (living room) + distributed nodes (bedroom, kitchen, hallway); all nodes observe same acoustic events in co-located condition.

---

### 4. Experiment Matrix

| # | Experiment | What It Measures | Primary Metric | Ground Truth Source | Data Source | STATUS |
|---|---|---|---|---|---|---|
| E1 | **Inter-device reliability** | Feature agreement across simultaneous same-room captures | ICC(3,1) per feature; Bland-Altman 95% LoA | Co-located node pair agreement | Live deployment logs | READY (blocked on enrollment + VAD calibration) |
| E2 | **HIL replay — absolute error** | Absolute feature error vs known stimulus | MAE / RMSE per feature vs reference extract | TESS + DAIC-WOZ clips replayed through in-situ speaker, captured across array | HIL rig (node acts as speaker) | **BLOCKED** — needs speaker-playback firmware on one node |
| E3 | **Distance / condition sweep** | Feature degradation vs source distance and noise condition | ICC & MAE vs distance; SNR proxy | Fixed reading at 1 / 2 / 4 / 6 m; quiet / TV-noise / kitchen-noise | Scripted protocol, volunteer reader | READY (protocol designed, execution pending) |
| E4 | **Jury calibration** (money result) | Does cross-device feature disagreement predict capture error? | Calibration curve (reliability score vs MAE from HIL ground truth); ECE | HIL replay (E2) as label | Combination of E1 logs + E2 HIL labels | BLOCKED (depends on E2) |
| E5 | **Test-retest — daily fixed reading** | Within-person, within-node feature stability over days | CV%; SEM; ICC across sessions | Repeated known reading (same text, same node, same time of day) | Daily scripted sessions, enrolled participant | READY (enrollment blocking) |
| E6 | **Systems tradeoff A/B/C** | Accuracy vs compute vs latency across extraction configs | Feature-level accuracy (vs HIL), CPU%, extraction latency ms | HIL replay | Server profiling logs + E2 HIL labels | BLOCKED (depends on E2) |
| E7 | **Deployment / fleet health** | Long-run uptime, reboot rate, packet loss, VAD false-positive rate | MTBF; reboot count/week; speech-gate FP rate | Operational logs (already streaming) | MongoDB `node_heartbeats`, dropped-segment logs, `speech_daily_features` | **DATA ALREADY COLLECTING** |

---

### 5. Honest Current Status

**Already built and running:**
- Server-side WebRTC VAD speech gate (aggressiveness=2) — live, gating feature extraction
- Feature extraction pipeline (MFCCs, jitter/shimmer, energy, speech timing) — live
- Behavioral-trace pipeline (`mine_behavior_trace.py`) — presence/absence from dropped-segment logs
- Speech quantity & timing analytics (`speech_daily_features.py`) per user/day
- Fleet heartbeat + reboot instrumentation — data collecting now (feeds E7 directly)

**Blocking items (honest):**
- **Enrollment** — no real participants yet; E1/E3/E5 need consented users producing real speech
- **VAD calibration** — overnight fault discovered during deployment: VAD was triggering on non-speech; server-side gate partially mitigates; calibration protocol still needed
- **Speaker-playback firmware** — one node must act as a calibrated speaker for E2/E4/E6; not yet implemented
- **IRB / ethics approval** — required before enrollment (in progress)

**Lessons-from-deployment result (already reportable):**
The overnight VAD false-positive fault, its discovery via behavioral-trace anomaly detection, and its partial remediation via server-side gating constitute a concrete reliability failure mode and recovery case study — publishable regardless of enrollment status.

---

### 6. Target Venue

| Priority | Venue | Rationale |
|---|---|---|
| Primary | **ACM IMWUT** (Ubicomp) | Best fit: in-home sensing, reliability, deployment study |
| Alternate 1 | ACM TIOT | Broader IoT systems audience |
| Alternate 2 | IEEE Sensors Journal | Hardware + measurement focus |

Submission target: IMWUT vol. closest to 12 months post-enrollment completion.

---

### 7. Planned Figures (6–8)

| Fig | Description |
|---|---|
| F1 | System architecture diagram — nodes, ESP32-S3 gateway, MQTT, server stack, MongoDB |
| F2 | Physical deployment floor plan — node placement, distances, room labels |
| F3 | Inter-device ICC heatmap — ICC(3,1) per feature × node-pair (E1) |
| F4 | Bland-Altman plots — 3–4 key features, co-located node pairs (E1) |
| F5 | HIL replay pipeline diagram — speaker node → array → feature extraction → MAE vs reference |
| F6 | Jury calibration curve — cross-device disagreement score vs absolute error (E4, money result) |
| F7 | Distance × condition degradation plot — ICC / MAE vs distance per noise condition (E3) |
| F8 | Fleet health dashboard — uptime, reboot events, VAD FP rate, speech volume over deployment time (E7) |

---

*Last updated: 2026-07-10. Status column reflects actual implementation state; figures marked BLOCKED require HIL firmware before execution.*
