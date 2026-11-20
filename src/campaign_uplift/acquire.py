"""Acquire and validate the public Criteo uplift dataset."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import shutil
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from campaign_uplift.config import (
    CRITEO_DATA_URL,
    CRITEO_EXPECTED_SHA256,
    CRITEO_HUGGING_FACE_COMMIT,
    CRITEO_LICENSE,
    CRITEO_SOURCE_PAGE,
    DEFAULT_DATA_PATH,
    EXPECTED_COLUMNS,
    EXPECTED_COMPRESSED_BYTES,
)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    """Calculate a file hash without loading the file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_archive(path: Path) -> dict[str, object]:
    """Validate gzip integrity and the source CSV schema."""
    if not path.exists():
        raise FileNotFoundError(path)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = tuple(next(reader))
        first_row = next(reader)
    missing = sorted(set(EXPECTED_COLUMNS) - set(header))
    if missing:
        raise ValueError(f"Dataset is missing expected columns: {missing}")
    if len(first_row) != len(header):
        raise ValueError("The first data row does not match the header width.")
    observed_bytes = path.stat().st_size
    observed_sha256 = sha256_file(path)
    if observed_bytes != EXPECTED_COMPRESSED_BYTES:
        raise ValueError(
            f"Dataset byte size mismatch: expected {EXPECTED_COMPRESSED_BYTES}, "
            f"observed {observed_bytes}."
        )
    if observed_sha256 != CRITEO_EXPECTED_SHA256:
        raise ValueError(
            f"Dataset SHA-256 mismatch: expected {CRITEO_EXPECTED_SHA256}, "
            f"observed {observed_sha256}."
        )
    return {
        "path": path.as_posix(),
        "bytes": observed_bytes,
        "sha256": observed_sha256,
        "columns": list(header),
        "mirror_commit": CRITEO_HUGGING_FACE_COMMIT,
    }


def download_dataset(
    destination: Path = DEFAULT_DATA_PATH,
    *,
    url: str = CRITEO_DATA_URL,
    force: bool = False,
) -> dict[str, object]:
    """Download the dataset atomically and record its provenance."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = destination.with_suffix(destination.suffix + ".metadata.json")

    if destination.exists() and not force:
        metadata = validate_archive(destination)
        metadata.update(
            {
                "source_url": url,
                "source_page": CRITEO_SOURCE_PAGE,
                "license": CRITEO_LICENSE,
                "status": "reused_existing_file",
            }
        )
        return metadata

    partial = destination.with_suffix(destination.suffix + ".part")
    if partial.exists():
        partial.unlink()
    request = urllib.request.Request(url, headers={"User-Agent": "campaign-uplift-optimizer/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as target:
            shutil.copyfileobj(response, target, length=1024 * 1024)
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise

    metadata = validate_archive(destination)
    metadata.update(
        {
            "source_url": url,
            "source_page": CRITEO_SOURCE_PAGE,
            "license": CRITEO_LICENSE,
            "downloaded_at_utc": datetime.now(UTC).isoformat(),
            "status": "downloaded",
        }
    )
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata
