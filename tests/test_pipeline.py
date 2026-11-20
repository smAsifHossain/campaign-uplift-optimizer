from __future__ import annotations

import json

from campaign_uplift.config import PipelineConfig
from campaign_uplift.pipeline import run_analysis, write_results
from campaign_uplift.publish import validate_results
from campaign_uplift.synthetic import make_synthetic_uplift_data


def test_pipeline_preserves_validation_test_boundary(tmp_path) -> None:
    frame = make_synthetic_uplift_data(8_000, seed=21)
    config = PipelineConfig(
        seed=21,
        sample_fraction=1.0,
        max_boost_iterations=18,
        min_samples_leaf=25,
    )
    results = run_analysis(
        frame,
        source_metadata={"source_type": "synthetic_development"},
        config=config,
    )
    assert results["selection"]["test_set_used_for_selection"] is False
    assert results["status"] == "synthetic_development_only"
    assert results["policy_curves"]["uplift"]
    result_path, memo_path = write_results(results, tmp_path)
    validated = validate_results(result_path)
    assert validated["selection"]["selected_model"]
    memo = memo_path.read_text(encoding="utf-8")
    assert "Controlled" in memo or "Recommendation" in memo
    json.loads(result_path.read_text(encoding="utf-8"))
