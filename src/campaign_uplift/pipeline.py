"""End-to-end model selection, locked-test evaluation, and result generation."""

from __future__ import annotations

import json
import platform
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from campaign_uplift.config import (
    CRITEO_LICENSE,
    CRITEO_SOURCE_PAGE,
    FEATURE_COLUMNS,
    OUTCOME_COLUMN,
    TREATMENT_COLUMN,
    PipelineConfig,
)
from campaign_uplift.data import grouped_hash_split, summarize_frame, validate_frame
from campaign_uplift.metrics import (
    auuc_above_random,
    experiment_summary,
    paired_policy_difference,
    policy_curve,
    uplift_calibration,
    value_at_fraction,
)
from campaign_uplift.models import (
    ConversionPropensity,
    boosted_outcome_model,
    causal_candidates,
)
from campaign_uplift.optimizer import optimize_scenario, scenario_table


def _arrays(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    features = frame.loc[:, list(FEATURE_COLUMNS)].to_numpy(dtype=np.float32, copy=False)
    treatment = frame[TREATMENT_COLUMN].to_numpy(dtype=np.int8, copy=False)
    outcome = frame[OUTCOME_COLUMN].to_numpy(dtype=np.int8, copy=False)
    return features, treatment, outcome


def _evaluate_scores(
    scores: np.ndarray, treatment: np.ndarray, outcome: np.ndarray
) -> tuple[list[dict[str, float | int]], float]:
    curve = policy_curve(scores, treatment, outcome)
    return curve, auuc_above_random(curve)


def run_analysis(
    frame: pd.DataFrame,
    *,
    source_metadata: dict[str, object],
    config: PipelineConfig,
) -> dict[str, object]:
    """Select on validation data and report final results on untouched test data."""
    started = time.perf_counter()
    config.validate()
    validate_frame(frame)
    splits = grouped_hash_split(
        frame,
        train_percent=config.train_percent,
        validation_percent=config.validation_percent,
    )
    x_train, t_train, y_train = _arrays(splits.train)
    x_validation, t_validation, y_validation = _arrays(splits.validation)
    x_test, t_test, y_test = _arrays(splits.test)

    candidates = causal_candidates(
        seed=config.seed,
        max_iter=config.max_boost_iterations,
        min_samples_leaf=config.min_samples_leaf,
    )
    validation_results: dict[str, dict[str, object]] = {}
    fitted: dict[str, object] = {}

    for name, learner in candidates.items():
        model_started = time.perf_counter()
        learner.fit(x_train, t_train, y_train)
        validation_scores = learner.predict_uplift(x_validation)
        validation_curve, validation_auuc = _evaluate_scores(
            validation_scores, t_validation, y_validation
        )
        validation_results[name] = {
            "validation_auuc_above_random": validation_auuc,
            "validation_curve": validation_curve,
            "fit_seconds": time.perf_counter() - model_started,
        }
        fitted[name] = learner

    selected_model = max(
        validation_results,
        key=lambda name: float(validation_results[name]["validation_auuc_above_random"]),
    )

    propensity = ConversionPropensity(
        boosted_outcome_model(
            seed=config.seed + 11,
            max_iter=config.max_boost_iterations,
            min_samples_leaf=config.min_samples_leaf,
        )
    ).fit(x_train, y_train)
    propensity_validation_scores = propensity.predict_score(x_validation)
    propensity_validation_curve, propensity_validation_auuc = _evaluate_scores(
        propensity_validation_scores, t_validation, y_validation
    )

    selected_validation_curve = validation_results[selected_model]["validation_curve"]
    selected_validation_scenario = optimize_scenario(
        selected_validation_curve,
        population=config.default_population,
        contact_cost=config.default_contact_cost,
        conversion_value=config.default_conversion_value,
        max_reach=config.default_max_reach,
    )
    selected_fraction = float(selected_validation_scenario["fraction"])

    test_results: dict[str, dict[str, object]] = {}
    selected_scores: np.ndarray | None = None
    for name, learner in fitted.items():
        scores = learner.predict_uplift(x_test)
        curve, auuc = _evaluate_scores(scores, t_test, y_test)
        test_results[name] = {
            "test_auuc_above_random": auuc,
            "test_curve": curve,
        }
        if name == selected_model:
            selected_scores = scores

    if selected_scores is None:
        raise RuntimeError("Selected model scores were not produced.")

    propensity_test_scores = propensity.predict_score(x_test)
    propensity_test_curve, propensity_test_auuc = _evaluate_scores(
        propensity_test_scores, t_test, y_test
    )
    rng = np.random.default_rng(config.seed + 99)
    random_test_scores = rng.random(len(x_test))
    random_test_curve, random_test_auuc = _evaluate_scores(random_test_scores, t_test, y_test)

    selected_test_curve = test_results[selected_model]["test_curve"]
    selected_test_point = value_at_fraction(selected_test_curve, selected_fraction)
    locked_test_scenario = scenario_table(
        [selected_test_point],
        population=config.default_population,
        contact_cost=config.default_contact_cost,
        conversion_value=config.default_conversion_value,
        max_reach=1.0,
    )[0]
    uplift_vs_propensity = paired_policy_difference(
        selected_scores,
        propensity_test_scores,
        t_test,
        y_test,
        fraction=selected_fraction,
        first_label="uplift",
        second_label="conversion_propensity",
    )
    uplift_vs_random = paired_policy_difference(
        selected_scores,
        random_test_scores,
        t_test,
        y_test,
        fraction=selected_fraction,
        first_label="uplift",
        second_label="random_targeting",
    )
    if uplift_vs_propensity["clear_first_policy_advantage"]:
        policy_conclusion = "uplift_clearly_outperforms_propensity"
    elif uplift_vs_propensity["clear_second_policy_advantage"]:
        policy_conclusion = "propensity_clearly_outperforms_uplift"
    else:
        policy_conclusion = "no_clear_uplift_propensity_winner"

    comparison = []
    for name in candidates:
        comparison.append(
            {
                "model": name,
                "category": "causal_uplift",
                "selected": name == selected_model,
                "validation_auuc_above_random": float(
                    validation_results[name]["validation_auuc_above_random"]
                ),
                "test_auuc_above_random": float(test_results[name]["test_auuc_above_random"]),
                "fit_seconds": float(validation_results[name]["fit_seconds"]),
            }
        )
    comparison.extend(
        [
            {
                "model": "conversion_propensity",
                "category": "predictive_baseline",
                "selected": False,
                "validation_auuc_above_random": propensity_validation_auuc,
                "test_auuc_above_random": propensity_test_auuc,
                "fit_seconds": None,
            },
            {
                "model": "random_targeting",
                "category": "random_baseline",
                "selected": False,
                "validation_auuc_above_random": None,
                "test_auuc_above_random": random_test_auuc,
                "fit_seconds": None,
            },
        ]
    )

    source_type = str(source_metadata.get("source_type", "real_criteo"))
    results: dict[str, object] = {
        "schema_version": "1.0",
        "status": (
            "portfolio_real_data" if source_type == "real_criteo" else "synthetic_development_only"
        ),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "elapsed_seconds": time.perf_counter() - started,
        },
        "configuration": asdict(config),
        "source": {
            **source_metadata,
            "publisher_page": CRITEO_SOURCE_PAGE,
            "dataset_license": CRITEO_LICENSE,
            "raw_data_committed": False,
        },
        "dataset": {
            "overall": summarize_frame(frame),
            "train": summarize_frame(splits.train),
            "validation": summarize_frame(splits.validation),
            "test": summarize_frame(splits.test),
            "split_method": "Stable feature-vector hash; identical covariates stay in one split.",
        },
        "experiment": experiment_summary(t_test, y_test),
        "selection": {
            "selected_model": selected_model,
            "selection_metric": "validation AUUC above random",
            "selected_reach_on_validation": selected_fraction,
            "test_set_used_for_selection": False,
        },
        "model_comparison": comparison,
        "policy_curves": {
            "uplift": selected_test_curve,
            "propensity": propensity_test_curve,
            "random": random_test_curve,
        },
        "calibration": uplift_calibration(selected_scores, t_test, y_test),
        "policy_comparison_at_selected_reach": {
            "uplift_vs_propensity": uplift_vs_propensity,
            "uplift_vs_random": uplift_vs_random,
            "conclusion": policy_conclusion,
            "recommendation": (
                "Run uplift and propensity policies head-to-head at equal reach in a new "
                "randomized experiment; retain random holdout traffic."
            ),
        },
        "default_scenario": {
            "inputs": {
                "population": config.default_population,
                "contact_cost": config.default_contact_cost,
                "conversion_value": config.default_conversion_value,
                "max_reach": config.default_max_reach,
            },
            "validation_optimized_policy": selected_validation_scenario,
            "locked_test_result_at_selected_reach": locked_test_scenario,
            "monetary_values_are_user_defined_scenarios": True,
        },
        "limitations": [
            (
                "The dataset contains anonymized features, so the project cannot prescribe "
                "operational feature definitions."
            ),
            (
                "Financial values are user-supplied scenarios; the dataset contains no revenue "
                "or campaign cost."
            ),
            "Offline policy estimates require confirmation in a new randomized experiment.",
            (
                "The dataset license is non-commercial and separate from the MIT-licensed "
                "project code."
            ),
            "No demographic attributes are available, so demographic fairness is not evaluated.",
        ],
    }
    return results


