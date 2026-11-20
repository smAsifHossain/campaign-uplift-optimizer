from __future__ import annotations

import numpy as np

from campaign_uplift.metrics import (
    auuc_above_random,
    experiment_summary,
    paired_policy_difference,
    policy_curve,
    transformed_outcome,
)


def test_experiment_summary_matches_difference_in_means() -> None:
    treatment = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    outcome = np.array([1, 1, 0, 0, 0, 0, 0, 0])
    summary = experiment_summary(treatment, outcome)
    assert summary["treated_conversion_rate"] == 0.5
    assert summary["control_conversion_rate"] == 0.0
    assert summary["absolute_effect"] == 0.5


def test_transformed_outcome_recovers_average_effect() -> None:
    treatment = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    outcome = np.array([1, 1, 0, 0, 0, 0, 0, 0])
    assert transformed_outcome(treatment, outcome).mean() == 0.5


def test_good_ranking_has_positive_area_above_random() -> None:
    treatment = np.array([1, 1, 0, 0] * 50)
    outcome = np.array([1, 1, 0, 0] + [0, 0, 0, 0] * 49)
    scores = np.zeros(len(treatment))
    scores[:4] = 1
    curve = policy_curve(scores, treatment, outcome, fractions=[0.05, 0.5, 1.0])
    assert auuc_above_random(curve) > 0
    assert curve[-1]["fraction"] == 1.0


def test_paired_policy_comparison_reports_overlap_and_interval() -> None:
    treatment = np.array([1, 0] * 100)
    outcome = np.array([1, 0] * 20 + [0, 0] * 80)
    first_scores = np.linspace(1, 0, len(treatment))
    second_scores = first_scores[::-1]
    result = paired_policy_difference(
        first_scores,
        second_scores,
        treatment,
        outcome,
        fraction=0.2,
        first_label="first",
        second_label="second",
    )
    assert result["difference_per_1000_eligible"] > 0
    assert result["overlap_rows"] == 0
    assert result["ci_95_low"] < result["ci_95_high"]
