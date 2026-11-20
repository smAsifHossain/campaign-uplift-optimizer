# Methodology

## Decision question

Which eligible customers should receive advertising because exposure changes their probability
of converting, and how does that policy change with campaign reach, contact cost, and the value
of an incremental conversion?

## Data and treatment

Criteo v2.1 contains anonymized features from advertising incrementality tests, randomized
treatment assignment, and visit and conversion outcomes. This project uses conversion as its
primary outcome and visit as a descriptive secondary outcome.

The acquisition step uses Criteo's official Hugging Face organization mirror, pinned to a specific
repository commit and verified against the published source-object SHA-256 identifier. It scans
the complete official archive. The portfolio run takes a seeded Bernoulli sample across the entire
file rather than reading a convenient prefix. Feature columns are compacted to 32-bit floats after
validation.

## Split strategy

A stable hash of all twelve anonymized feature values assigns feature groups to:

- 60% training
- 20% validation
- 20% locked test

Identical feature vectors cannot cross these boundaries. The test set is not used for model
selection, hyperparameter choice, or economic reach selection.

## Experimental baseline

The test-set average treatment effect is the treated conversion rate minus the control conversion
rate. The reported uncertainty uses a two-sample normal approximation for a difference in binary
rates. This average effect is the consistency benchmark for full-reach policy evaluation.

## Models

The candidate set is deliberately limited and auditable:

1. Regularized logistic T-learner
2. Histogram-gradient-boosted T-learner
3. Histogram-gradient-boosted S-learner

A separate conversion-propensity model acts as a non-causal targeting baseline. Random targeting
provides the policy baseline.

## Policy evaluation

The randomized test set supports inverse-propensity transformed outcomes:

```text
Y* = Y × [T / P(T=1) - (1-T) / P(T=0)]
```

For each targeting depth, the analysis ranks customers using scores produced without test-set
training and estimates incremental conversions among selected customers. It reports:

- Incremental conversions per 1,000 eligible customers
- Incremental conversions per 1,000 targeted customers
- Normal-approximation 95% intervals for policy value
- AUUC above random targeting
- Predicted-versus-realized uplift by score group
- Paired equal-reach differences between uplift and propensity policies

## Model and policy selection

The causal model with the highest validation AUUC above random is selected. The default economic
reach is also chosen on the validation curve. The locked test set then reports the chosen model
and reach once. Uplift and conversion-propensity policies are compared on the same test customers
using paired influence values, so the project can report whether either ranking is clearly better
rather than relying on two point estimates alone.

## Economics

Criteo supplies neither campaign cost nor conversion value. The optimizer therefore treats
population, contact cost, and value per incremental conversion as explicit user assumptions:

```text
scenario profit = incremental conversions × assumed conversion value
                  - targeted customers × assumed contact cost
```

These calculations are scenario estimates, not claims of historical or deployed revenue.
