# Threshold Audit

Predict positive: score > 0.8

Input SHA-256: `e0a6395610cf6feee9c0f172e6f01350b87a78b00535e4fe2ffdcc8affed9a5f`

| Scope | Group | N | FP | TP | FPR | TPR |
|---|---|---:|---:|---:|---:|---:|
| overall |  | 8 | 1 | 3 | 0.25 | 0.75 |
| group | A | 4 | 1 | 1 | 0.5 | 0.5 |
| group | B | 4 | 0 | 2 | 0.0 | 1.0 |

## Interpretation

- Target FPR is empirical on calibration, not a population or test guarantee.
- Wilson intervals assume independent Bernoulli observations and a fixed threshold on held-out test data.
- Calibration intervals are descriptive only: threshold selection uses these same observations.
- Group intervals are marginal, not simultaneous; correlated samples invalidate nominal coverage.
- Unique IDs detect exact ID overlap, not duplicated content or hidden dependence.

Full counts, confidence intervals and configuration: `report.json`.
