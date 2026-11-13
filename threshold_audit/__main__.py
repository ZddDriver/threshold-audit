import argparse
import csv
import hashlib
import json
from pathlib import Path
from . import __version__, audit, read_csv


def main():
    p = argparse.ArgumentParser(description='Calibrate on clean negatives, freeze, audit held-out scores.')
    p.add_argument('input', type=Path)
    p.add_argument('--target-fpr', type=float, default=.01)
    p.add_argument('--direction', choices=['higher', 'lower'], required=True)
    p.add_argument('--comparison', choices=['strict', 'inclusive'], default='strict')
    p.add_argument('--confidence', type=float, default=.95)
    p.add_argument('--output', type=Path, default=Path('audit-report'))
    args = p.parse_args()
    try:
        snapshot = args.input.read_bytes()
        result = audit(read_csv(snapshot), args.target_fpr, args.direction, args.comparison, args.confidence)
        result['input_sha256'] = hashlib.sha256(snapshot).hexdigest()
        result['tool_version'] = __version__
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / 'report.json').write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')
        rows = [dict(scope='overall', group='', **result['overall'])]
        rows += [dict(scope='group', group=g, **m) for g,m in result['groups'].items()]
        with (args.output / 'metrics.csv').open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            for row in rows:
                row = row.copy()
                group = row['group']
                if group.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
                    row['group'] = "'" + group
                w.writerow({k: json.dumps(v) if isinstance(v, list) else v for k,v in row.items()})
        lines = ['# Threshold Audit', '', f"Predict positive: score {result['operator']} {result['threshold']}", '',
                 f"Input SHA-256: `{result['input_sha256']}`", '',
                 '| Scope | Group | N | FP | TP | FPR | TPR |', '|---|---|---:|---:|---:|---:|---:|']
        def cell(v):
            return str(v).replace('|', '\\|').replace('\n',' ').replace('\r',' ')
        for r in rows:
            lines.append('| '+' | '.join(cell(r[k]) if r[k] is not None else 'undefined' for k in ('scope','group','n','fp','tp','fpr','tpr'))+' |')
        lines += ['', '## Interpretation', ''] + ['- '+s for s in result['assumptions']]
        lines += ['', 'Full counts, confidence intervals and configuration: `report.json`.', '']
        (args.output/'report.md').write_text('\n'.join(lines), encoding='utf-8')
    except (ValueError, OSError, UnicodeError) as e:
        p.error(str(e))


if __name__ == '__main__':
    main()
