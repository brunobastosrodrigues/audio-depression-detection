# Technical Focus: Feasibility, Not Clinical Claims

## Reframed Research Question

**NOT:** "Can we detect depression using edge devices?"

**YES:** "What is the technical feasibility of extracting paralinguistic features—sufficient for downstream clinical research—entirely on commodity hardware within household boundaries?"

---

## Two Core Technical Claims

### Claim A: Data Collection Capability
> We can collect the paralinguistic features **required** for clinical evaluation (as established by prior literature) without requiring cloud infrastructure.

**What we prove:**
- Feature completeness: We extract the same features used in published clinical studies
- Feature accuracy: Our edge-extracted features correlate highly with reference implementations
- No evaluation of clinical validity ourselves—that's for clinicians

### Claim B: Privacy Architecture
> No data whatsoever leaves the household premises. Metadata only upon explicit authorization.

**What we prove:**
- Architectural guarantee: Raw audio physically cannot exit the ESP32-S3
- Transmitted data (features) cannot reconstruct intelligible speech
- All processing happens on commodity hardware within the home

---

## Why This Framing Is Stronger

| Clinical Framing (Weak) | Technical Framing (Strong) |
|------------------------|---------------------------|
| "We detect depression" | "We extract depression-relevant features" |
| Requires IRB, clinical validation | Requires only technical benchmarks |
| Reviewers ask about sensitivity/specificity | Reviewers ask about latency/accuracy |
| Must compare to clinical gold standard | Compare to reference feature extractors |
| Evaluation: expensive, long-term study | Evaluation: controlled experiments |

---

## Technical Questions We Answer

### Q1: Feature Completeness
> Which paralinguistic features have been used in depression/mental health research, and can we extract them?

| Feature Family | Clinical Usage (Literature) | Our Capability |
|---------------|---------------------------|----------------|
| Pitch (F0) statistics | Cummins et al. 2015, Low et al. 2011 | ✅ Edge + Hub |
| MFCC coefficients | Alghowinem et al. 2013 | ✅ Edge |
| Jitter/Shimmer | Cannizzaro et al. 2004 | ⚠️ Hub only |
| Speaking rate | Mundt et al. 2012 | ✅ Hub |
| Pause patterns | Trevino et al. 2011 | ✅ Hub |
| Energy dynamics | Ozdas et al. 2004 | ✅ Edge |
| Formants | Moore et al. 2008 | ⚠️ Hub only |
| HNR/CPP | Scherer et al. 2016 | ⚠️ Hub only |

**Claim:** We can extract **all major feature families** used in clinical literature, with some requiring hub processing.

### Q2: Feature Accuracy vs Reference
> How accurate are our edge-extracted features compared to established tools?

| Feature | Reference Tool | Target Correlation |
|---------|---------------|-------------------|
| MFCC | librosa/OpenSMILE | r > 0.95 |
| F0 | Praat/REAPER | r > 0.90 |
| Energy | librosa | r > 0.99 |
| Jitter/Shimmer | Praat | r > 0.85 |

**We do NOT claim:** These features predict depression (clinical claim)
**We DO claim:** Our features match reference implementations (technical claim)

### Q3: Hardware Boundaries
> What are the limits of each hardware tier?

See detailed analysis below.

### Q4: Privacy Guarantee
> What data can be extracted from transmitted features?

- MFCC inversion produces unintelligible audio (STOI < 0.5)
- F0 + energy cannot recover speech content
- Formal analysis of reconstruction attacks

---

## Hardware Capability Analysis

### Tier 1A: ReSpeaker Lite (ESP32-S3)

**Specifications:**
- CPU: Dual-core Xtensa LX7 @ 240MHz
- SRAM: 512KB
- PSRAM: 8MB
- Mics: 2x digital MEMS
- Price: ~$15

**What It Can Do:**
| Task | Feasibility | Memory | Latency |
|------|-------------|--------|---------|
| Audio capture (16kHz) | ✅ Excellent | 160KB/5s | Real-time |
| VAD (Silero INT8) | ✅ Good | ~40KB model | <15ms/frame |
| MFCC (13 coef, INT8) | ✅ Good | ~50KB | <50ms/5s |
| F0 (autocorrelation) | ✅ Moderate | ~20KB | <30ms/5s |
| RMS/ZCR | ✅ Trivial | <1KB | <5ms |

**What It Cannot Do:**
| Task | Reason |
|------|--------|
| Jitter/Shimmer | Requires precise F0 tracking, float32 |
| Formants | LPC analysis too heavy |
| Speaker verification | Model too large (~50MB) |
| Noise suppression | No hardware DSP |

