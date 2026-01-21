# Multi-Speaker Identification in Challenging Conditions

## The Challenge

In a real household environment, the system must:
1. **Identify the target user** among multiple household members
2. **Handle far-field audio** (user not close to microphone)
3. **Filter background noise** (TV, HVAC, appliances, street noise)
4. **Distinguish speech from non-speech** (music, TV dialogue)

This is harder than lab conditions where:
- Single speaker in quiet room
- Close-talking microphone
- Controlled acoustic environment

---

## Current System: Scene Analysis Gatekeeper

The current implementation uses a **scene resolver** that:

1. **Speaker Verification (D-vectors)**
   - Resemblyzer model extracts 128-D speaker embeddings
   - Cosine similarity against enrolled user's reference embedding
   - Threshold: ≥0.70 = "target_user", 0.55-0.70 = "uncertain", <0.55 = "other"

2. **Context Classification (60s window)**
   - `solo_activity`: Target user dominates (>50%)
   - `social_interaction`: Mixed speakers
   - `background_noise_tv`: Mostly noise

3. **Decision Logic**
   - Process if: target_user OR (uncertain AND solo_activity context)
   - Discard otherwise

### Limitations of Current Approach

| Challenge | Current Handling | Problem |
|-----------|------------------|---------|
| Far-field (>2m) | None | SNR degrades, D-vector fails |
| Background noise | None at edge | False speaker matches |
| Multiple speakers | Context window | Lag in detection |
| TV/music | Mechanical detection | Only detects typing |
| Reverberation | None | Distorts speaker embedding |

---

## XVF3800 Advantages for Multi-Speaker Scenarios

The XVF3800 hardware DSP provides capabilities the ReSpeaker Lite lacks:

### 1. Acoustic Echo Cancellation (AEC)
- Removes playback audio (TV, music) from microphone input
- Requires reference signal from speaker output
- **Benefit:** Isolates actual speech from media playback

### 2. Beamforming (3 beams)
- 1 scanning beam (finds speakers)
- 2 focused beams (tracks individuals)
- **Benefit:** Can follow target user, reject off-axis noise

### 3. Direction of Arrival (DoA)
- 360° coverage, up to 5m range
- **Benefit:** Spatial separation of speakers
- **Opportunity:** Combine DoA with D-vector for higher confidence

### 4. Noise Suppression
- Hardware-based stationary + non-stationary noise reduction
- **Benefit:** Cleaner audio for downstream processing

### 5. Dereverberation
- Reduces room reflections
- **Benefit:** Better speaker embedding extraction

---

## Proposed Multi-Speaker Architecture

### Tier 1: XVF3800 Hardware Processing

```
[4-mic array] → [XMOS DSP] → [Cleaned audio + metadata]
                    │
                    ├── AEC (remove TV/music)
                    ├── Beamform (focus on speaker)
                    ├── Denoise (suppress background)
                    ├── Dereverb (remove reflections)
                    └── DoA (speaker direction)
```

**Output:** Cleaned mono audio + DoA angle per frame

### Tier 2: ESP32-S3 Edge Processing

```
[Cleaned audio] → [ESP32-S3] → [Features + speaker score]
                       │
                       ├── VAD (is this speech?)
                       ├── Lightweight D-vector (speaker ID)
                       ├── MFCC extraction
                       └── F0 extraction
```

**Key insight:** D-vector on cleaned audio from XVF3800 will be much more reliable than on raw ReSpeaker audio.

### Tier 3: Pi 5 Hub Fusion

```
[Features from all devices] → [Pi 5] → [Identity decision]
                                  │
                                  ├── Multi-device DoA fusion (triangulation)
                                  ├── D-vector ensemble (multiple devices)
                                  ├── Temporal smoothing (speaker tracking)
                                  └── Context inference (who is where)
```

---

## Speaker Identification Strategies

### Strategy 1: D-vector with DoA Prior

Instead of D-vector alone, combine with spatial information:

```python
def identify_speaker(audio, doa_angle, device_location):
    # 1. Get D-vector embedding
    embedding = extract_dvector(audio)

    # 2. Get expected location of target user
    expected_doa = get_user_expected_location(time_of_day, device_location)

    # 3. Compute scores
    embedding_score = cosine_similarity(embedding, user_reference)
    location_score = angular_similarity(doa_angle, expected_doa)

    # 4. Fused score
    confidence = 0.7 * embedding_score + 0.3 * location_score

    return confidence > THRESHOLD
```

**Advantage:** If D-vector is uncertain (0.55-0.70), location can disambiguate.

### Strategy 2: Multi-Device Triangulation

With 4 XVF3800 devices, we can localize speakers in 3D:

```
Device 1 (Kitchen): DoA = 45°  ─┐
Device 2 (Living):  DoA = 120° ─┼─→ [Triangulation] → Position (x, y)
Device 3 (Bedroom): DoA = 270° ─┤
Device 4 (Office):  DoA = 180° ─┘
```

**Identity inference:** Target user's phone/watch location → expected position → match speaker position

### Strategy 3: Voice Fingerprint Ensemble

Multiple devices capture the same utterance → ensemble D-vector:

```python
def ensemble_identification(embeddings_from_devices, user_reference):
    # Weight by SNR (higher SNR device gets more weight)
    weights = [estimate_snr(e) for e in embeddings_from_devices]
    weights = softmax(weights)

    # Weighted average embedding
    fused_embedding = sum(w * e for w, e in zip(weights, embeddings))

    return cosine_similarity(fused_embedding, user_reference)
```

