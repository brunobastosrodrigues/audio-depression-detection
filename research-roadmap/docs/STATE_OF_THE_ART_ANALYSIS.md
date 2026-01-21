# State of the Art: Depression Detection from Voice/Speech on Edge Devices

**Research Report | January 2026**

---

## Executive Summary

Depression detection from voice and speech signals represents a rapidly advancing field at the intersection of affective computing, digital health, and machine learning. This analysis examines the current state of the art, focusing on systems that could potentially run on resource-constrained edge devices.

### Key Findings

1. **Mature Research Domain**: Depression detection from speech has been actively researched since 2013, with significant advances through the AVEC challenge series (2013-2019).

2. **Validated Features Exist**: Acoustic features including jitter, shimmer, MFCC, F0 (pitch), and formants have been clinically validated as depression biomarkers with statistically significant correlations to PHQ-8/PHQ-9 scores.

3. **Gap in Edge Deployment**: While TinyML and edge AI are rapidly maturing for general speech tasks (keyword spotting, emotion recognition), **no published work specifically targets depression detection on microcontrollers** (ESP32, ARM Cortex-M).

4. **Privacy-Preserving Approaches Emerging**: Federated learning for speech-based depression detection has been demonstrated with only 4-6% accuracy loss compared to centralized training.

5. **Opportunity for Novel Contribution**: A resource-efficient, privacy-preserving depression screening system on edge devices represents an unexplored niche with significant clinical and commercial potential.

---

## Table of Related Work

### Depression Detection Systems

| Paper/System | Year | Features | Model | Accuracy/Metric | Hardware/Platform |
|-------------|------|----------|-------|-----------------|-------------------|
| AVEC 2019 Baseline | 2019 | eGeMAPS, openSMILE | SVM | CCC: 0.120 (test) | Server/Cloud |
| Ray et al. (AVEC 2019 Winner) | 2019 | Text (Bi-LSTM + Attention) | Multi-level Attention | CCC: 0.67, RMSE: 4.37 | Server/Cloud |
| wav2vec 2.0 Fine-tuned | 2024 | Self-supervised embeddings | Transformer | Accuracy: 96.49% | GPU Server |
| CNN-to-SNN (DAIC-WOZ) | 2024 | Audio spectrograms | Spiking Neural Network | Accuracy: 82.5%, F1: 0.825 | Neuromorphic (simulated) |
| FL Speech Depression | 2022 | MFCC, eGeMAPS | Federated MLP | 4-6% loss vs centralized | Mobile devices |
| MHDeep Framework | 2022 | Wearable sensors (HRV, EDA) | Efficient DNN | Not speech-specific | Smartphone edge |
| Mon Majhi | 2023 | App usage behavioral | LGBM | 82.4% sensitivity | Smartphone |
| FedTherapist | 2023 | Text + keyboard input | CALL methodology | 0.15 AUROC improvement | Smartphone |
| Multimodal LLM (E-DAIC) | 2024 | Audio + Text + Video | FPT Transformer | RMSE: 4.80, Acc: 79% | Server/Cloud |

### Edge/TinyML Speech Systems (General, Not Depression-Specific)

| System | Year | Task | Model Size | Hardware | Inference Time |
|--------|------|------|------------|----------|----------------|
| TF Lite Micro Speech | 2019 | Keyword Spotting | <20 KB | ARM Cortex-M | ~24 ms |
| Wav2Small | 2024 | Emotion Recognition | 72K params, 9MB RAM | Edge device | Real-time |
| Edge Impulse Audio | 2021 | Audio Classification | Configurable | ESP32, nRF52 | Real-time |
| Speech Emotion TinyML | 2023 | Emotion (LSTM) | Quantized | Arduino Nano 33 | Real-time |

---

## Datasets with Ground-Truth Depression Labels

### Primary Datasets

