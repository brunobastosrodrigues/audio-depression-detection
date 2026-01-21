# IHearYou: Zero-Cloud Paralinguistic Sensing Research Roadmap

## Vision

**Fully local, privacy-preserving mental health monitoring where no data ever leaves the household.**

A hierarchical edge computing architecture that distributes paralinguistic feature extraction across commodity hardware:
- **Tier 1 (Edge):** ESP32-S3 boards with ReSpeaker/XVF3800 - on-device preprocessing
- **Tier 2 (Home Hub):** Raspberry Pi 5 - heavy ML inference and aggregation
- **No Tier 3:** Zero cloud dependency

## Core Research Contribution

**"Hierarchical Edge Processing for Privacy-Preserving Paralinguistic Sensing"**

We demonstrate that clinically-relevant paralinguistic features can be extracted entirely within a household using commodity edge devices, with:
1. Quantified privacy guarantees (no raw audio transmission even within home)
2. Real-time performance (<1s latency from speech to features)
3. Clinical validity within 5% of cloud-based approaches

## Hardware Platform

| Device | Quantity | Role | Compute |
|--------|----------|------|---------|
| ReSpeaker Lite | 4 | Edge capture + basic features | ESP32-S3 (dual-core, 8MB PSRAM) |
| XVF3800 | 4 | Edge capture + DSP + DoA | ESP32-S3 + XMOS xcore.ai |
| Raspberry Pi 5 | 1 | Home hub - heavy inference | Quad-core Cortex-A76 @ 2.4GHz, 8GB RAM |

## Key Documents

- [Architecture](docs/ARCHITECTURE.md) - Technical system design
- [Roadmap](docs/ROADMAP.md) - Research phases and timeline
- [Hardware](docs/HARDWARE.md) - Device capabilities and constraints
- [Experiments](docs/EXPERIMENTS.md) - Validation experiments

## Research Questions

1. **Feature Partitioning:** Which paralinguistic features can run on ESP32-S3 (INT8) vs require Pi 5 (float32)?
2. **Accuracy Preservation:** What is the clinical validity loss from quantization and edge processing?
3. **Latency Budget:** Can we achieve <1s end-to-end with hierarchical processing?
4. **Privacy Quantification:** How do we formally prove no recoverable audio leaves edge devices?

## Target Venues

- **Primary:** IEEE PerCom 2026, ACM IMWUT/UbiComp 2026
- **Secondary:** ACM SenSys 2026, IEEE/ACM IPSN 2026
- **Journal:** IEEE Internet of Things Journal

## Quick Start

```bash
# Phase 1: Benchmark current pipeline on Pi 5
cd experiments/
./benchmark_pi5_baseline.sh

# Phase 2: Test ESP32-S3 feature extraction
cd ../firmware/
# See ESP32 development instructions
```

## Contact

Project Lead: [Your Name]
Created: January 2026
