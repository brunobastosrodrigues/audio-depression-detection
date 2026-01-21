# Tasks for Jules

## Active Tasks

### Task 1: Implement SceneResolverV2 with XVF3800 DoA Fusion
**Status:** 🟡 Ready for work
**Priority:** High
**Branch:** `feature/zero-cloud-architecture`

#### Summary
Implement the enhanced SceneResolver (V2) that fuses D-vector speaker verification with XVF3800's Direction of Arrival (DoA) for improved speaker identification in challenging conditions.

#### Design Document
See: `research-roadmap/docs/XVF3800_INTEGRATION_SKETCH.md`

#### Subtasks

**1. Create Data Models**
- [ ] Create `processing_layer/scene_analysis/models.py`
- [ ] Add `AudioChunkMetadata` dataclass (board_type, doa_angle, doa_confidence, snr_estimate, room)
- [ ] Add `EnhancedResolveResult` dataclass (extends current result with location_score, fused_confidence)

**2. Extend SceneConfig**
- [ ] Update `scene_config.json` with:
  - `doa_fusion` section (enabled, doa_weight, dvector_weight)
  - `location_priors` section (expected DoA by room/time)
  - `hardware_profiles.xvf3800` profile
- [ ] Update `SceneConfig.py` to load new config sections

**3. Implement SceneResolverV2**
- [ ] Create `SceneResolverV2.py` (or extend existing `SceneResolver.py`)
- [ ] Add `_compute_location_score()` method
- [ ] Add `_fuse_dvector_and_doa()` method
- [ ] Add `_get_location_prior()` method
- [ ] Add `_update_location_history()` for learning
- [ ] Update `resolve()` to accept optional `AudioChunkMetadata`
- [ ] Maintain backward compatibility (metadata=None for ReSpeaker Lite)

**4. Integration**
- [ ] Update `ComputeMetricsHandler.py` to extract metadata from MQTT payload
- [ ] Pass metadata to SceneResolver
- [ ] Update scene_logs collection to include DoA info

**5. Tests**
- [ ] Test DoA fusion improves uncertain D-vector matches
- [ ] Test wrong location reduces confidence
- [ ] Test backward compatibility with ReSpeaker Lite (no DoA)

#### Technical Notes

**Fusion Formula:**
```python
fused_confidence = dvector_weight * similarity + doa_weight * location_score
# Default weights: 0.7 / 0.3
```

**Location Score (Gaussian falloff):**
```python
location_score = exp(-0.5 * (angular_distance / expected_std)²)
```

**Hardware Profile for XVF3800:**
```json
{
  "xvf3800": {
    "similarity_threshold_high": 0.65,
    "similarity_threshold_low": 0.50,
    "has_doa": true,
    "has_aec": true,
    "far_field_range_m": 5.0
  }
}
```

#### Acceptance Criteria
- [ ] SceneResolverV2 passes all existing tests
- [ ] DoA fusion is configurable and can be disabled
- [ ] Location priors can be configured per room
- [ ] Backward compatible with ReSpeaker Lite payloads (no DoA)
- [ ] Scene logs include DoA metadata when available

---

## Completed Tasks

(None yet)

---

## Notes for Jules

1. **Branch:** Always work on `feature/zero-cloud-architecture`
2. **Design docs:** Check `research-roadmap/docs/` for detailed specifications
3. **Testing:** Run existing tests with `pytest` before committing
4. **Commits:** Use conventional commit format (`feat:`, `fix:`, `docs:`, etc.)
