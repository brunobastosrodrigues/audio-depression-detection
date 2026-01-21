# Task Coordination: Fix Everything

## Active AI Assistants

| Assistant | Specialty | Communication |
|-----------|-----------|---------------|
| **Claude** | Python, research, coordination | Direct conversation |
| **Gemini** | C code, firmware, embedded | tmux gemini-worker |
| **Jules** | GitHub issues, async tasks | GitHub issues (label: jules) |

---

## Master Task List

### HIGH PRIORITY - C Feature Extractor Fixes

| Task | Owner | Status | Dependency |
|------|-------|--------|------------|
| Fix SNR inversion in voice_quality.c | Gemini | **DONE** | - |
| Tune VAD thresholds in vad.c | Gemini | IN PROGRESS | - |
| Recompile C extractor | Claude | PENDING | Gemini VAD fix |
| Re-run linkage analysis | Claude | PENDING | Recompile |

### MEDIUM PRIORITY - Dashboard Enhancements

| Task | Owner | Status | GitHub Issue |
|------|-------|--------|--------------|
| Add FDR correction display to Research Validation | Jules | PENDING | TBD |
| Add gender-stratified F0 view | Jules | PENDING | TBD |
| Show Simpson's Paradox warning | Jules | PENDING | TBD |
| Add power analysis summary | Jules | PENDING | TBD |

### MEDIUM PRIORITY - Documentation & Data

| Task | Owner | Status | GitHub Issue |
|------|-------|--------|--------------|
| Create dataset acquisition guide | Jules | PENDING | TBD |
| Document DAIC-WOZ download process | Jules | PENDING | TBD |
| Update README with research findings | Jules | PENDING | TBD |

### LOW PRIORITY - Future Enhancements

| Task | Owner | Status |
|------|-------|--------|
| Download full DAIC-WOZ (189 sessions) | User | PENDING (needs credentials) |
| Request DEPAC dataset access | User | PENDING |
| Request CMDC dataset access | User | PENDING |

---

## GitHub Issues for Jules

### Issue 1: Add FDR Correction to Research Validation Page
```
Title: feat(dashboard): Display FDR-corrected p-values in Research Validation
Labels: jules, enhancement, dashboard

Description:
The statistical analysis now includes Benjamini-Hochberg FDR correction for multiple comparisons.
Update the Research Validation page to show:
1. Raw p-values AND FDR-adjusted p-values
2. Significance indicator after FDR correction
3. Warning about multiple comparison inflation (34% false positive risk without correction)

Reference: research-roadmap/experiments/statistical_rigor.py:benjamini_hochberg_correction()
```

### Issue 2: Add Gender-Stratified Analysis View
```
Title: feat(dashboard): Add gender-stratified F0 analysis view
Labels: jules, enhancement, dashboard, critical

Description:
We discovered a Simpson's Paradox in the F0-depression relationship:
- Aggregated: F0 HIGHER in depressed (confounded)
- Gender-stratified: F0 LOWER in depressed females (correct)

Add a new section to Research Validation showing:
1. Gender distribution pie charts (depressed vs non-depressed)
2. Gender-stratified effect sizes
3. Warning banner about Simpson's Paradox when confound detected

Reference: research-roadmap/experiments/results/GENDER_CONFOUND_ANALYSIS.md
```

### Issue 3: Add Power Analysis Display
```
Title: feat(dashboard): Show statistical power for each feature
Labels: jules, enhancement, dashboard

Description:
Add power analysis visualization showing:
1. Power level for each feature (color-coded: green ≥80%, yellow ≥50%, red <50%)
2. Minimum detectable effect size given current sample
3. Warning for underpowered features (5/8 currently underpowered)

Reference: research-roadmap/experiments/results/power_analysis.csv
```

### Issue 4: Dataset Acquisition Documentation
```
Title: docs: Create comprehensive dataset acquisition guide
Labels: jules, documentation

Description:
Create docs/DATASET_ACQUISITION.md with:
1. List of available depression speech datasets
2. Access requirements and licensing for each
3. Step-by-step download instructions
4. Data format specifications
5. Citation requirements

Datasets to cover:
- DAIC-WOZ (English, PHQ-8)
- EATD-Corpus (Chinese, SDS)
- DEPAC (English, PHQ-9 + GAD-7)
- CMDC (Chinese, HAMD-17)
```

---

## Coordination Protocol

1. **Gemini** works on C code in `research-roadmap/experiments/c_feature_extractor/`
2. **Claude** handles Python analysis and coordination
3. **Jules** handles dashboard UI and documentation via GitHub issues
4. **No file conflicts** - each assistant has separate domains

## Communication

- Claude ↔ Gemini: tmux send-keys
- Claude → Jules: GitHub issues with "jules" label
- All → User: Direct conversation/PR reviews