| Dataset | Size | Labels | Language | Access | Notes |
|---------|------|--------|----------|--------|-------|
| **DAIC-WOZ** | 189 sessions | PHQ-8 (binary + score) | English | Request | Gold standard, AVEC 2016-2017 |
| **E-DAIC** | 275 sessions | PHQ-8, PCL-C | English | Request | Extended version, AVEC 2019 |
| **MODMA** | 53 subjects (24 MDD + 29 HC) | PHQ-9, Clinical diagnosis | Chinese | Free (EULA) | Interview, reading, picture description |
| **CMDC** | 78 participants | Clinical MDD diagnosis | Chinese | IEEE DataPort | Semi-structured interviews |
| **D-vlog** | YouTube videos | Self-reported depression | English | Research | In-the-wild data |

### Dataset Characteristics

- **DAIC-WOZ/E-DAIC**: Most widely used benchmark. Sessions are 7-33 minutes (avg 16 min). Includes audio, video, and transcripts. Class imbalance: ~19-24% depressed.
- **MODMA**: Smaller but clinically validated. 29 audio files per subject across three tasks. PHQ-9 scoring available.
- **CMDC**: Chinese language. 90% F1 achieved on this dataset.

### Evaluation Metrics

- **Binary Classification**: Accuracy, F1-score, Precision, Recall (PHQ-8 >= 10 = depressed)
- **Severity Regression**: RMSE, MAE, CCC (Concordance Correlation Coefficient)

---

## Validated Acoustic Features for Depression Detection

### Tier 1: Clinically Validated (Strong Evidence)

| Feature | Description | Correlation with Depression | Computational Cost |
|---------|-------------|----------------------------|-------------------|
| **Jitter** | F0 period length deviations | Higher in depressed (p<0.001) | Low |
| **Shimmer** | Amplitude perturbation | Higher in depressed (eta-sq=0.066) | Low |
| **F0 (Pitch)** | Fundamental frequency | Reduced variability | Low |
| **F0 SD** | Pitch standard deviation | Higher in depressed | Low |
| **CPPS** | Cepstral Peak Prominence Smoothed | Lower in depressed | Medium |
| **Speech Rate** | Words/syllables per second | Reduced | Low |
| **Pause Frequency** | Number of pauses | Increased | Low |

### Tier 2: Widely Used (Moderate Evidence)

| Feature | Description | Notes | Computational Cost |
|---------|-------------|-------|-------------------|
| **MFCCs (1-13)** | Mel-frequency cepstral coefficients | r=0.32-0.40 correlation | Medium |
| **HNR** | Harmonics-to-Noise Ratio | Voice quality indicator | Medium |
| **Formants (F1-F3)** | Vocal tract resonances | Articulatory precision | Medium |
| **GNE** | Glottal-to-Noise Excitation | Lower in depressed | Medium |
| **Spectral Tilt** | High vs low frequency energy | Lower in depressed | Low |

### Tier 3: Deep Learning Features

| Feature | Description | Performance | Computational Cost |
|---------|-------------|-------------|-------------------|
| **wav2vec 2.0 embeddings** | Self-supervised representations | 96.49% accuracy | Very High (768-dim) |
| **Log-Mel Spectrograms** | Time-frequency representation | ~78% with CNN | High |
| **i-vectors** | Speaker embedding technique | Strong for audio analysis | High |

### Minimum Viable Feature Set for Edge Deployment

Based on clinical validation and computational efficiency:

```
Essential (6 features):
1. Jitter (local)
2. Shimmer (local)
3. F0 mean
4. F0 standard deviation
5. Speech rate
6. Pause ratio

Extended (12 features):
+ MFCC 1-4 (first 4 coefficients)
+ HNR
+ Spectral centroid
```

### Feature Extraction Tools

- **openSMILE**: Industry standard, C++ (runs on Raspberry Pi), real-time capable
- **GeMAPS**: 62 features, standardized minimal set
- **eGeMAPS**: 88 features, extended version
- **ComParE 2016**: 6,373 features (too large for edge)

---

## Edge/TinyML Landscape for Depression Detection

### Current State

**No published work exists specifically for depression detection on microcontrollers.**

### Related TinyML Audio Work

