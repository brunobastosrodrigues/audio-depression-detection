from core.services.temporal_context.Contextualizer import Contextualizer
from typing import List
from hmmlearn.hmm import GaussianHMM
import numpy as np


class HMM(Contextualizer):
    def __init__(self, n_states: int = 5, n_iter: int = 200, random_state: int = 42):
        self.n_states = n_states
        self.n_iter = n_iter
        self.random_state = random_state

    def compute(self, values: List[float]) -> List[float]:
        if not values or len(values) < self.n_states:
            return values

        series = np.array(values, dtype=float)
        mean = np.mean(series)
        std = np.std(series)
        # A constant series has std == 0 -> normalization would divide by zero (inf/nan that
        # GaussianHMM rejects). There is nothing to model, so return the series unchanged.
        if std == 0 or not np.isfinite(std):
            return list(series)
        normed = (series - mean) / std

        X = normed.reshape(-1, 1)

        model = GaussianHMM(
            n_components=self.n_states,
            covariance_type="diag",
            n_iter=self.n_iter,
            random_state=self.random_state,
        )
        model.fit(X)

        states = model.predict(X)

        state_means = model.means_.flatten()

        baseline = [state_means[state] * std + mean for state in states]

        return baseline
