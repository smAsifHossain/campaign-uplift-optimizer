"""Prepare and validate the static GitHub Pages payload."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

REQUIRED_RESULT_KEYS = {
    "schema_version",
    "status",
    "dataset",
    "experiment",
    "selection",
    "model_comparison",
    "policy_curves",
    "calibration",
    "policy_comparison_at_selected_reach",
    "default_scenario",
    "limitations",
}


def validate_results(path: Path) -> dict[str, object]:
    """Fail the deployment when required analysis evidence is absent."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = sorted(REQUIRED_RESULT_KEYS - set(payload))
    if missing:
        raise ValueError(f"Result artifact is missing keys: {missing}")
    if not payload["policy_curves"].get("uplift"):
        raise ValueError("The selected uplift policy curve is empty.")
    return payload


def build_site(
    result_path: Path = Path("artifacts/results.json"),
    site_dir: Path = Path("site"),
) -> Path:
    """Copy the validated result into the committed static site."""
    validate_results(result_path)
    data_dir = Path(site_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    destination = data_dir / "results.json"
    shutil.copy2(result_path, destination)
    validate_site(site_dir)
    return destination


def validate_site(site_dir: Path = Path("site")) -> None:
    """Check the files that GitHub Pages will publish."""
    site_dir = Path(site_dir)
    required = [
        site_dir / "index.html",
        site_dir / "styles.css",
        site_dir / "app.js",
        site_dir / "data" / "results.json",
    ]
    missing = [path.as_posix() for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Static site is incomplete: {missing}")
    validate_results(site_dir / "data" / "results.json")
