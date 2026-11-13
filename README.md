# Threshold Audit

A small, dependency-free Python component for **clean calibration → frozen threshold → held-out evaluation**. Useful for anomaly detectors, security scores and binary detection experiments. It does not train a model or claim a new statistical method.

## Quick start

Python 3.10+. From this repository (no installation required):

```sh
python -m threshold_audit examples/synthetic.csv --direction higher --target-fpr 0.1 --output audit-report
python -m unittest discover -s tests -v
```

Or install locally with `python -m pip install .` and run `threshold-audit` with the same arguments. This project is not currently distributed on PyPI.

For spreadsheet safety, formula-like group names in CSV are prefixed with an apostrophe; JSON preserves exact names. The input hash and parsing use the same byte snapshot.

Outputs: `report.json` (full configuration, counts, confidence intervals and input SHA-256), `metrics.csv` (overall and per-group test metrics), `report.md` (readable summary). Same bytes and configuration produce byte-identical reports; there is no run timestamp.

```python
from threshold_audit import audit, read_csv
result = audit(read_csv('examples/synthetic.csv'), target_fpr=0.1,
               direction='higher', comparison='strict')
print(result['threshold'], result['overall'])
```

## Input contract

| Column | Meaning |
|---|---|
| sample_id | Nonempty, globally unique identifier |
| score | Finite floating-point score |
| label | Exactly 0 (clean/negative) or 1 (positive) |
| split | `calibration` or `test` |
| group | Optional group name; blank/missing is a single unnamed group |

Calibration must be nonempty and contain **only label 0**. Test must be nonempty. Duplicate IDs anywhere, including across splits, are rejected. This only catches ID overlap, not copied content with different IDs. Prevent leakage yourself when creating splits. Extra named columns are ignored. Duplicate headers, missing fields, extra unnamed cells, NaN and infinity scores are rejected.

## Threshold semantics

`--direction higher` means large scores are suspicious; `lower` means small scores are suspicious. `--comparison strict` uses `>` / `<`, while `inclusive` uses `>=` / `<=`.

Normalize scores to suspiciousness (negate for lower direction). Let `n` be the number of calibration negatives and `k = floor(target_fpr * n)`. Sort descending and choose the score at zero-based index `k` as the strict boundary. Ties at the boundary are excluded as a block, so the achieved empirical FPR can be below the target. Inclusive comparisons use the next representable float above that boundary. Thus the two comparisons agree on calibration decisions but expose their precise numerical boundaries for downstream use. For target 1, choose the all-positive boundary. An extreme inclusive boundary can also be infinite. JSON represents infinities as strings `Infinity` / `-Infinity`, not invalid JSON numeric literals.

The selected boundary is the most permissive among these calibration order-statistic boundaries that satisfies the empirical FP budget. It is **not** an optimum over test scores, and no test labels or scores are used for threshold selection. Target 0 means no calibration false positives, not a guarantee of zero future false positives. The minimum nonzero empirical resolution is `1/n`.

For the included example, target 0.1 selects `score > 0.8`; calibration FP = 1/10, test FP = 1/4 and TP = 3/4. This intentionally illustrates why empirical calibration and test FPR differ.

## Statistical interpretation

- Reports include TP, FP, TN, FN, class denominators, FPR and TPR.
- An absent class gives an undefined rate/interval (`null` in JSON, blank in CSV), not zero.
- Intervals are two-sided Wilson score intervals (default 95%; change with `--confidence`). They assume independent Bernoulli observations and a fixed threshold applied to held-out data.
- Calibration intervals are descriptive only, because the threshold was selected on those observations.
- Group intervals are marginal, not simultaneous. Repeated users, correlated observations, post-hoc group searches and distribution shift require additional statistical care.
- This is an **empirical audit**, not a population-FPR guarantee, conformal procedure, hypothesis test, fairness certification or evidence of detector robustness.
- Keep the calibration split separate from model training, tuning and held-out evaluation. Never select a threshold from the test results.

## 中文说明

这是一个小型科研评测组件：用独立的干净校准集确定阈值，然后固定阈值，在测试集和各分组上报告混淆矩阵、FPR、TPR 与 Wilson 区间。不依赖 GPU，不训练模型，运行时无第三方依赖。

`label=0` 表示干净负样本；`label=1` 表示待检出的正样本。`calibration` 只能包含负样本。分数越大越可疑时选择 `--direction higher`，反之选择 `lower`。默认严格比较，不把边界同分样本计为阳性。

注意：目标 FPR 只约束校准集上的经验值，不能保证测试集或真实分布上的误报率。分组缺少正/负样本时，对应指标标记为缺失。示例数据全部为合成数据。

## Contributing and scope

Bug fixes, boundary-case tests and clearer reports are welcome. Please include a minimal synthetic reproduction and run the tests. Do not include private research data, credentials, or identifying sample records in issues. Keep the core small and dependency-free; model training and dashboards are out of scope.

MIT licensed. See [LICENSE](LICENSE).


## Contributors and acknowledgments

- [@rangerhu](https://github.com/rangerhu): contributed the Chinese README in [PR #1](https://github.com/ZddDriver/threshold-audit/pull/1).
- [@GShaol](https://github.com/GShaol): acknowledged as a project community supporter.

感谢两位参与项目交流与支持。