**Edge Budget (ReSpeaker Lite):**
```
Available SRAM: ~300KB after system overhead
- Audio buffer: 160KB (5 seconds)
- VAD model: 40KB
- MFCC model: 50KB
- F0 buffer: 20KB
- Remaining: 30KB ✓
```

### Tier 1B: XVF3800 (XMOS + ESP32-S3)

**Specifications:**
- Voice Processor: XMOS xcore.ai (dedicated DSP)
- MCU: ESP32-S3 (same as ReSpeaker)
- Mics: 4x digital MEMS
- DSP: AEC, beamforming, noise suppression, DoA
- Price: ~$40

**Advantages Over ReSpeaker Lite:**
| Capability | ReSpeaker Lite | XVF3800 |
|------------|----------------|---------|
| Microphones | 2 | 4 |
| Far-field range | ~2m | ~5m |
| Noise suppression | ❌ None | ✅ Hardware |
| Echo cancellation | ❌ None | ✅ Hardware |
| Beamforming | ❌ None | ✅ Hardware (3 beams) |
| Direction of Arrival | ❌ None | ✅ 360° |
| Multi-speaker | Poor | 2 focused beams |

**XVF3800 DSP Output:**
The XMOS processor outputs **preprocessed audio** to ESP32-S3:
- Noise-suppressed
- Echo-cancelled
- Beamformed (focused on speaker)
- Gain-normalized

**Implication:** ESP32-S3 on XVF3800 receives **cleaner input**, so:
- Edge feature extraction is more reliable
- Can achieve higher accuracy in noisy environments
- DoA provides spatial context for free

**Closed Access Limitation:**
The XMOS DSP is a black box—we can only use its output, not modify its algorithms. This is fine for our purposes but limits customization.

### Tier 2: Raspberry Pi 5 (Home Hub)

**Specifications:**
- CPU: Quad-core Arm Cortex-A76 @ 2.4GHz
- RAM: 8GB LPDDR4X
- Storage: NVMe SSD (via HAT)
- Price: ~$80 + accessories

