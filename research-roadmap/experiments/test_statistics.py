import numpy as np
import pytest
from dashboard_layer.utils.validation import (
    cohens_d,
    fdr_correction,
    run_hypothesis_test,
    calculate_classification_metrics,
)


def test_cohens_d_known_value():
    """Test Cohen's d with a known effect size."""
    # group1: mean=1, std=1
    group1 = np.array([0, 1, 2])
    # group2: mean=3, std=1
    group2 = np.array([2, 3, 4])

    # n1=3, n2=3, var1=1, var2=1
    # pooled_std = sqrt(((2*1 + 2*1)/(3+3-2))) =.sqrt(4/4) = 1
    # cohens_d = (1 - 3) / 1 = -2.0
    d = cohens_d(group1, group2)

    assert d == pytest.approx(-2.0)


def test_cohens_d_zero_std():
    """Test Cohen's d when the pooled standard deviation is zero."""
    group1 = np.array([1, 1, 1, 1, 1])
    group2 = np.array([2, 2, 2, 2, 2])

    # The function should handle this gracefully by returning 0.0
    d = cohens_d(group1, group2)
    assert d == 0.0

def test_fdr_correction_bh():
    """Test the Benjamini-Hochberg FDR correction."""
    p_values = [0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5]
    n = len(p_values)

    # Expected corrected p-values (p * n / rank)
    # [0.01*10/1, 0.02*10/2, 0.03*10/3, ..., 0.5*10/10]
    # [0.1, 0.1, 0.1, 0.1, 0.1, 0.166, 0.285, 0.375, 0.444, 0.5]
    # After enforcing montonicity, the first 6 values should be 0.1
    expected_corrected = [
        0.1, 0.1, 0.1, 0.1, 0.1, 0.16666667, 0.28571429,
        0.375, 0.44444444, 0.5
    ]
    expected_significant = [True, True, True, True, True, False, False, False, False, False]

    corrected, significant = fdr_correction(p_values, alpha=0.15)

    assert corrected == pytest.approx(expected_corrected, abs=1e-2)
    assert significant == expected_significant

def test_run_hypothesis_test_directional():
    """Test the directional hypothesis test wrapper."""
    depressed = np.array([1, 2, 3, 4, 5])  # mean=3
    nondepressed = np.array([4, 5, 6, 7, 8])  # mean=6

    # Test case 1: depressed < nondepressed (correct direction)
    result1 = run_hypothesis_test("test_feature", depressed, nondepressed, expected_direction="<")

    assert result1.feature == "test_feature"
    assert result1.direction_correct is True
    assert result1.p_value < 0.05
    assert result1.depressed_mean == 3
    assert result1.nondepressed_mean == 6

    # Test case 2: depressed > nondepressed (incorrect direction)
    result2 = run_hypothesis_test("test_feature", depressed, nondepressed, expected_direction=">")

    assert result2.direction_correct is False
    assert result2.p_value > 0.95

def test_calculate_classification_metrics_basic():
    """Test the calculation of classification metrics."""
    y_true = np.array([1, 1, 0, 0, 1, 0])
    y_pred = np.array([1, 0, 0, 1, 1, 0])

    # TP=2, TN=2, FP=1, FN=1
    metrics = calculate_classification_metrics(y_true, y_pred)

    assert metrics.tp == 2
    assert metrics.tn == 2
    assert metrics.fp == 1
    assert metrics.fn == 1

    assert metrics.sensitivity == pytest.approx(2/3)
    assert metrics.specificity == pytest.approx(2/3)
    assert metrics.ppv == pytest.approx(2/3)
    assert metrics.npv == pytest.approx(2/3)

    assert metrics.accuracy == pytest.approx(4/6)
    assert metrics.f1_score == pytest.approx(2 * ( (2/3)*(2/3) ) / (2/3 + 2/3) )

def bootstrap_ci(data, n_bootstrap=1000, ci=95):
    """Calculate the bootstrap confidence interval for the mean."""
    means = np.zeros(n_bootstrap)
    for i in range(n_bootstrap):
        sample = np.random.choice(data, size=len(data), replace=True)
        means[i] = np.mean(sample)

    lower_bound = np.percentile(means, (100 - ci) / 2)
    upper_bound = np.percentile(means, 100 - (100 - ci) / 2)

    return lower_bound, upper_bound

def test_bootstrap_ci_coverage():
    """Test the coverage of the bootstrap confidence interval."""
    true_mean = 5
    n_experiments = 1000
    coverage_count = 0

    for _ in range(n_experiments):
        # Generate a dataset from a known distribution
        data = np.random.normal(loc=true_mean, scale=2, size=100)

        # Calculate the 95% confidence interval
        lower, upper = bootstrap_ci(data, n_bootstrap=100, ci=95)

        # Check if the true mean is within the interval
        if lower <= true_mean <= upper:
            coverage_count += 1

    # The coverage should be approximately 95%
    coverage = coverage_count / n_experiments
    assert coverage == pytest.approx(0.95, abs=0.05)
