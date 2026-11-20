"""Translate an evaluated uplift ranking into an economic decision."""

from __future__ import annotations


def scenario_table(
    curve: list[dict[str, float | int]],
    *,
    population: int,
    contact_cost: float,
    conversion_value: float,
    max_reach: float = 1.0,
) -> list[dict[str, float | int]]:
    """Calculate scenario economics without claiming observed revenue."""
    if population <= 0:
        raise ValueError("population must be positive.")
    if contact_cost < 0 or conversion_value < 0:
        raise ValueError("Economic inputs cannot be negative.")
    if not 0 < max_reach <= 1:
        raise ValueError("max_reach must be in (0, 1].")

    rows: list[dict[str, float | int]] = []
    for point in curve:
        fraction = float(point["fraction"])
        if fraction > max_reach + 1e-12:
            continue
        targeted = int(round(population * fraction))
        incremental = population * float(point["incremental_per_1000_eligible"]) / 1000
        incremental_low = population * float(point["ci_95_low"]) / 1000
        incremental_high = population * float(point["ci_95_high"]) / 1000
        campaign_cost = targeted * contact_cost
        profit = incremental * conversion_value - campaign_cost
        break_even_cost = incremental * conversion_value / targeted if targeted else 0.0
        rows.append(
            {
                "fraction": fraction,
                "targeted_customers": targeted,
                "incremental_conversions": incremental,
                "incremental_conversions_ci_95_low": incremental_low,
                "incremental_conversions_ci_95_high": incremental_high,
                "campaign_cost": campaign_cost,
                "scenario_profit": profit,
                "break_even_contact_cost": break_even_cost,
            }
        )
    if not rows:
        raise ValueError("No evaluated policy point is within max_reach.")
    return rows


def optimize_scenario(
    curve: list[dict[str, float | int]],
    *,
    population: int,
    contact_cost: float,
    conversion_value: float,
    max_reach: float = 1.0,
) -> dict[str, float | int | str]:
    """Return the highest estimated-profit evaluated reach."""
    rows = scenario_table(
        curve,
        population=population,
        contact_cost=contact_cost,
        conversion_value=conversion_value,
        max_reach=max_reach,
    )
    best = max(rows, key=lambda row: float(row["scenario_profit"]))
    return {
        **best,
        "recommendation": (
            "controlled_rollout" if float(best["scenario_profit"]) > 0 else "do_not_launch"
        ),
        "interpretation": (
            "Scenario value is positive; validate with a permanent randomized holdout."
            if float(best["scenario_profit"]) > 0
            else "No evaluated reach is profitable under the supplied assumptions."
        ),
    }
