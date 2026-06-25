from core.services.temporal_context.Contextualizer import Contextualizer
from typing import List

import numpy as np


class SpikeDampenedEMA(Contextualizer):
    """EMA that dampens steps which are large relative to the series' OWN variability.

    The spike threshold is a multiple of the typical day-to-day step (the median absolute
    consecutive delta), not a fraction of the current value's magnitude. The old
    `ratio * abs(value)` threshold was scale- and sign-dependent: it never fired for large
    values (their own magnitude set a large threshold) and dampened every normal step for
    metrics centered on zero (threshold ~0). `spike_multiplier` keeps the legacy-ish
    `spike_threshold_ratio` name for back-compat but is now a multiplier on the typical step.
    """

    def __init__(self, alpha=0.13, spike_multiplier=3.0, dampening_factor=0.3):
        self.alpha = alpha
        self.spike_multiplier = spike_multiplier
        self.dampening_factor = dampening_factor

    def compute(self, values: List[float]) -> List[float]:
        if not values:
            return []

        arr = np.asarray(values, dtype=float)
        if len(arr) > 1:
            deltas = np.abs(np.diff(arr))
            nonzero = deltas[deltas > 0]
            typical_step = float(np.median(nonzero)) if nonzero.size else 0.0
        else:
            typical_step = 0.0
        # typical_step == 0 (constant series) => threshold 0 => never dampen.
        spike_threshold = self.spike_multiplier * typical_step

        ema = []
        prev_ema = float(arr[0])
        for val in arr:
            delta = abs(val - prev_ema)
            update = self.alpha * (val - prev_ema)
            if spike_threshold > 0 and delta > spike_threshold:
                update *= self.dampening_factor
            prev_ema += update
            ema.append(prev_ema)
        return ema