| Capability | ESP32 | ARM Cortex-M4 | nRF52840 |
|------------|-------|---------------|----------|
| MFCC Extraction | Yes | Yes | Yes |
| CNN Inference | Yes (small) | Yes | Yes |
| LSTM Inference | Limited | Yes | Limited |
| RAM Available | 520 KB | 256 KB typical | 256 KB |
| Flash Available | 4 MB | 1 MB typical | 1 MB |

### Optimization Techniques Available

1. **Quantization**: 8-bit (25x memory reduction demonstrated)
2. **Pruning**: Remove redundant weights
3. **Knowledge Distillation**: Wav2Small achieves 72K parameters from 0.4B teacher
4. **Binary Activation Maps**: Replace multiplications with additions
5. **CNN-to-SNN Conversion**: Energy-efficient spiking networks (82.5% on DAIC-WOZ)

### Frameworks for Deployment

- **TensorFlow Lite Micro**: Most mature, CMSIS-NN acceleration
- **Edge Impulse**: End-to-end platform, ESP32 support
- **STM32Cube.AI**: ST-specific, optimized for Cortex-M
- **microTVM**: Apache TVM for microcontrollers

---

## Gaps and Opportunities for Novel Contribution

### Identified Gaps

| Gap | Current State | Opportunity |
|-----|--------------|-------------|
| **No MCU depression detection** | All work on servers/smartphones | First ESP32/Cortex-M implementation |
| **Feature extraction on edge** | openSMILE requires Linux/Windows | Lightweight C library for MCU |
| **Real-time continuous monitoring** | Batch processing dominant | Streaming inference pipeline |
| **Privacy by design** | FL explored but not on-device | Fully on-device, no data leaves MCU |
| **Longitudinal tracking** | Single-session classification | Track changes over time on-device |
| **Power efficiency** | Not addressed | Battery-operated wearable |
| **Multi-language support** | English/Chinese datasets | Cross-lingual feature validation |

### Research Questions to Address

1. **What is the minimum feature set that maintains clinically acceptable accuracy on edge devices?**
   - Hypothesis: 6-12 hand-crafted features can achieve >75% accuracy

2. **Can CNN-to-SNN conversion enable ultra-low-power depression detection?**
   - SNN has shown 82.5% on DAIC-WOZ in simulation

3. **What inference latency and power consumption is achievable on ESP32?**
   - Keyword spotting achieves ~24ms; depression features may be similar

4. **Can federated learning be combined with on-device inference?**
   - Train on smartphone, deploy to wearable

### Recommended Research Directions

#### Direction 1: Minimal Feature Edge Detector (Short-term, 3-6 months)

**Approach**:
- Extract jitter, shimmer, F0, pause features using custom C implementation
- Train small MLP or decision tree on DAIC-WOZ
- Deploy on ESP32 with TF Lite Micro

**Expected Outcome**:
- First depression screening on MCU
- Target: >70% accuracy, <100ms inference, <50mW power

**Novelty**: First published work on MCU-based depression detection

#### Direction 2: Spiking Neural Network Depression Detector (Medium-term, 6-12 months)

**Approach**:
- Build on CNN-to-SNN conversion work (82.5% baseline)
- Target neuromorphic chips (Loihi) or software SNN on MCU
- Focus on energy efficiency for wearables

**Expected Outcome**:
- 10-100x energy reduction vs CNN
- Suitable for always-on monitoring

**Novelty**: First neuromorphic depression detection system

#### Direction 3: Privacy-Preserving Wearable System (Long-term, 12-18 months)

**Approach**:
- Federated learning for model updates
- On-device inference with differential privacy
- Longitudinal tracking with secure aggregation

**Expected Outcome**:
- Complete wearable mental health monitor
- No raw audio leaves device ever

**Novelty**: Privacy-by-design mental health wearable

---

## Technical Recommendations

### Architecture for Edge Depression Detection

```
+------------------+     +------------------+     +------------------+
|   Microphone     | --> | Feature Extract  | --> |   Classifier     |
|   (I2S/PDM)      |     | (Jitter,Shimmer, |     |   (MLP/SVM/DT)   |
|                  |     |  F0, MFCC)       |     |   Quantized 8-bit|
+------------------+     +------------------+     +------------------+
        |                        |                        |
        v                        v                        v
   16kHz, 16-bit          ~12 features             Binary: Dep/Not
   ~32KB/sec buffer       per 4s window            + Confidence score
```

