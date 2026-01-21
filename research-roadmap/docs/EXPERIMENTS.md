# Validation Experiments

## Overview

This document defines the experiments needed to validate the zero-cloud hierarchical architecture. Each experiment has clear success criteria and expected timeline.

---

## Experiment 1: Raspberry Pi 5 Baseline Performance

### Objective
Validate that Pi 5 can handle the full IHearYou processing pipeline.

### Setup
1. Raspberry Pi 5 8GB with NVMe SSD
2. Current IHearYou Docker stack ported to ARM64
3. Pre-recorded test audio files (TESS or RAVDESS)

### Procedure
```bash
# 1. Deploy Docker stack
cd /home/rodrigues/depression-detection
docker-compose -f docker-compose.pi5.yml up -d

# 2. Run benchmark script
cd research-roadmap/experiments
python benchmark_pi5_baseline.py \
    --audio-dir /path/to/test/audio \
    --num-streams 1 4 8 \
    --iterations 100

# 3. Collect metrics
python collect_metrics.py --output results/pi5_baseline.json
```

### Metrics to Measure
| Metric | Measurement Method | Target |
|--------|-------------------|--------|
| Feature extraction latency | Time from audio input to features output | <500ms |
| Memory usage | `docker stats` over 1 hour | <4GB |
| CPU utilization | `htop` logging | <80% sustained |
| Concurrent streams | Increase until drops | ≥4 streams |
| Dashboard responsiveness | Page load time | <2s |

### Expected Results
Based on Pi 5's 2-3x performance improvement over Pi 4:
- Feature extraction: 150-300ms (vs 300-500ms on server)
- Memory: 3-4GB (similar to server)
- Concurrent streams: 4-8 without drops

### Success Criteria
- [ ] Feature extraction <500ms for 95th percentile
- [ ] 4 concurrent streams without data loss
- [ ] Memory <4GB sustained over 1 hour
- [ ] Dashboard pages load in <2s

### Timeline
**Week 1-2**

---

## Experiment 2: ESP32-S3 Feature Extraction Feasibility

### Objective
Determine which features can be extracted on ESP32-S3 with acceptable accuracy.

### Setup
1. ReSpeaker Lite with ESP32-S3
2. Edge Impulse or TFLite Micro development environment
3. Test dataset: 100 audio samples with ground truth features

### Procedure
```bash
# 1. Prepare ground truth
cd research-roadmap/experiments
python prepare_ground_truth.py \
    --audio-dir /path/to/test/audio \
    --output ground_truth.json \
    --features mfcc,f0,energy,zcr

# 2. Flash ESP32-S3 firmware
cd ../firmware/respeaker_lite
idf.py build flash

# 3. Collect edge-extracted features
python collect_edge_features.py \
    --board 192.168.1.20 \
    --audio-dir /path/to/test/audio \
    --output edge_features.json

# 4. Compare
python compare_features.py \
    --ground-truth ground_truth.json \
    --edge edge_features.json \
    --output results/edge_accuracy.json
```

### Features to Test

| Feature | Implementation | Expected Accuracy |
|---------|---------------|-------------------|
| MFCC (13 coef) | TFLite Micro INT8 | r > 0.95 |
| F0 mean | Fixed-point YIN | r > 0.90 |
| F0 std | Fixed-point YIN | r > 0.85 |
| RMS energy | Direct computation | r > 0.99 |
| Zero-crossing rate | Direct computation | r > 0.99 |
| Spectral centroid | Fixed-point FFT | r > 0.85 |

### Metrics to Measure
| Metric | Target |
|--------|--------|
| Pearson correlation (MFCC) | r > 0.95 |
| Pearson correlation (F0) | r > 0.90 |
| Mean absolute error | Report for each feature |
| Extraction latency | <100ms per 5s chunk |
| Memory footprint | <200KB models |
| Power consumption | <1W active |

### Success Criteria
- [ ] MFCC correlation r > 0.95
- [ ] F0 mean correlation r > 0.90
- [ ] Extraction completes in <100ms
- [ ] Total model size <200KB

### Timeline
**Week 5-8**

---

## Experiment 3: XVF3800 DSP Quality Assessment

### Objective
Quantify the improvement in feature quality from XVF3800's hardware DSP.

### Setup
1. Co-located ReSpeaker Lite and XVF3800
2. Controlled noise environment (TV, HVAC, conversation)
3. Known speaker at varying distances (1m, 3m, 5m)

### Procedure
```bash
# 1. Record same audio on both devices simultaneously
python record_comparison.py \
    --respeaker 192.168.1.20 \
    --xvf3800 192.168.1.30 \
    --duration 300 \
    --noise-conditions clean,tv,hvac,conversation

# 2. Extract features from both
python extract_features.py \
    --input recordings/ \
    --output features/

# 3. Compare against clean reference
python analyze_dsp_improvement.py \
    --respeaker-features features/respeaker/ \
    --xvf3800-features features/xvf3800/ \
    --reference features/clean/ \
    --output results/dsp_comparison.json
```

