"""Causal demo and export checks require no private records or model artifacts."""
import csv
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import serve_dashboard as web
from glucotwin.demo import DemoReplay
from glucotwin.reporting import csv_report,html_report


class DemoTests(unittest.TestCase):
    def test_no_files_required(self):
        with patch.object(web,'catalog',side_effect=AssertionError('private manifest read')),patch.object(web,'models',side_effect=AssertionError('artifact read')):
            service=web.Service();key,s=service.create('demo','rise')
            self.assertTrue(s['synthetic']);self.assertEqual(len(s['ledger']),2)
            self.assertIsNone(s['ledger'][0]['actual'])
            json.dumps(web.clean(s),allow_nan=False)

    def test_every_step_and_end_reset(self):
        r=DemoReplay('demo','rise');first=r.snapshot()['issue_time']
        r.advance(60)
        self.assertEqual(len(r.ledger),26);self.assertEqual(len(r.event_ledger),13)
        self.assertEqual(pd.Series([v['issued_at'] for v in r.event_ledger]).diff().dropna().unique(),pd.Timedelta(minutes=5))
        while not r.snapshot()['at_end']:r.advance(60)
        count=len(r.ledger);r.advance(60);self.assertEqual(len(r.ledger),count)
        r.reset();self.assertEqual(r.snapshot()['issue_time'],first);self.assertEqual(len(r.ledger),2)

    def test_future_edits_cannot_change_predictions(self):
        a=DemoReplay('demo','rise');b=DemoReplay('demo','rise')
        cutoff=a.clock[a.position]-pd.Timedelta(minutes=5)
        b.glucose.loc[b.glucose.index>cutoff]=900.
        b.ledger=[];b.event_ledger=[];b.issue()
        self.assertEqual(a.ledger,b.ledger);self.assertEqual(a.event_ledger,b.event_ledger)
        self.assertEqual(a.snapshot()['chart'],b.snapshot()['chart'])

    def test_delayed_reveal_and_immutable_forecast(self):
        r=DemoReplay('demo','rise');original=dict(r.ledger[0]);r.advance(30)
        self.assertIsNone(r.snapshot()['ledger'][0]['actual'])
        r.advance(5);row=r.snapshot()['ledger'][0]
        self.assertEqual(row['outcome'],'Observed');self.assertEqual(r.ledger[0],original)
        self.assertEqual(row['actual'],r.glucose.loc[original['target_time']])

    def test_gap_withholding_and_recovery(self):
        r=DemoReplay('demo','gap');r.advance(60)
        self.assertTrue(any(v['prediction'] is None for v in r.ledger))
        self.assertLess(r.snapshot()['coverage'],13)
        r.advance(60);r.advance(30)
        self.assertIsNotNone(r.snapshot()['forecasts'][0]['prediction'])

    def test_event_pending_then_revealed(self):
        r=DemoReplay('demo','rise');r.advance(60)
        rows=r.snapshot()['event_research']['ledger']
        flags=[v for v in rows if v['research_flag']]
        self.assertTrue(flags)
        r.advance(30)
        self.assertTrue(any(v['event_at'] is not None for v in r.snapshot()['event_research']['ledger']))
        r.reset()
        self.assertTrue(all(v['event_at'] is None for v in r.snapshot()['event_research']['ledger']))

    def test_exports_are_labelled_escaped_and_pending(self):
        s=web.clean(DemoReplay('demo','rise').snapshot())
        s['patient_label']='=HYPERLINK("example")<script>'
        rows=list(csv.DictReader(io.StringIO(csv_report(s))))
        self.assertTrue(all(r['patient'].startswith("'=") for r in rows))
        self.assertEqual(rows[0]['actual'],'')
        report=html_report(s)
        self.assertIn('SYNTHETIC DEMONSTRATION',report)
        self.assertNotIn('<script>',report)
        self.assertIn('Pending',report)

    def test_bad_steps_rejected(self):
        for value in (True,5.0,'5',-5,10):
            with self.assertRaises(ValueError):DemoReplay('demo','rise').advance(value)
