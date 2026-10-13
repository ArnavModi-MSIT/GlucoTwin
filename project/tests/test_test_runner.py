"""One entry point covers both languages without recursively running tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_tests


class TestRunnerTests(unittest.TestCase):
    def test_all_js_files_and_unit_suites_are_discovered_and_integration_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'web').mkdir();(root/'tests').mkdir()
            (root/'web/new.js').write_text('');(root/'tests/new_unit.js').write_text('')
            calls=[]
            def run(command,**kw):
                calls.append((command,kw));return SimpleNamespace(stdout='v22.0.0\n',returncode=0)
            with patch.object(run_tests,'ROOT',root),patch.object(run_tests.subprocess,'run',side_effect=run):
                self.assertEqual(run_tests.main(['--node','node','--integration']),0)
            self.assertEqual(len(calls),4)
            self.assertIn('--check',calls[2][0]);self.assertTrue(calls[3][0][1].endswith('new_unit.js'))
            self.assertEqual(calls[1][1]['env']['GLUCOTWIN_INTEGRATION'],'1')
            self.assertEqual(calls[1][1]['cwd'],root)

    def test_failures_stop_the_pipeline_and_missing_node_is_actionable(self):
        with patch.object(run_tests.shutil,'which',return_value=None):self.assertEqual(run_tests.main([]),2)
        with patch.object(run_tests.subprocess,'run',side_effect=[SimpleNamespace(stdout='v22.0.0',returncode=0),SimpleNamespace(returncode=7)]) as run:
            self.assertEqual(run_tests.main(['--node','node']),7);self.assertEqual(run.call_count,2)

    def test_every_declared_requirement_is_pinned_or_an_existing_include(self):
        root=Path(__file__).resolve().parents[1]
        for name in ['requirements.txt','requirements-event.txt']:
            for line in (root/name).read_text().splitlines():
                line=line.strip()
                if not line or line.startswith('#'):continue
                if line.startswith('-r '):self.assertTrue((root/line[3:].strip()).is_file())
                else:self.assertRegex(line,r'^[a-zA-Z0-9_.-]+==[0-9][a-zA-Z0-9.]*$')
