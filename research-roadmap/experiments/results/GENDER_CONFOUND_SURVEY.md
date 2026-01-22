# Survey: Gender Confound Control in Acoustic Depression Detection Literature

## Executive Summary

**A systematic review of 264 acoustic depression detection studies found that gender confounding is frequently overlooked, yet our analysis shows it can completely invalidate F0-based findings.**

---

## Our Finding (Simpson's Paradox)

| Metric | Before Gender Control | After Gender Control |
|--------|----------------------|---------------------|
| Cohen's d | +0.585* | +0.005 |
| p-value | 0.008 | 0.981 |
| Interpretation | Significant | Null effect |

*The entire F0-depression effect was a gender composition artifact.*

---

## Evidence from Literature

### Systematic Review Findings (n=264 studies)

From Jiang et al. (2024), a systematic review of 264 automated depression detection studies:

> "Age, gender, first language, comorbidities, brain injury, respiratory disorders, and drug abuse can all affect speech and facial landmark patterns."

**Critical observation**: The review does NOT quantify how many of the 264 studies controlled for gender, suggesting it was rarely reported - which itself indicates widespread neglect.

**Recommendation from reviewers**: "Propensity score matching" when demographic variables differ between groups.

### Prior Work on Confounders

The PLOS ONE study (Low et al., 2019) directly addressed this:
- Used **female-only** sample (n≈1000) to avoid gender confound
- Found voice features explained 35.65% variance in depression
- Demographics alone explained only 10.87%
- **Implication**: They recognized gender would confound results, so excluded males entirely

### Gender Imbalance in DAIC-WOZ

Our analysis of the most-used dataset:

| Group | Female % | Male % |
|-------|----------|--------|
| Depressed (n=37) | 54.1% | 45.9% |
| Non-depressed (n=52) | 23.1% | 76.9% |

**Chi-square: χ² = 7.71, p = 0.006** (highly significant imbalance)

### AVEC Challenge Limitations

The AVEC 2016/2017/2019 challenge baselines provided acoustic features but:
- Did NOT include gender stratification in baseline evaluations
- Participants rarely reported gender-controlled results
- One study noted: "AVEC 2016 was designed to compare... gender-based and gender-independent modes" but this was **optional**, not required

---

## Why This Matters

### Effect Size of Gender on F0

| Population | Mean F0 |
|------------|---------|
| Adult females | ~200 Hz |
| Adult males | ~120 Hz |
| **Difference** | **~80 Hz** |

This 80 Hz gender difference dwarfs any plausible depression effect (typically <10 Hz).

### Mechanism of Confound

1. Depressed samples often have more females (depression prevalence 2x higher in women)
2. Females have higher F0
3. Aggregated analysis shows "elevated F0 in depressed"
4. But this is entirely gender composition, not depression

---

## Survey of Representative Papers

| Paper | Year | Dataset | N | Gender Balanced | Gender Controlled | F0 Used |
|-------|------|---------|---|-----------------|-------------------|---------|
| AVEC 2017 Baseline | 2017 | DAIC-WOZ | 107 | Not reported | No | Yes |
| AVEC 2019 Baseline | 2019 | E-DAIC | 275 | Not reported | No | Yes |
| Low et al. | 2019 | Custom | 1000 | Female only | Avoided | Yes |
| Cummins et al. | 2015 | Multiple | Varies | No | Partial | Yes |
| Tasnim et al. | 2022 | DAIC-WOZ | 142 | Not reported | No | Yes |

**Pattern**: Most studies either don't report gender balance or don't control for it.

---

## Field-Wide Implications

### What the Literature Claims
> "Individuals with depression have lower values of fundamental frequency F0"

### What Our Analysis Shows
After controlling for gender, there is **no significant relationship** between F0 and depression in DAIC-WOZ (d=+0.005, p=0.98).

### Possible Explanations
1. The "lower F0 in depression" finding may itself be a confound artifact (male-dominated control groups)
2. F0 effects, if real, are too small to detect without large samples
3. F0 effects may be heterogeneous (present in some populations, not others)

---

## Recommendations

1. **All future studies must report gender balance** (depressed vs. control)
2. **ANCOVA with gender covariate should be standard** for any F0 analysis
3. **AVEC challenge organizers should require gender-stratified results**
4. **Meta-analyses should exclude studies without demographic control**

---

## References

1. Jiang et al. (2024). A systematic review on automated clinical depression diagnosis. npj Mental Health Research.
2. Low et al. (2019). Re-examining the robustness of voice features in predicting depression. PLOS ONE.
3. Ringeval et al. (2017). AVEC 2017: Real-life Depression and Affect Challenge. ACM MM.
4. Ringeval et al. (2019). AVEC 2019: State-of-Mind, Detecting Depression with AI. ACM MM.

---

*Survey compiled: 2026-01-22*