def _fmt_percent(value: float, digits: int = 2) -> str:
    return f"{100 * value:.{digits}f}%"


def executive_summary(results: dict[str, object]) -> str:
    """Create a decision memo directly from the machine-readable result."""
    experiment = results["experiment"]
    selection = results["selection"]
    scenario = results["default_scenario"]["locked_test_result_at_selected_reach"]
    comparison = results["policy_comparison_at_selected_reach"]
    paired = comparison["uplift_vs_propensity"]
    status = results["status"]
    title = "Campaign Uplift Optimizer — Executive Decision Memo"
    return f"""# {title}

## Decision

The validation process selected **{selection["selected_model"]}** at a campaign reach of
**{_fmt_percent(float(selection["selected_reach_on_validation"]), 0)}**. On the untouched test
set, the corresponding policy estimates **{float(scenario["incremental_conversions"]):,.1f}**
incremental conversions per {int(results["configuration"]["default_population"]):,} eligible
customers under the default scenario.

## Experimental baseline

- Control conversion rate: {_fmt_percent(float(experiment["control_conversion_rate"]), 3)}
- Treatment conversion rate: {_fmt_percent(float(experiment["treated_conversion_rate"]), 3)}
- Average treatment effect: {_fmt_percent(float(experiment["absolute_effect"]), 3)}
- 95% confidence interval: {_fmt_percent(float(experiment["ci_95_low"]), 3)} to
  {_fmt_percent(float(experiment["ci_95_high"]), 3)}
- Two-sided p-value: {float(experiment["p_value_two_sided"]):.4g}

## Economic scenario

At a contact cost of **${float(results["configuration"]["default_contact_cost"]):.2f}** and an
assumed value of **${float(results["configuration"]["default_conversion_value"]):,.0f}** per
incremental conversion, the locked-test policy produces scenario profit of
**${float(scenario["scenario_profit"]):,.0f}**. These monetary inputs are assumptions, not
observed Criteo revenue.

## Uplift versus propensity

At equal reach, uplift minus propensity is
**{float(paired["difference_per_1000_eligible"]):+.3f} incremental conversions per 1,000 eligible**
(95% CI **{float(paired["ci_95_low"]):+.3f} to {float(paired["ci_95_high"]):+.3f}**).
Conclusion: `{comparison["conclusion"]}`. The evidence does not justify claiming uplift
superiority when this interval contains zero.

## Recommendation

Use the uplift policy as a candidate for a controlled online rollout, compare it head-to-head with
propensity targeting at equal reach, retain a permanent randomized holdout, and confirm
incremental value before production adoption. Do not treat this offline estimate as a deployed
business win.

## Reproducibility status

Result status: `{status}`. Model selection used validation data only; final performance was
reported on a separate feature-grouped test set.
"""


def write_results(
    results: dict[str, object], artifact_dir: Path = Path("artifacts")
) -> tuple[Path, Path]:
    """Write the canonical JSON result and generated decision memo."""
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result_path = artifact_dir / "results.json"
    memo_path = artifact_dir / "executive-summary.md"
    result_path.write_text(json.dumps(results, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    memo_path.write_text(executive_summary(results), encoding="utf-8")
    return result_path, memo_path
