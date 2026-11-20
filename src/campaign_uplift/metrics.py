"""Experiment and policy metrics for randomized uplift evaluation."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
from scipy.stats import norm


def experiment_summary(treatment: np.ndarray, outcome: np.ndarray) -> dict[str, float | int]:
    """Estimate the randomized average treatment effect with a normal interval."""
    treatment = np.asarray(treatment, dtype=np.int8)
    outcome = np.asarray(outcome, dtype=float)
    treated = outcome[treatment == 1]
    control = outcome[treatment == 0]
    if len(treated) == 0 or len(control) == 0:
        raise ValueError("Both treatment groups are required.")
    treated_rate = float(treated.mean())
    control_rate = float(control.mean())
    effect = treated_rate - control_rate
    standard_error = float(
        np.sqrt(
            treated_rate * (1 - treated_rate) / len(treated)
            + control_rate * (1 - control_rate) / len(control)
        )
    )
    z_score = effect / standard_error if standard_error > 0 else 0.0
    margin = 1.959963984540054 * standard_error
    relative_lift = effect / control_rate if control_rate > 0 else float("nan")
    return {
        "rows": int(len(outcome)),
        "treated_rows": int(len(treated)),
        "control_rows": int(len(control)),
        "treatment_probability": float(treatment.mean()),
        "treated_conversion_rate": treated_rate,
        "control_conversion_rate": control_rate,
        "absolute_effect": effect,
        "relative_lift": relative_lift,
        "standard_error": standard_error,
        "ci_95_low": effect - margin,
        "ci_95_high": effect + margin,
        "z_score": z_score,
        "p_value_two_sided": float(2 * norm.sf(abs(z_score))),
    }


def transformed_outcome(
    treatment: np.ndarray, outcome: np.ndarray, treatment_probability: float | None = None
) -> np.ndarray:
    """Return the inverse-propensity transformed outcome for an RCT."""
    treatment = np.asarray(treatment, dtype=float)
    outcome = np.asarray(outcome, dtype=float)
    probability = (
        float(treatment.mean()) if treatment_probability is None else treatment_probability
    )
    if not 0 < probability < 1:
        raise ValueError("treatment_probability must be in (0, 1).")
    return outcome * (treatment / probability - (1 - treatment) / (1 - probability))


def policy_curve(
    scores: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    *,
    fractions: Iterable[float] | None = None,
    treatment_probability: float | None = None,
) -> list[dict[str, float | int]]:
    """Evaluate a ranking policy on data not used to fit the ranking."""
    scores = np.asarray(scores, dtype=float)
    treatment = np.asarray(treatment, dtype=np.int8)
    outcome = np.asarray(outcome, dtype=float)
    if not (len(scores) == len(treatment) == len(outcome)):
        raise ValueError("scores, treatment, and outcome must have equal lengths.")
    if fractions is None:
        fractions = np.linspace(0.05, 1.0, 20)
    requested = sorted({float(fraction) for fraction in fractions})
    if not requested or requested[0] <= 0 or requested[-1] > 1:
        raise ValueError("Policy fractions must be in (0, 1].")

    probability = (
        float(treatment.mean()) if treatment_probability is None else treatment_probability
    )
    influence = transformed_outcome(treatment, outcome, probability)
    order = np.argsort(-scores, kind="stable")
    overall_ate = float(influence.mean())
    n_rows = len(scores)
    results: list[dict[str, float | int]] = []
    for fraction in requested:
        selected_rows = max(1, min(n_rows, int(round(fraction * n_rows))))
        selected = np.zeros(n_rows, dtype=bool)
        selected[order[:selected_rows]] = True
        policy_influence = influence * selected
        incremental_per_eligible = 1000 * float(policy_influence.mean())
        incremental_per_targeted = 1000 * float(influence[selected].mean())
        standard_error = 1000 * float(policy_influence.std(ddof=1) / np.sqrt(n_rows))
        margin = 1.959963984540054 * standard_error
        results.append(
            {
                "fraction": selected_rows / n_rows,
                "selected_rows": selected_rows,
                "incremental_per_1000_eligible": incremental_per_eligible,
                "incremental_per_1000_targeted": incremental_per_targeted,
                "ci_95_low": incremental_per_eligible - margin,
                "ci_95_high": incremental_per_eligible + margin,
                "random_policy_per_1000_eligible": 1000 * overall_ate * selected_rows / n_rows,
            }
        )
    return results


def auuc_above_random(curve: list[dict[str, float | int]]) -> float:
    """Area between the observed ranking policy and random targeting."""
    x = np.array([0.0, *[float(point["fraction"]) for point in curve]])
    observed = np.array([0.0, *[float(point["incremental_per_1000_eligible"]) for point in curve]])
    random = np.array([0.0, *[float(point["random_policy_per_1000_eligible"]) for point in curve]])
    return float(np.trapezoid(observed - random, x))


def value_at_fraction(
    curve: list[dict[str, float | int]], fraction: float
) -> dict[str, float | int]:
    """Select the evaluated point nearest a requested reach."""
    return min(curve, key=lambda point: abs(float(point["fraction"]) - fraction))


def paired_policy_difference(
    first_scores: np.ndarray,
    second_scores: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    *,
    fraction: float,
    first_label: str,
    second_label: str,
) -> dict[str, float | int | str | bool]:
    """Compare two equal-reach policies using paired randomized-test influence values."""
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1].")
    first_scores = np.asarray(first_scores, dtype=float)
    second_scores = np.asarray(second_scores, dtype=float)
    treatment = np.asarray(treatment, dtype=np.int8)
    outcome = np.asarray(outcome, dtype=float)
    if not (len(first_scores) == len(second_scores) == len(treatment) == len(outcome)):
        raise ValueError("Policy scores, treatment, and outcome must have equal lengths.")

    n_rows = len(outcome)
    selected_rows = max(1, min(n_rows, int(round(fraction * n_rows))))
    first_selected = np.zeros(n_rows, dtype=bool)
    second_selected = np.zeros(n_rows, dtype=bool)
    first_selected[np.argsort(-first_scores, kind="stable")[:selected_rows]] = True
    second_selected[np.argsort(-second_scores, kind="stable")[:selected_rows]] = True
    influence = transformed_outcome(treatment, outcome)
    paired_influence = influence * (first_selected.astype(float) - second_selected.astype(float))
    estimate = 1000 * float(paired_influence.mean())
    standard_error = 1000 * float(paired_influence.std(ddof=1) / np.sqrt(n_rows))
    margin = 1.959963984540054 * standard_error
    ci_low = estimate - margin
    ci_high = estimate + margin
    return {
        "first_policy": first_label,
        "second_policy": second_label,
        "fraction": selected_rows / n_rows,
        "selected_rows_per_policy": selected_rows,
        "overlap_rows": int((first_selected & second_selected).sum()),
        "difference_per_1000_eligible": estimate,
        "standard_error": standard_error,
        "ci_95_low": ci_low,
        "ci_95_high": ci_high,
        "clear_first_policy_advantage": ci_low > 0,
        "clear_second_policy_advantage": ci_high < 0,
    }


def uplift_calibration(
    scores: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    *,
    bins: int = 10,
) -> list[dict[str, float | int]]:
    """Compare predicted and realized treatment effects by score group."""
    scores = np.asarray(scores, dtype=float)
    influence = transformed_outcome(treatment, outcome)
    frame = pd.DataFrame({"score": scores, "influence": influence})
    frame["bin"] = pd.qcut(frame["score"], q=bins, labels=False, duplicates="drop")
    summary = (
        frame.groupby("bin", observed=True)
        .agg(
            rows=("score", "size"),
            predicted_uplift=("score", "mean"),
            realized_uplift=("influence", "mean"),
        )
        .reset_index()
        .sort_values("predicted_uplift", ascending=False)
    )
    return [
        {
            "rank": rank,
            "rows": int(row.rows),
            "predicted_uplift": float(row.predicted_uplift),
            "realized_uplift": float(row.realized_uplift),
        }
        for rank, row in enumerate(summary.itertuples(index=False), start=1)
    ]
