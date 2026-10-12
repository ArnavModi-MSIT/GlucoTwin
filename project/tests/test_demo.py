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
from glucotwin.reporting import csv_report,html_report,history_csv_report


class DemoTests(unittest.TestCase):
    def test_feed_stores_only_received_samples(self):
        r=DemoReplay('demo','feed');s=r.snapshot()
        self.assertEqual(len(r.glucose),73)
        self.assertEqual(r.glucose.index[-1],s['data_cutoff'])
        self.assertFalse(s['at_end']);self.assertEqual(s['sensor_feed']['received'],0)
        with patch.object(r,'feed_value',side_effect=AssertionError('GET must not generate samples')):
            self.assertEqual(web.clean(r.snapshot()),web.clean(s))
        r.receive();after=r.snapshot()
        self.assertEqual(len(r.glucose),74)
        self.assertEqual(after['sensor_feed']['received'],1)
        self.assertEqual(r.glucose.index[-1],after['data_cutoff'])
        self.assertTrue(all(t<=after['data_cutoff'] for t in r.glucose.index))

    def test_feed_reveal_requires_receipt_and_preserves_predictions(self):
        r=DemoReplay('demo','feed');issued=dict(r.ledger[0])
        r.advance(30);self.assertEqual(r.snapshot()['ledger'][0]['outcome'],'Pending')
        r.receive();self.assertEqual(r.snapshot()['ledger'][0]['outcome'],'Observed')
        self.assertEqual(r.ledger[0],issued)
        self.assertEqual(r.snapshot()['sensor_feed']['received'],7)

    def test_feed_missing_target_withholding_recovery_and_reset(self):
        r=DemoReplay('demo','feed');initial=web.clean(r.snapshot())
        r.advance(30);r.receive(missing=True)
        s=r.snapshot();self.assertEqual(s['ledger'][0]['outcome'],'Missing observation')
        self.assertTrue(np.isnan(s['latest']));self.assertEqual(s['coverage'],12)
        self.assertIsNone(s['forecasts'][0]['prediction'])
        r.advance(60);self.assertIsNone(r.snapshot()['forecasts'][0]['prediction'])
        r.receive();self.assertIsNotNone(r.snapshot()['forecasts'][0]['prediction'])
        r.reset();self.assertEqual(web.clean(r.snapshot()),initial)

    def test_feed_invalid_samples_are_atomic_and_session_is_bounded(self):
        r=DemoReplay('demo','feed');before=web.clean(r.snapshot())
        for missing in ('false',None,1):
            with self.assertRaises(ValueError):r.receive(missing)
        self.assertEqual(web.clean(r.snapshot()),before)
        with self.assertRaises(ValueError):DemoReplay('demo','rise').receive()
        for _ in range(24):r.advance(60)
        self.assertTrue(r.snapshot()['at_end']);self.assertEqual(len(r.glucose),361)
        count=len(r.ledger);r.receive();r.advance(60);self.assertEqual(len(r.ledger),count)

    def test_showcase_has_past_patterns_and_replayed_outcomes(self):
        r=DemoReplay('demo','showcase');s=r.snapshot()
        self.assertEqual(next(iter(web.SCENARIOS)), 'showcase')
        self.assertTrue(s['demo_prefill'])
        self.assertEqual(s['issue_time'],pd.Timestamp('2024-01-15T08:35:00'))
        self.assertTrue(all(p['time']<=s['data_cutoff'] for p in s['chart']))
        self.assertTrue(all(p['eligible_days']>=6 for p in s['historical_patterns']['periods']))
        self.assertTrue(all(p['median'] is not None for p in s['historical_patterns']['profile']['hours']))
        self.assertGreater(s['comparison']['evaluated'],0)
        self.assertTrue(any(p['outcome']=='Pending' for p in s['ledger']))
        self.assertTrue(any(p['research_flag'] and p['event_at'] is not None
                            for p in s['event_research']['ledger']))
        before=web.clean(s);r.advance(60);r.reset()
        self.assertEqual(before,web.clean(r.snapshot()))

    def test_showcase_history_and_prefilled_ledger_remain_causal(self):
        a=DemoReplay('demo','showcase');b=DemoReplay('demo','showcase')
        cutoff=a.snapshot()['data_cutoff']
        b.glucose.loc[b.glucose.index>cutoff]=900.
        b.reset()
        self.assertEqual(web.clean(a.snapshot()),web.clean(b.snapshot()))
        self.assertFalse(DemoReplay('demo','rise').snapshot()['demo_prefill'])

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

    def test_hourly_csv_exports_only_available_summaries_and_escapes_formula(self):
        s=web.clean(DemoReplay('demo','showcase').snapshot())
        expected=len(s['historical_patterns']['hourly'])
        s['patient_label']=' \t=HYPERLINK("example")'
        future=dict(s['historical_patterns']['hourly'][-1],last_checkpoint='2024-01-16T00:55:00')
        s['historical_patterns']['hourly'].append(future)
        rows=list(csv.DictReader(io.StringIO(history_csv_report(s))))
        self.assertEqual(len(rows),expected)
        self.assertTrue(all(row['patient'].startswith("'") for row in rows))
        self.assertTrue(all(row['last_checkpoint']<=s['data_cutoff'] for row in rows))
        self.assertNotIn('prediction',rows[0]);self.assertNotIn('note',rows[0])
        s['historical_patterns']['through']='2024-01-16T00:00:00'
        with self.assertRaises(ValueError):history_csv_report(s)
