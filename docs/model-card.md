# Model card

## Intended use

Demonstrate how randomized experimental evidence can support uplift ranking and campaign-policy
decisions. The project is an educational, non-commercial portfolio analysis.

## Out-of-scope use

- Production targeting without a new randomized validation experiment
- Commercial use of the Criteo dataset
- Individual-level decisions with legal, credit, employment, health, or safety consequences
- Demographic fairness conclusions
- Claims about actual marketing profit or revenue

## Inputs and outputs

Inputs are twelve anonymized numeric features. The selected causal learner outputs an estimated
individual treatment-effect ranking score. The score is used for ranking, not interpreted as a
guaranteed individual causal effect.

## Evaluation

Candidate models are selected using validation AUUC above random. Final policy curves,
calibration, paired equal-reach policy contrasts, and economic scenarios are reported on a
separate grouped test split.

## Important limitations

- Feature meanings are unavailable, preventing operational feature interpretation.
- Rare conversions create substantial uncertainty at narrow targeting depths.
- Offline randomized-policy estimates do not replace an online experiment.
- No protected demographic attributes are present.
- Campaign economics are assumed by the user, not observed in the source data.
- Data-generating conditions may differ materially from a future campaign.

## Monitoring recommendation

A production adaptation should retain a permanent randomized holdout and monitor feature drift,
treatment allocation, delayed outcome rates, uplift by score group, policy coverage, and realized
incremental value. Retraining should be triggered by evidence, not a fixed calendar alone.
