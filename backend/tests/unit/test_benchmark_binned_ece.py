"""Mathematical and boundary unit tests for binned Expected Calibration Error (ECE).

Formally verifies:
    ECE = sum_{b=1}^{B} (|S_b| / N) * |acc(S_b) - conf(S_b)|
across all edge cases, boundaries, and calibration distributions.
"""

import pytest
from app.services.benchmark_engine_service import BenchmarkScoringService


def test_ece_perfect_calibration():
    """Verify that perfectly calibrated predictions yield an ECE of 0.0."""
    # 3 samples in different bins with exact confidence == accuracy
    predictions = [
        {"confidence_score": 0.25, "score": 25.0},
        {"confidence_score": 0.50, "score": 50.0},
        {"confidence_score": 0.85, "score": 85.0},
    ]
    ece = BenchmarkScoringService.calculate_calibration_error(predictions, num_bins=10)
    assert ece == 0.0


def test_ece_severe_overconfidence():
    """Verify ECE calculation for severe overconfidence."""
    # Model predicts 95% confidence but accuracy is only 10%
    predictions = [
        {"confidence_score": 0.95, "score": 10.0},
        {"confidence_score": 0.95, "score": 10.0},
    ]
    # acc = 0.10, conf = 0.95 -> diff = |0.10 - 0.95| = 0.85
    ece = BenchmarkScoringService.calculate_calibration_error(predictions, num_bins=10)
    assert pytest.approx(ece, 0.001) == 0.85


def test_ece_severe_underconfidence():
    """Verify ECE calculation for severe underconfidence."""
    # Model predicts 20% confidence but accuracy is 90%
    predictions = [
        {"confidence_score": 0.20, "score": 90.0},
        {"confidence_score": 0.20, "score": 90.0},
    ]
    # acc = 0.90, conf = 0.20 -> diff = |0.90 - 0.20| = 0.70
    ece = BenchmarkScoringService.calculate_calibration_error(predictions, num_bins=10)
    assert pytest.approx(ece, 0.001) == 0.70


def test_ece_mixed_confidence_bins():
    """Verify multi-bin weighted summation with known analytical result."""
    # 2 predictions in bin 1 ([0.1, 0.2)): conf=0.15, scores: 10.0 and 20.0 -> acc=0.15, diff=0.0
    # 2 predictions in bin 8 ([0.8, 0.9)): conf=0.85, scores: 60.0 and 60.0 -> acc=0.60, diff=|0.60 - 0.85| = 0.25
    # Total N = 4.
    # Bin 1 weight = 2/4 = 0.5, error = 0.0
    # Bin 8 weight = 2/4 = 0.5, error = 0.25
    # Expected ECE = 0.5 * 0.0 + 0.5 * 0.25 = 0.125
    predictions = [
        {"confidence_score": 0.15, "score": 10.0},
        {"confidence_score": 0.15, "score": 20.0},
        {"confidence_score": 0.85, "score": 60.0},
        {"confidence_score": 0.85, "score": 60.0},
    ]
    ece = BenchmarkScoringService.calculate_calibration_error(predictions, num_bins=10)
    assert pytest.approx(ece, 0.0001) == 0.125


def test_ece_all_predictions_in_single_bin():
    """Verify handling when all predictions concentrate in a single bin."""
    predictions = [
        {"confidence_score": 0.72, "score": 80.0},
        {"confidence_score": 0.74, "score": 70.0},
        {"confidence_score": 0.76, "score": 90.0},
    ]
    # Mean conf = 0.74, Mean acc = 80.0/100.0 = 0.80
    # Error = |0.80 - 0.74| = 0.06
    ece = BenchmarkScoringService.calculate_calibration_error(predictions, num_bins=10)
    assert pytest.approx(ece, 0.001) == 0.06


def test_ece_empty_input():
    """Verify that an empty list of results returns 0.0 without errors."""
    ece = BenchmarkScoringService.calculate_calibration_error([], num_bins=10)
    assert ece == 0.0


def test_ece_boundary_values_zero_and_one():
    """Verify that confidence boundary values 0.0 and 1.0 are placed correctly without IndexError."""
    predictions = [
        {"confidence_score": 0.0, "score": 0.0},   # Bin 0: diff = 0.0
        {"confidence_score": 1.0, "score": 100.0}, # Bin 9: diff = 0.0
    ]
    ece = BenchmarkScoringService.calculate_calibration_error(predictions, num_bins=10)
    assert ece == 0.0

    predictions_imperfect = [
        {"confidence_score": 0.0, "score": 50.0},  # Bin 0: conf=0.0, acc=0.5 -> diff=0.5
        {"confidence_score": 1.0, "score": 50.0},  # Bin 9: conf=1.0, acc=0.5 -> diff=0.5
    ]
    # Total ECE = 0.5 * 0.5 + 0.5 * 0.5 = 0.5
    ece_imperfect = BenchmarkScoringService.calculate_calibration_error(predictions_imperfect, num_bins=10)
    assert pytest.approx(ece_imperfect, 0.001) == 0.5


def test_ece_insufficient_sample_size():
    """Verify calculation with a single observation (N=1)."""
    predictions = [{"confidence_score": 0.65, "score": 95.0}]
    # acc = 0.95, conf = 0.65 -> diff = |0.95 - 0.65| = 0.30
    ece = BenchmarkScoringService.calculate_calibration_error(predictions, num_bins=10)
    assert pytest.approx(ece, 0.001) == 0.30


def test_ece_missing_and_none_confidence_handling():
    """Verify that predictions with missing or None confidence are safely skipped."""
    predictions = [
        {"confidence_score": None, "score": 100.0},
        {"confidence_score": 0.80, "score": 80.0},
        {"score": 90.0},
    ]
    # Only the middle prediction is valid -> diff = |0.80 - 0.80| = 0.0
    ece = BenchmarkScoringService.calculate_calibration_error(predictions, num_bins=10)
    assert ece == 0.0


def test_mace_vs_binned_ece():
    """Verify comparison between binned ECE and Mean Absolute Confidence Error (MACE)."""
    predictions = [
        {"confidence_score": 0.81, "score": 85.0}, # conf=0.81, acc=0.85, diff=0.04
        {"confidence_score": 0.89, "score": 85.0}, # conf=0.89, acc=0.85, diff=0.04
    ]
    # Both fall in bin 8 ([0.8, 0.9)).
    # Mean conf in bin 8 = (0.81 + 0.89) / 2 = 0.85.
    # Mean acc in bin 8 = 0.85.
    # In binned ECE: bin error = |0.85 - 0.85| = 0.0 -> ECE = 0.0!
    # In unbinned MACE: mean(|0.81 - 0.85|, |0.89 - 0.85|) = (0.04 + 0.04) / 2 = 0.04!
    ece = BenchmarkScoringService.calculate_calibration_error(predictions, num_bins=10)
    mace = BenchmarkScoringService.calculate_mean_absolute_confidence_error(predictions)

    assert ece == 0.0
    assert pytest.approx(mace, 0.001) == 0.04
