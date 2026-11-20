"""Project-wide configuration and data contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FEATURE_COLUMNS = tuple(f"f{i}" for i in range(12))
TREATMENT_COLUMN = "treatment"
OUTCOME_COLUMN = "conversion"
SECONDARY_OUTCOME_COLUMN = "visit"
EXPOSURE_COLUMN = "exposure"

EXPECTED_COLUMNS = (
    *FEATURE_COLUMNS,
    TREATMENT_COLUMN,
    OUTCOME_COLUMN,
    SECONDARY_OUTCOME_COLUMN,
    EXPOSURE_COLUMN,
)

CRITEO_HUGGING_FACE_COMMIT = "2424920019e49d52d72c13ac1143ec5d53af276b"
CRITEO_DATA_URL = (
    "https://huggingface.co/datasets/criteo/criteo-uplift/resolve/"
    f"{CRITEO_HUGGING_FACE_COMMIT}/criteo-research-uplift-v2.1.csv.gz?download=true"
)
CRITEO_EXPECTED_SHA256 = "2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc"
CRITEO_SOURCE_PAGE = "https://ailab.criteo.com/criteo-uplift-prediction-dataset/"
CRITEO_LICENSE = "CC BY-NC-SA 4.0"
EXPECTED_ROW_COUNT = 13_979_592
EXPECTED_COMPRESSED_BYTES = 311_422_618

DEFAULT_DATA_PATH = Path("data/raw/criteo-uplift-v2.1.csv.gz")
DEFAULT_ARTIFACT_DIR = Path("artifacts")


@dataclass(frozen=True)
class PipelineConfig:
    """Runtime settings recorded alongside every analysis result."""

    seed: int = 20261120
    sample_fraction: float = 0.10
    chunk_size: int = 400_000
    train_percent: int = 60
    validation_percent: int = 20
    max_boost_iterations: int = 120
    min_samples_leaf: int = 100
    bootstrap_repetitions: int = 300
    default_population: int = 1_000_000
    default_contact_cost: float = 0.08
    default_conversion_value: float = 120.0
    default_max_reach: float = 0.50

    def validate(self) -> None:
        """Raise a useful error for invalid settings."""
        if not 0 < self.sample_fraction <= 1:
            raise ValueError("sample_fraction must be in (0, 1].")
        if self.train_percent + self.validation_percent >= 100:
            raise ValueError("The train and validation shares must leave a test split.")
        if self.chunk_size < 1:
            raise ValueError("chunk_size must be positive.")
