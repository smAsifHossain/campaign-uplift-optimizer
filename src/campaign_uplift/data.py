"""Memory-conscious loading, validation, and leakage-resistant splitting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from campaign_uplift.config import (
    EXPECTED_COLUMNS,
    FEATURE_COLUMNS,
    OUTCOME_COLUMN,
    SECONDARY_OUTCOME_COLUMN,
    TREATMENT_COLUMN,
)


@dataclass(frozen=True)
class DataSplits:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


def validate_frame(frame: pd.DataFrame) -> None:
    """Enforce the minimal analytical data contract."""
    missing = sorted(set(EXPECTED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing expected columns: {missing}")
    for column in (TREATMENT_COLUMN, OUTCOME_COLUMN, SECONDARY_OUTCOME_COLUMN):
        values = set(frame[column].dropna().unique().tolist())
        if not values.issubset({0, 1}):
            raise ValueError(f"{column} must be binary; observed {sorted(values)}")
    if frame.empty:
        raise ValueError("The analytical frame is empty.")


def _compact_dtypes(frame: pd.DataFrame) -> pd.DataFrame:
    compact = frame.copy()
    compact.loc[:, list(FEATURE_COLUMNS)] = compact.loc[:, list(FEATURE_COLUMNS)].astype("float32")
    for column in (TREATMENT_COLUMN, OUTCOME_COLUMN, SECONDARY_OUTCOME_COLUMN, "exposure"):
        compact[column] = compact[column].astype("int8")
    return compact


def sample_gzip_csv(
    path: Path,
    *,
    fraction: float,
    seed: int,
    chunk_size: int = 400_000,
) -> tuple[pd.DataFrame, dict[str, int | float]]:
    """Draw a deterministic Bernoulli sample while scanning every source row."""
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1].")
    rng = np.random.default_rng(seed)
    selected: list[pd.DataFrame] = []
    scanned_rows = 0

    for chunk in pd.read_csv(path, compression="gzip", chunksize=chunk_size):
        missing = sorted(set(EXPECTED_COLUMNS) - set(chunk.columns))
        if missing:
            raise ValueError(f"Source data is missing columns: {missing}")
        mask = rng.random(len(chunk)) < fraction
        selected.append(chunk.loc[mask, list(EXPECTED_COLUMNS)])
        scanned_rows += len(chunk)

    if not selected:
        raise ValueError("No CSV chunks were read.")
    sample = pd.concat(selected, ignore_index=True)
    sample = _compact_dtypes(sample)
    validate_frame(sample)
    return sample, {
        "rows_scanned": scanned_rows,
        "rows_sampled": len(sample),
        "requested_sample_fraction": fraction,
        "realized_sample_fraction": len(sample) / scanned_rows,
    }


def grouped_hash_split(
    frame: pd.DataFrame,
    *,
    train_percent: int = 60,
    validation_percent: int = 20,
) -> DataSplits:
    """Keep identical feature vectors in one split to prevent leakage."""
    if train_percent + validation_percent >= 100:
        raise ValueError("train_percent + validation_percent must be below 100.")
    feature_hash = pd.util.hash_pandas_object(
        frame.loc[:, list(FEATURE_COLUMNS)], index=False, hash_key="uplift2026112000"
    ).to_numpy(dtype="uint64")
    bucket = feature_hash % np.uint64(100)
    train_mask = bucket < train_percent
    validation_mask = (bucket >= train_percent) & (bucket < train_percent + validation_percent)
    test_mask = bucket >= train_percent + validation_percent
    splits = DataSplits(
        train=frame.loc[train_mask].reset_index(drop=True),
        validation=frame.loc[validation_mask].reset_index(drop=True),
        test=frame.loc[test_mask].reset_index(drop=True),
    )
    if min(len(splits.train), len(splits.validation), len(splits.test)) == 0:
        raise ValueError("At least one data split is empty.")
    return splits


def summarize_frame(frame: pd.DataFrame) -> dict[str, object]:
    """Return non-identifying aggregate diagnostics."""
    validate_frame(frame)
    treatment_rate = float(frame[TREATMENT_COLUMN].mean())
    return {
        "rows": int(len(frame)),
        "treatment_rate": treatment_rate,
        "control_rate": 1.0 - treatment_rate,
        "conversion_rate": float(frame[OUTCOME_COLUMN].mean()),
        "visit_rate": float(frame[SECONDARY_OUTCOME_COLUMN].mean()),
        "missing_values": int(frame.isna().sum().sum()),
        "duplicate_feature_rows": int(frame.duplicated(subset=list(FEATURE_COLUMNS)).sum()),
    }
