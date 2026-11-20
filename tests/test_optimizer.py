from __future__ import annotations

from campaign_uplift.optimizer import optimize_scenario, scenario_table

CURVE = [
    {
        "fraction": 0.1,
        "incremental_per_1000_eligible": 0.3,
        "ci_95_low": 0.2,
        "ci_95_high": 0.4,
    },
    {
        "fraction": 0.2,
        "incremental_per_1000_eligible": 0.5,
        "ci_95_low": 0.3,
        "ci_95_high": 0.7,
    },
]


def test_scenario_table_uses_incremental_effect_not_total_conversion() -> None:
    rows = scenario_table(
        CURVE,
        population=1_000_000,
        contact_cost=0.05,
        conversion_value=100,
    )
    assert rows[0]["incremental_conversions"] == 300
    assert rows[0]["campaign_cost"] == 5_000


def test_optimizer_respects_maximum_reach() -> None:
    result = optimize_scenario(
        CURVE,
        population=1_000_000,
        contact_cost=0.05,
        conversion_value=100,
        max_reach=0.1,
    )
    assert result["fraction"] == 0.1
    assert result["recommendation"] == "controlled_rollout"
