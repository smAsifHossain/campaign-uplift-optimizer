"""Interpretable causal learners and a non-causal targeting baseline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from sklearn.base import BaseEstimator, clone
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


class UpliftEstimator(Protocol):
    def fit(self, features: np.ndarray, treatment: np.ndarray, outcome: np.ndarray) -> object: ...

    def predict_uplift(self, features: np.ndarray) -> np.ndarray: ...


def linear_outcome_model() -> Pipeline:
    """A transparent, regularized probability baseline."""
    return Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=0.5,
                    max_iter=400,
                    solver="lbfgs",
                    random_state=20261120,
                ),
            ),
        ]
    )


def boosted_outcome_model(
    *, seed: int, max_iter: int = 120, min_samples_leaf: int = 100
) -> HistGradientBoostingClassifier:
    """A CPU-friendly nonlinear model with native missing-value support."""
    return HistGradientBoostingClassifier(
        learning_rate=0.08,
        max_iter=max_iter,
        max_leaf_nodes=15,
        min_samples_leaf=min_samples_leaf,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.12,
        n_iter_no_change=12,
        random_state=seed,
    )


@dataclass
class TLearner:
    """Estimate treatment and control response surfaces separately."""

    base_model: BaseEstimator
    control_model: BaseEstimator | None = None
    treatment_model: BaseEstimator | None = None

    def fit(self, features: np.ndarray, treatment: np.ndarray, outcome: np.ndarray) -> TLearner:
        treatment = np.asarray(treatment, dtype=np.int8)
        outcome = np.asarray(outcome, dtype=np.int8)
        if set(np.unique(treatment)) != {0, 1}:
            raise ValueError("Both treatment groups are required.")
        self.control_model = clone(self.base_model)
        self.treatment_model = clone(self.base_model)
        self.control_model.fit(features[treatment == 0], outcome[treatment == 0])
        self.treatment_model.fit(features[treatment == 1], outcome[treatment == 1])
        return self

    def predict_uplift(self, features: np.ndarray) -> np.ndarray:
        if self.control_model is None or self.treatment_model is None:
            raise RuntimeError("The learner must be fitted before prediction.")
        control_probability = self.control_model.predict_proba(features)[:, 1]
        treatment_probability = self.treatment_model.predict_proba(features)[:, 1]
        return np.asarray(treatment_probability - control_probability, dtype=float)


@dataclass
class SLearner:
    """Use treatment as a feature and score the two counterfactual settings."""

    model: BaseEstimator

    def fit(self, features: np.ndarray, treatment: np.ndarray, outcome: np.ndarray) -> SLearner:
        augmented = np.column_stack([features, treatment])
        self.model.fit(augmented, outcome)
        return self

    def predict_uplift(self, features: np.ndarray) -> np.ndarray:
        treated = np.column_stack([features, np.ones(len(features), dtype=np.int8)])
        control = np.column_stack([features, np.zeros(len(features), dtype=np.int8)])
        return np.asarray(
            self.model.predict_proba(treated)[:, 1] - self.model.predict_proba(control)[:, 1],
            dtype=float,
        )


@dataclass
class ConversionPropensity:
    """Predict conversion likelihood without claiming a treatment effect."""

    model: BaseEstimator

    def fit(self, features: np.ndarray, outcome: np.ndarray) -> ConversionPropensity:
        self.model.fit(features, outcome)
        return self

    def predict_score(self, features: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.predict_proba(features)[:, 1], dtype=float)


def causal_candidates(
    *, seed: int, max_iter: int, min_samples_leaf: int
) -> dict[str, UpliftEstimator]:
    """Return a deliberately small, explainable candidate set."""
    return {
        "linear_t_learner": TLearner(linear_outcome_model()),
        "boosted_t_learner": TLearner(
            boosted_outcome_model(seed=seed, max_iter=max_iter, min_samples_leaf=min_samples_leaf)
        ),
        "boosted_s_learner": SLearner(
            boosted_outcome_model(
                seed=seed + 1, max_iter=max_iter, min_samples_leaf=min_samples_leaf
            )
        ),
    }