### Strategy 4: Temporal Speaker Tracking

Once identified, track the speaker across time:

```python
class SpeakerTracker:
    def __init__(self):
        self.last_known_doa = {}  # {speaker_id: doa_angle}
        self.confidence_history = {}  # {speaker_id: [scores]}

    def update(self, current_doa, current_embedding):
        # Predict expected DoA based on last known + motion model
        predicted_doa = self.predict_location(speaker_id)

        # If close to predicted, boost confidence
        if angular_distance(current_doa, predicted_doa) < 30:
            confidence_boost = 0.1

        # Update tracker
        self.last_known_doa[speaker_id] = current_doa
```

---

## Handling Specific Challenges

### Challenge 1: Far-Field Audio (>2m)

**Problem:** SNR drops, D-vector accuracy degrades

**Solutions:**
1. XVF3800 beamforming focuses gain on speaker direction
2. Noise suppression recovers some SNR
3. Lower D-vector threshold (0.60 instead of 0.70) but require DoA confirmation
4. Use multiple devices (at least one will be closer)

### Challenge 2: Background TV/Music

**Problem:** TV dialogue may be misidentified as household speech

**Solutions:**
1. XVF3800 AEC removes playback audio (if speaker output is routed to XVF3800)
2. Without AEC: Detect TV audio patterns (consistent energy, no pauses)
3. Cross-device consistency: Real speaker appears on multiple devices, TV only on one
4. Music detection: High spectral flatness, periodic energy

### Challenge 3: Multiple Simultaneous Speakers

**Problem:** Two people talking at once

**Solutions:**
1. XVF3800's 2 focused beams can track 2 speakers independently
2. Process only the beam matching target user's expected location
3. Detect overlap (energy from multiple DoA) → mark as "social_interaction"
4. Don't extract features during overlap (unreliable)

### Challenge 4: New/Unknown Speakers (Visitors)

**Problem:** Visitor might be misidentified as target user

**Solutions:**
1. Enroll all household members (negative examples)
2. If embedding matches neither target nor known others → "unknown_speaker"
3. Require higher threshold for processing (0.75 instead of 0.70)
4. Location prior: Visitor unlikely to be in bedroom at 3am

---

## Enrollment Protocol for Robust Identification

### Current Enrollment
- Single voice sample (~15 seconds)
- One embedding per user

### Improved Enrollment

```
1. Multi-room enrollment:
   - Record in kitchen (high noise)
   - Record in bedroom (quiet)
   - Record in living room (TV background)

2. Multi-condition enrollment:
   - Normal speaking voice
   - Soft voice (tired/depressed baseline!)
   - Slightly louder (calling across room)

3. Multi-device enrollment:
   - Enroll from each XVF3800 position
   - Creates device-specific reference embeddings
   - Handles acoustic differences between rooms
```

**Storage:** Multiple reference embeddings per user, weighted by relevance

---

## Implementation Roadmap

### Phase 1: XVF3800 Integration (Weeks 5-8)
- [ ] Integrate XVF3800 into data ingestion pipeline
- [ ] Extract DoA from XVF3800 (via I2C/SPI)
- [ ] Log DoA with each audio chunk
- [ ] Compare D-vector accuracy: ReSpeaker vs XVF3800

### Phase 2: DoA-Enhanced Identification (Weeks 9-12)
- [ ] Implement DoA + D-vector fusion
- [ ] Collect data: DoA patterns for target user over 1 week
- [ ] Learn expected DoA by time-of-day
- [ ] Evaluate: Does DoA improve identification accuracy?

### Phase 3: Multi-Device Fusion (Weeks 13-16)
- [ ] Implement multi-device speaker localization
- [ ] Test triangulation accuracy
- [ ] Implement ensemble D-vector scoring
- [ ] Evaluate in simulated multi-speaker scenarios

### Phase 4: Robustness Testing (Weeks 17-20)
- [ ] Test with background TV
- [ ] Test far-field (3m, 5m)
- [ ] Test multiple speakers
- [ ] Measure false acceptance rate (FAR) and false rejection rate (FRR)

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Speaker ID accuracy (quiet) | ~90% | >95% |
| Speaker ID accuracy (noisy) | ~70% | >85% |
| Far-field range | 2m | 5m |
| Multi-speaker separation | None | 2 speakers |
| False acceptance rate | Unknown | <5% |
| False rejection rate | Unknown | <10% |

---

## Research Questions

1. **How much does XVF3800 DSP improve D-vector accuracy?**
   - Hypothesis: 10-20% improvement in noisy conditions

2. **Can DoA disambiguate when D-vector is uncertain?**
   - Hypothesis: Yes, especially with learned location priors

3. **What is the minimum enrollment data for robust identification?**
   - Current: 15 seconds
   - Hypothesis: 2-3 minutes across conditions is sufficient

4. **How does multi-device ensemble compare to single best device?**
   - Hypothesis: Ensemble improves accuracy by 5-10%

---

## Hardware Deployment Recommendations

| Room | Device | Rationale |
|------|--------|-----------|
| **Kitchen** | XVF3800 | High noise, far-field, benefits from DSP |
| **Living Room** | XVF3800 | TV interference, multiple speakers |
| **Bedroom** | ReSpeaker Lite | Quiet, close-field, cost savings |
| **Office** | XVF3800 | Variable noise, far-field |

Total: 3x XVF3800 ($120) + 1x ReSpeaker Lite ($15) = $135
vs 4x XVF3800 = $160

The bedroom is the only room where ReSpeaker Lite is sufficient.