**Computational Capacity:**
Based on benchmarks ([Raspberry Pi](https://www.raspberrypi.com/news/benchmarking-raspberry-pi-5/), [Seeed Studio](https://www.seeedstudio.com/blog/2023/09/28/raspberry-pi-5-vs-pi-4-ai-performance-cpu-benchmark-how-much-leap-forward/)):

| Benchmark | Pi 4 | Pi 5 | Improvement |
|-----------|------|------|-------------|
| Geekbench 6 (single) | ~320 | ~774 | 2.4x |
| Geekbench 6 (multi) | ~850 | ~1800 | 2.1x |
| ncnn YOLOv8n | ~5 fps | ~12 fps | 2.4x |
| TFLite inference | Baseline | ~2.5x | 2.5x |

**Estimated IHearYou Tasks on Pi 5:**
| Task | Estimated Latency | Memory |
|------|------------------|--------|
| OpenSMILE eGeMAPS (25 features) | 100-200ms | ~200MB |
| Resemblyzer speaker verification | 50-100ms | ~100MB |
| Jitter/Shimmer (Praat-style) | 20-50ms | ~50MB |
| HNR/CPP computation | 10-30ms | ~30MB |
| Formant extraction | 30-50ms | ~50MB |
| EMA temporal modeling | <10ms | Negligible |
| MongoDB operations | <50ms | ~500MB |
| **Total per chunk** | **200-400ms** | **~1GB** |

**I/O Boundaries:**
| Interface | Capacity | Our Usage |
|-----------|----------|-----------|
| WiFi (802.11ac) | ~400 Mbps | <1 Mbps (features only) |
| RAM | 8GB | ~2-3GB used |
| NVMe SSD | ~500 MB/s | Negligible (features are tiny) |
| CPU | 4 cores | 2-3 cores for processing |

**Bottleneck Analysis:**
- **NOT I/O bound:** Feature data is tiny (~200 bytes/utterance)
- **NOT memory bound:** 8GB is plenty for all models
- **CPU bound:** Feature extraction uses most CPU
- **Pi 5 can handle 8+ concurrent streams** based on estimates

### Pushing Pi 5 Boundaries

**What would saturate Pi 5?**
| Scenario | CPU Usage | Feasible? |
|----------|-----------|-----------|
| 4 streams, full features | ~50% | ✅ Yes |
| 8 streams, full features | ~80% | ✅ Yes |
| 16 streams, full features | ~160% | ⚠️ Throttled |
| 8 streams + real-time dashboard | ~90% | ✅ Yes |

**To push further:**
1. Use PyTorch with ARM optimizations (NEON)
2. Quantize Resemblyzer to INT8
3. Use multiprocessing (all 4 cores)
4. Consider Hailo-8L AI accelerator HAT (+$70, 13 TOPS)

---

## Price-Performance Analysis

### Option A: Budget ($200)
- 4x ReSpeaker Lite: $60
- 1x Raspberry Pi 5 4GB: $60
- 1x microSD 64GB: $10
- Accessories: $70

**Capability:** Basic features at edge, full processing at hub, noisy environment performance limited.

### Option B: Balanced ($400)
- 2x ReSpeaker Lite: $30
- 2x XVF3800: $80
- 1x Raspberry Pi 5 8GB: $80
- 1x NVMe HAT + 256GB SSD: $50
- Accessories: $100

**Capability:** Mix of basic and advanced edge devices, robust hub, good noise handling in key rooms.

### Option C: Full ($550)
- 4x XVF3800: $160
- 1x Raspberry Pi 5 8GB: $80
- 1x NVMe HAT + 256GB SSD: $50
- 1x Active cooler: $15
- Accessories: $100
- WiFi router: $30

**Capability:** Best edge performance everywhere, handles noisy environments, spatial tracking via DoA.

### Cost-Accuracy Tradeoff

| Configuration | Edge Accuracy (noisy) | Hub Load | Total Cost |
|---------------|----------------------|----------|------------|
| 4x ReSpeaker | 70-80% | High | $200 |
| 2x ReSpeaker + 2x XVF3800 | 80-90% | Medium | $400 |
| 4x XVF3800 | 90-95% | Low | $550 |

XVF3800's hardware DSP effectively does preprocessing that would otherwise require the hub, reducing hub load and improving overall system efficiency.

---

## Evaluation Strategy (Pure Technical)

### What We Measure
1. **Feature correlation:** Our features vs. reference tools (librosa, Praat, OpenSMILE)
2. **Latency:** End-to-end processing time
3. **Throughput:** Concurrent streams handled
4. **Accuracy vs. noise:** Performance at different SNR levels
5. **Hardware utilization:** CPU, memory, power consumption

### What We Do NOT Claim
1. Clinical validity (requires IRB, longitudinal study)
2. Diagnostic accuracy (requires gold standard labels)
3. Depression detection performance (requires clinical evaluation)

### Evaluation Datasets
- **RAVDESS:** Emotional speech with known labels (technical validation)
- **TESS:** Similar, different speakers
- **Synthetic:** Controlled SNR, speaker distance
- **Real recordings:** Collected in lab (not clinical)

---

## Paper Framing

### Title Options
1. "Technical Feasibility of Zero-Cloud Paralinguistic Feature Extraction on Commodity Edge Hardware"
2. "Hierarchical Edge Processing for Privacy-Preserving Acoustic Sensing: A Technical Analysis"
3. "Pushing the Boundaries of Embedded Speech Processing: Feature Extraction on ESP32-S3 and Raspberry Pi 5"

### Abstract Template
> Longitudinal paralinguistic monitoring has applications in mental health research, but privacy concerns limit deployment. We present a technical analysis of extracting speech features—used in clinical literature—entirely on commodity hardware within household boundaries. We partition 25+ acoustic features across ESP32-S3 edge devices and a Raspberry Pi 5 hub, demonstrating that [X]% of features can be accurately extracted at the edge (r > 0.95 vs. reference) with [Y]ms latency. We characterize the accuracy-compute tradeoff between low-cost 2-mic arrays (ReSpeaker Lite) and advanced 4-mic DSP systems (XVF3800), showing [finding]. Our privacy analysis confirms that transmitted features cannot reconstruct intelligible speech (STOI < 0.5). This work establishes the technical foundation for privacy-preserving acoustic sensing without making clinical claims.

### Contribution Bullets (Technical Only)
1. A systematic characterization of which paralinguistic features survive INT8 quantization on ESP32-S3, with accuracy measurements against reference tools.

2. A hierarchical processing architecture that achieves <[X]ms end-to-end latency for 25+ acoustic features on a Raspberry Pi 5 hub with 8 concurrent edge streams.

3. A comparative analysis of budget (ReSpeaker Lite) vs. advanced (XVF3800) edge hardware, quantifying the accuracy-cost tradeoff under varying noise conditions.

4. A privacy analysis demonstrating that transmitted features cannot be used to reconstruct intelligible speech, validated through reconstruction attacks.

5. An open-source implementation deployable on <$500 commodity hardware, enabling future clinical research without cloud infrastructure.