### Test Conditions
| Condition | Description | SNR (approx) |
|-----------|-------------|--------------|
| Clean | Quiet room, 1m distance | >30dB |
| TV | Television at normal volume | ~15dB |
| HVAC | Air conditioning running | ~20dB |
| Conversation | Background conversation | ~10dB |
| Far-field | Speaker at 5m | ~15dB |

### Metrics to Measure
| Metric | Measurement |
|--------|-------------|
| Feature correlation vs clean | Per condition |
| F0 tracking accuracy | % frames with valid F0 |
| SNR improvement | dB gained by XVF3800 DSP |
| DoA accuracy | Degrees error vs ground truth |

### Expected Results
- XVF3800 should show 10-20dB SNR improvement in noisy conditions
- F0 tracking should be more reliable (fewer dropouts)
- DoA accuracy within ±15° at 3m distance

### Success Criteria
- [ ] XVF3800 maintains r > 0.90 for MFCC at 10dB SNR
- [ ] ReSpeaker degrades to r < 0.80 at 10dB SNR
- [ ] DoA error <20° at 3m distance
- [ ] XVF3800 shows ≥10dB effective SNR improvement

### Timeline
**Week 9-10**

---

## Experiment 4: End-to-End Latency Measurement

### Objective
Measure total latency from speech to indicator score in hierarchical architecture.

### Setup
1. Full system: 4 ReSpeaker + 4 XVF3800 + Pi 5
2. Synchronized timestamps across all devices (NTP)
3. Test utterances with known start times

### Procedure
```bash
# 1. Synchronize clocks
python sync_clocks.py --devices all

# 2. Run latency test
python measure_e2e_latency.py \
    --boards 192.168.1.20-27 \
    --hub 192.168.1.10 \
    --test-audio /path/to/test.wav \
    --iterations 50 \
    --output results/e2e_latency.json

# 3. Analyze breakdown
python analyze_latency.py \
    --input results/e2e_latency.json \
    --output results/latency_breakdown.json
```

### Latency Stages to Measure
| Stage | Start Event | End Event | Target |
|-------|-------------|-----------|--------|
| Audio capture | Sound produced | Buffer full | 5000ms (fixed) |
| Edge processing | Buffer full | Features sent | <100ms |
| Network transit | Features sent | Features received | <50ms |
| Hub processing | Features received | Indicators computed | <500ms |
| **Total** | Sound produced | Indicators ready | **<5650ms** |

### Success Criteria
- [ ] Edge processing <100ms (p95)
- [ ] Network transit <50ms (p95)
- [ ] Hub processing <500ms (p95)
- [ ] Total E2E <6000ms (p95)
- [ ] No dropped features at 8 concurrent devices

### Timeline
**Week 11-12**

---

## Experiment 5: Clinical Validity Comparison

### Objective
Validate that hierarchical edge processing maintains clinical validity.

### Setup
1. TESS dataset (or DAIC-WOZ if accessible)
2. Both architectures: current server-based and new hierarchical
3. Ground truth: emotion labels or PHQ scores

### Procedure
```bash
# 1. Process dataset with server architecture
python process_dataset.py \
    --arch server \
    --dataset /path/to/tess \
    --output results/server_features.json

# 2. Process dataset with hierarchical architecture
python process_dataset.py \
    --arch hierarchical \
    --dataset /path/to/tess \
    --output results/hierarchical_features.json

# 3. Train classifiers on both
python train_classifier.py \
    --features results/server_features.json \
    --output models/server_classifier.pkl

python train_classifier.py \
    --features results/hierarchical_features.json \
    --output models/hierarchical_classifier.pkl

# 4. Compare clinical metrics
python compare_clinical.py \
    --server-model models/server_classifier.pkl \
    --hier-model models/hierarchical_classifier.pkl \
    --test-set /path/to/test \
    --output results/clinical_comparison.json
```

### Metrics to Measure
| Metric | Description | Target |
|--------|-------------|--------|
| AUC-ROC | Classification performance | Within 5% of server |
| Indicator correlation | Per-indicator score correlation | r > 0.95 |
| Sensitivity | True positive rate | Within 5% of server |
| Specificity | True negative rate | Within 5% of server |

### Success Criteria
- [ ] AUC-ROC within 5% of server baseline
- [ ] Per-indicator correlation r > 0.95
- [ ] Sensitivity within 5%
- [ ] Specificity within 5%

### Timeline
**Week 13-14**

---

## Experiment 6: Privacy Validation (Audio Reconstruction Attack)

