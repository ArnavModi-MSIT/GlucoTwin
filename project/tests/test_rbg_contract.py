from local_only import local_only
import sys,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

@local_only
class RbgContractTests(unittest.TestCase):
    def test_patient_roles_and_baseline_profiles(self):
        data=json.loads((ROOT/'configs/rbg_splits.json').read_text())
        rows=data['participants']
        self.assertEqual(len({r['patient_id'] for r in rows}),226)
        self.assertEqual({s:sum(r['split']==s for r in rows) for s in ['train','validation','test']},{'train':158,'validation':34,'test':34})
        self.assertTrue(all(18<=r['age_at_enrollment']<=100 and r['sex_f'] in [0,1] for r in rows))
        self.assertEqual(data['sensor_delay_minutes'],5)
        self.assertFalse(any('hba1c' in k.lower() for r in rows for k in r))

if __name__=='__main__':unittest.main()
