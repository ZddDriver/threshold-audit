"""Calibration and held-out evaluation; no distribution-free FPR guarantee."""
import csv
import io
import math
from pathlib import Path
from decimal import Decimal
from statistics import NormalDist


def read_csv(path):
    content = path if isinstance(path, bytes) else Path(path).read_bytes()
    with io.StringIO(content.decode('utf-8-sig'), newline='') as f:
        reader = csv.DictReader(f)
        required = {'sample_id', 'score', 'label', 'split'}
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError('Missing or duplicate CSV headers')
        if not required.issubset(reader.fieldnames):
            raise ValueError('Required columns: sample_id, score, label, split; optional: group')
        rows = list(reader)
    return rows


def _validate(rows):
    data, seen = [], set()
    for i, row in enumerate(rows, 1):
        try:
            if None in row or any(row.get(k) is None for k in ('sample_id', 'score', 'label', 'split')):
                raise ValueError('Malformed row')
            sid = str(row['sample_id']).strip()
            if not sid or sid in seen:
                raise ValueError('Empty or duplicate sample_id (including calibration/test overlap)')
            seen.add(sid)
            label = str(row['label']).strip()
            if label not in ('0', '1'):
                raise ValueError('label must be 0 or 1')
            score = float(row['score'])
            if not math.isfinite(score):
                raise ValueError('score must be finite')
            split = str(row['split']).strip()
            if split not in ('calibration', 'test'):
                raise ValueError('split must be calibration or test')
            if split == 'calibration' and label != '0':
                raise ValueError('Calibration must contain only clean negatives (label 0)')
            data.append(dict(sample_id=sid, score=score, label=int(label), split=split,
                             group=str(row.get('group') or '').strip()))
        except (ValueError, TypeError, KeyError) as e:
            raise ValueError(f'Row {i}: {e}') from e
    if not any(r['split'] == 'calibration' for r in data):
        raise ValueError('An independent nonempty calibration split is required')
    if not any(r['split'] == 'test' for r in data):
        raise ValueError('A nonempty test split is required')
    return data


def _rate(k, n, confidence):
    if not n:
        return None, None
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    p = k / n
    d = 1 + z*z/n
    center = (p + z*z/(2*n)) / d
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return p, [max(0., center-half), min(1., center+half)]


def _metrics(rows, predicts, confidence):
    tp = sum(r['label'] == 1 and predicts(r['score']) for r in rows)
    fp = sum(r['label'] == 0 and predicts(r['score']) for r in rows)
    positives = sum(r['label'] for r in rows)
    negatives = len(rows) - positives
    fpr, fpr_ci = _rate(fp, negatives, confidence)
    tpr, tpr_ci = _rate(tp, positives, confidence)
    return dict(n=len(rows), positives=positives, negatives=negatives,
                tp=tp, fp=fp, tn=negatives-fp, fn=positives-tp,
                fpr=fpr, tpr=tpr, fpr_ci=fpr_ci, tpr_ci=tpr_ci)


def audit(rows, target_fpr=0.01, direction='higher', comparison='strict', confidence=0.95):
    """Select most permissive calibration boundary meeting empirical FPR budget.

    higher/strict means score > threshold; higher/inclusive means >=.
    lower/strict means score < threshold; lower/inclusive means <=.
    Inclusive boundaries use nextafter to exclude boundary ties, when needed.
    Labels: 0 = clean/negative; 1 = positive. All IDs must be globally unique.
    """
    if not math.isfinite(target_fpr) or not 0 <= target_fpr <= 1:
        raise ValueError('target_fpr must be finite and in [0, 1]')
    if not math.isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError('confidence must be in (0, 1)')
    if direction not in ('higher', 'lower') or comparison not in ('strict', 'inclusive'):
        raise ValueError('Invalid direction or comparison')
    data = _validate(rows)
    calibration = [r for r in data if r['split'] == 'calibration']
    test = [r for r in data if r['split'] == 'test']
    sign = 1 if direction == 'higher' else -1
    scores = sorted((sign*r['score'] for r in calibration), reverse=True)
    # Decimal prevents 0.29 * 100 becoming an accidental budget of 28.
    budget = int(Decimal(str(target_fpr)) * len(scores))
    if budget == len(scores):
        boundary = -math.inf
    else:
        boundary = scores[budget]
        if comparison == 'inclusive':
            boundary = math.nextafter(boundary, math.inf)
    threshold = sign * boundary
    def predicts(score):
        value = sign * score
        return value > boundary if comparison == 'strict' else value >= boundary
    operator = ('>' if comparison == 'strict' else '>=') if sign == 1 else ('<' if comparison == 'strict' else '<=')
    # String infinities keep the exported JSON compliant with RFC 8259.
    encoded_threshold = threshold if math.isfinite(threshold) else ('Infinity' if threshold > 0 else '-Infinity')
    groups = sorted({r['group'] for r in test})
    return dict(schema_version=1, config=dict(target_fpr=target_fpr, direction=direction,
                comparison=comparison, confidence=confidence), threshold=encoded_threshold,
                operator=operator, calibration_fp_budget=budget,
                calibration=_metrics(calibration, predicts, confidence),
                overall=_metrics(test, predicts, confidence),
                groups={g: _metrics([r for r in test if r['group']==g], predicts, confidence) for g in groups},
                assumptions=['Target FPR is empirical on calibration, not a population or test guarantee.',
                'Wilson intervals assume independent Bernoulli observations and a fixed threshold on held-out test data.',
                'Calibration intervals are descriptive only: threshold selection uses these same observations.',
                'Group intervals are marginal, not simultaneous; correlated samples invalidate nominal coverage.',
                'Unique IDs detect exact ID overlap, not duplicated content or hidden dependence.'])