### Objective
Verify that transmitted features cannot be used to reconstruct intelligible audio.

### Setup
1. Feature set: MFCCs + F0 + energy (what leaves edge device)
2. State-of-the-art vocoder (Griffin-Lim, WaveGlow, or HiFi-GAN)
3. Human evaluation panel

### Procedure
```bash
# 1. Extract features as they would be transmitted
python extract_edge_features.py \
    --audio /path/to/test/audio \
    --output transmitted_features.json

# 2. Attempt reconstruction with multiple methods
python reconstruct_audio.py \
    --features transmitted_features.json \
    --method griffin-lim \
    --output reconstructed/griffin-lim/

python reconstruct_audio.py \
    --features transmitted_features.json \
    --method waveglow \
    --output reconstructed/waveglow/

# 3. Measure intelligibility
python measure_intelligibility.py \
    --original /path/to/test/audio \
    --reconstructed reconstructed/ \
    --output results/intelligibility.json

# 4. Human evaluation (optional)
# Play reconstructed audio to listeners, ask them to transcribe
```

### Metrics to Measure
| Metric | Description | Target |
|--------|-------------|--------|
| PESQ | Perceptual speech quality | <1.5 (bad quality) |
| STOI | Short-time objective intelligibility | <0.5 (unintelligible) |
| WER | Word error rate on ASR | >90% (mostly wrong) |
| Human transcription | % words correctly transcribed | <20% |

### Success Criteria
- [ ] Reconstructed audio has PESQ <1.5
- [ ] STOI <0.5 (unintelligible)
- [ ] ASR WER >90% (essentially random)
- [ ] Human listeners cannot transcribe >20% of words

### Timeline
**Week 15-16**

---

## Experiment 7: Real-Home Deployment Study

### Objective
Validate system performance in real home environments.

### Setup
1. 3-5 volunteer homes (or simulated home environments)
2. Full system deployed per home
3. 1-2 week data collection period

### Procedure
```bash
# 1. Deploy system
./deploy_home.sh --home-id home_001 --config configs/home_001.yaml

# 2. Monitor remotely (local network access only)
python monitor_deployment.py \
    --homes home_001,home_002,home_003 \
    --duration 14d \
    --output logs/

# 3. Analyze collected data
python analyze_deployment.py \
    --logs logs/ \
    --output results/deployment_analysis.json
```

### Metrics to Measure
| Metric | Description | Target |
|--------|-------------|--------|
| Uptime | % time system operational | >95% |
| Usable speech | Hours/day of captured speech | >30 min |
| Gatekeeper rejection | % audio filtered out | 60-90% |
| False negatives | Target speech incorrectly rejected | <10% |
| Indicator stability | Day-to-day variance | Reasonable trends |

### Data to Collect
- System logs (no audio)
- Feature statistics (aggregated)
- Indicator scores over time
- User experience feedback (survey)

### Success Criteria
- [ ] System uptime >95%
- [ ] Captured >30 min usable speech per day
- [ ] Gatekeeper false negative rate <10%
- [ ] No system crashes over 1 week
- [ ] User satisfaction >3/5

### Timeline
**Week 19-20**

### Ethical Considerations
- IRB approval required for human subjects
- Clear informed consent for participants
- Data minimization: no audio stored
- Right to withdraw at any time
- Local-only data (no researcher access to raw features)

---

## Summary: Experiment Timeline

| Week | Experiment | Key Deliverable |
|------|------------|-----------------|
| 1-2 | Pi 5 Baseline | Performance benchmarks |
| 5-8 | ESP32-S3 Features | Accuracy report |
| 9-10 | XVF3800 DSP Quality | Comparison report |
| 11-12 | E2E Latency | Latency breakdown |
| 13-14 | Clinical Validity | Validation metrics |
| 15-16 | Privacy (Reconstruction) | Privacy proof |
| 19-20 | Real-Home Deployment | Deployment report |

---

## Experiment Scripts Directory Structure

```
research-roadmap/
├── experiments/
│   ├── benchmark_pi5_baseline.py
│   ├── prepare_ground_truth.py
│   ├── collect_edge_features.py
│   ├── compare_features.py
│   ├── record_comparison.py
│   ├── analyze_dsp_improvement.py
│   ├── measure_e2e_latency.py
│   ├── analyze_latency.py
│   ├── process_dataset.py
│   ├── train_classifier.py
│   ├── compare_clinical.py
│   ├── extract_edge_features.py
│   ├── reconstruct_audio.py
│   ├── measure_intelligibility.py
│   ├── deploy_home.sh
│   ├── monitor_deployment.py
│   └── analyze_deployment.py
├── results/
│   └── (experiment outputs)
└── configs/
    └── (deployment configurations)
```
