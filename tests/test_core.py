import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from threshold_audit import audit, read_csv


def fixture(scores=(1,2,2,3)):
    rows = [dict(sample_id=f'c{i}', score=s, label=0, split='calibration') for i,s in enumerate(scores)]
    rows += [dict(sample_id='n', score=2, label=0, split='test', group='a'),
             dict(sample_id='p', score=4, label=1, split='test', group='b')]
    return rows


class AuditTests(unittest.TestCase):
    def test_ties(self):
        r = audit(fixture(), .5)
        self.assertEqual(r['threshold'], 2)
        self.assertEqual(r['calibration']['fp'], 1)
        self.assertEqual(r['overall']['tp'], 1)
        self.assertEqual(r['overall']['fp'], 0)
        self.assertIsNone(r['groups']['a']['tpr'])
        self.assertIsNone(r['groups']['b']['fpr'])

    def test_inclusive(self):
        r = audit(fixture(), .5, comparison='inclusive')
        self.assertEqual(r['threshold'], math.nextafter(2, math.inf))
        self.assertEqual(r['calibration']['fp'], 1)

    def test_lower(self):
        r = audit(fixture(), .25, direction='lower')
        self.assertEqual(r['threshold'], 2)
        self.assertEqual(r['calibration']['fp'], 1)
        self.assertEqual(r['operator'], '<')

    def test_budgets_and_directions(self):
        for scores in [(1,1,1), (-2,0,1,1,5), (0,), (1e308,-1e308)]:
            for target in [0,.1,.25,.5,.99,1]:
                for direction in ['higher','lower']:
                    for comparison in ['strict','inclusive']:
                        r = audit(fixture(scores), target, direction, comparison)
                        self.assertLessEqual(r['calibration']['fp'], r['calibration_fp_budget'])
                        json.dumps(r, allow_nan=False)

    def test_decimal_budget(self):
        self.assertEqual(audit(fixture(range(100)), .29)['calibration_fp_budget'],29)

    def test_invalid_rows(self):
        for key, value in [('score',float('nan')), ('score','bad'), ('label',2), ('split','train'), ('sample_id','')]:
            rows=fixture(); rows[0][key]=value
            with self.assertRaises(ValueError): audit(rows)
        rows=fixture(); rows[-1]['sample_id']=rows[0]['sample_id']
        with self.assertRaises(ValueError): audit(rows)
        rows=fixture(); rows[0]['label']=1
        with self.assertRaises(ValueError): audit(rows)
        for rows in [[],fixture()[:4],fixture()[4:]]:
            with self.assertRaises(ValueError): audit(rows)

    def test_invalid_config(self):
        for kwargs in [dict(target_fpr=-1),dict(target_fpr=float('nan')),dict(confidence=1),dict(direction='bad'),dict(comparison='bad')]:
            with self.assertRaises(ValueError): audit(fixture(), **kwargs)

    def test_csv_validation(self):
        for data in [b'score,score\n1,2', b'sample_id,score,label,split\nx,2,0,test,extra']:
            with self.assertRaises(ValueError): audit(read_csv(data))

    def test_wilson(self):
        r=audit(fixture())
        lo,hi=r['overall']['fpr_ci']
        self.assertAlmostEqual(lo,0)
        self.assertGreater(hi,0)

    def test_cli_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs=[]
            for i in range(2):
                out=Path(tmp)/str(i)
                subprocess.run([sys.executable,'-m','threshold_audit','examples/synthetic.csv','--direction','higher','--target-fpr','.1','--output',str(out)],check=True)
                outputs.append({p.name:p.read_bytes() for p in out.iterdir()})
            self.assertEqual(outputs[0],outputs[1])
            self.assertEqual(set(outputs[0]),{'report.json','metrics.csv','report.md'})

if __name__ == '__main__': unittest.main()
