from __future__ import annotations

import pandas as pd

from campaign_uplift.config import FEATURE_COLUMNS
from campaign_uplift.data import grouped_hash_split, summarize_frame, validate_frame
from campaign_uplift.synthetic import make_synthetic_uplift_data


def test_synthetic_data_satisfies_contract() -> None:
    frame = make_synthetic_uplift_data(2_000, seed=4)
    validate_frame(frame)
    summary = summarize_frame(frame)
    assert summary["rows"] == 2_000
    assert 0 < summary["treatment_rate"] < 1
    assert 0 < summary["conversion_rate"] < 1


def test_identical_feature_vectors_never_cross_splits() -> None:
    frame = make_synthetic_uplift_data(3_000, seed=9)
    duplicate = frame.iloc[[0]].copy()
    duplicate.loc[:, list(FEATURE_COLUMNS)] = 777.0
    copies = pd.concat([duplicate] * 12, ignore_index=True)
    copies["treatment"] = [0, 1] * 6
    frame = pd.concat([frame, copies], ignore_index=True)
    splits = grouped_hash_split(frame)
    counts = [
        int((split.loc[:, list(FEATURE_COLUMNS)] == 777.0).all(axis=1).sum())
        for split in (splits.train, splits.validation, splits.test)
    ]
    assert sorted(counts) == [0, 0, 12]
