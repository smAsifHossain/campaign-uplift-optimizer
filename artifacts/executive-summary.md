# Campaign Uplift Optimizer — Executive Decision Memo

## Decision

The validation process selected **linear_t_learner** at a campaign reach of
**20%**. On the untouched test
set, the corresponding policy estimates **901.8**
incremental conversions per 1,000,000 eligible
customers under the default scenario.

## Experimental baseline

- Control conversion rate: 0.213%
- Treatment conversion rate: 0.312%
- Average treatment effect: 0.099%
- 95% confidence interval: 0.049% to
  0.148%
- Two-sided p-value: 9.963e-05

## Economic scenario

At a contact cost of **$0.08** and an
assumed value of **$120** per
incremental conversion, the locked-test policy produces scenario profit of
**$92,211**. These monetary inputs are assumptions, not
observed Criteo revenue.

## Uplift versus propensity

At equal reach, uplift minus propensity is
**-0.047 incremental conversions per 1,000 eligible**
(95% CI **-0.139 to +0.044**).
Conclusion: `no_clear_uplift_propensity_winner`. The evidence does not justify claiming uplift
superiority when this interval contains zero.

## Recommendation

Use the uplift policy as a candidate for a controlled online rollout, compare it head-to-head with
propensity targeting at equal reach, retain a permanent randomized holdout, and confirm
incremental value before production adoption. Do not treat this offline estimate as a deployed
business win.

## Reproducibility status

Result status: `portfolio_real_data`. Model selection used validation data only; final performance was
reported on a separate feature-grouped test set.
