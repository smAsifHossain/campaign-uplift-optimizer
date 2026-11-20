"""Explicit synthetic fixtures for tests and development only."""

from __future__ import annotations

import numpy as np
import pandas as pd

from campaign_uplift.config import FEATURE_COLUMNS


def make_synthetic_uplift_data(n_rows: int = 30_000, seed: int = 7) -> pd.DataFrame:
    """Create data with a known heterogeneous treatment effect."""
    if n_rows < 100:
        raise ValueError("n_rows must be at least 100.")
    rng = np.random.default_rng(seed)
    features = rng.normal(size=(n_rows, len(FEATURE_COLUMNS))).astype("float32")
    treatment = rng.binomial(1, 0.5, size=n_rows).astype("int8")
    baseline_logit = -3.1 + 0.55 * features[:, 0] - 0.35 * features[:, 1]
    true_uplift_logit = 0.85 * (features[:, 2] > 0.25) - 0.35 * (features[:, 3] < -0.5)
    conversion_probability = 1 / (1 + np.exp(-(baseline_logit + treatment * true_uplift_logit)))
    conversion = rng.binomial(1, conversion_probability).astype("int8")
    visit_probability = np.clip(conversion_probability * 3.4 + 0.04, 0, 0.95)
    visit = np.maximum(conversion, rng.binomial(1, visit_probability)).astype("int8")
    frame = pd.DataFrame(features, columns=FEATURE_COLUMNS)
    frame["treatment"] = treatment
    frame["conversion"] = conversion
    frame["visit"] = visit
    frame["exposure"] = treatment
    return frame