### Suggested Model Specifications

| Component | Specification | Rationale |
|-----------|--------------|-----------|
| Input | 4-second audio window | Sufficient for prosodic features |
| Features | 12 hand-crafted | Validated, computationally efficient |
| Model | 3-layer MLP (12-32-16-2) | ~2KB weights |
| Quantization | INT8 | 4x memory reduction |
| Inference | <50ms | Real-time capable |
| Power | <20mW active | Battery feasibility |

### Evaluation Protocol

1. **Train/Test Split**: Use official DAIC-WOZ splits
2. **Metrics**: F1-score (primary), Accuracy, AUROC
3. **Baseline Comparison**: eGeMAPS + SVM (AVEC baseline)
4. **Edge Metrics**: Latency, Memory, Power consumption
5. **Clinical Validation**: Consult with psychiatrists on utility

---

## Conclusion

Depression detection from speech is a mature research area with validated acoustic biomarkers and established benchmarks. However, the translation to edge devices remains unexplored. This represents a significant opportunity for novel contribution:

1. **Technical novelty**: First MCU-based depression screening system
2. **Clinical relevance**: Accessible, privacy-preserving mental health monitoring
3. **Commercial potential**: Integration into wearables and IoT health devices

The recommended starting point is a minimal feature set (jitter, shimmer, F0, pause features) with a small quantized classifier on ESP32, targeting the DAIC-WOZ benchmark. This establishes a baseline for more sophisticated approaches including spiking neural networks and federated learning.

---

## References

### Datasets
- [DAIC-WOZ Database](https://dcapswoz.ict.usc.edu/)
- [MODMA Dataset](https://modma.lzu.edu.cn/)
- [Chinese Multimodal Depression Corpus (CMDC)](https://ieee-dataport.org/open-access/chinese-multimodal-depression-corpus)

### Key Papers
- [Voice Acoustic Parameters as Predictors of Depression](https://pubmed.ncbi.nlm.nih.gov/34353686/)
- [The voice of depression: speech features as biomarkers](https://link.springer.com/article/10.1186/s12888-024-06253-6)
- [Depression recognition using voice-based pre-training model](https://www.nature.com/articles/s41598-024-63556-0)
- [Improving speech depression detection using transfer learning with wav2vec 2.0](https://pmc.ncbi.nlm.nih.gov/articles/PMC11045867/)
- [AVEC 2019 Workshop and Challenge](https://dl.acm.org/doi/10.1145/3347320.3357688)
- [From Convolution to Spikes: CNN-to-SNN for DAIC-WOZ](https://www.mdpi.com/2076-3417/15/16/9032)
- [Privacy Sensitive Speech Analysis Using Federated Learning](https://arxiv.org/abs/2205.00111)
- [MHDeep: Mental Health Disorder Detection on Wearables](https://dl.acm.org/doi/10.1145/3527170)
- [Wav2Small: Distilling Wav2Vec2 to 72K parameters](https://arxiv.org/html/2408.13920v2)

### Tools and Frameworks
- [openSMILE](https://github.com/audeering/opensmile)
- [TensorFlow Lite for Microcontrollers](https://www.tensorflow.org/lite/microcontrollers)
- [Edge Impulse](https://www.edgeimpulse.com/)
- [AVEC 2019 Baseline Code](https://github.com/AudioVisualEmotionChallenge/AVEC2019)

### TinyML Resources
- [Speech Emotion Recognition TinyML](https://github.com/Hannibal0420/Speech-Emotion-Recognition-TinyML)
- [TF Lite Micro Speech Example](https://github.com/tensorflow/tflite-micro/blob/main/tensorflow/lite/micro/examples/micro_speech/README.md)
- [Deploying Neural Networks on Microcontrollers](https://www.embedded.com/deploying-neural-networks-on-microcontrollers-with-tinyml/)

---

*Report generated: January 2026*
*Research focus: Edge/TinyML Depression Detection from Speech*
