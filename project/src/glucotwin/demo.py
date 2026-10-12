"""Deterministic fictional patients for UI demonstration, not benchmark evidence."""
import numpy as np
import pandas as pd
from glucotwin.episodes import onsets

SCENARIOS = {
    'rise': 'Rising glucose',
    'stable': 'Stable trajectory',
    'gap': 'Sensor interruption',
}


class DemoReplay:
    """Past-only trend rule with a fictional baseline; no trained artifact required."""
    def __init__(self, cohort, pid):
        if pid not in SCENARIOS:
            raise ValueError('Unknown synthetic scenario')
        self.pid = pid
        self.clock = pd.date_range('2024-01-01', periods=145, freq='5min')
        minutes = np.arange(len(self.clock)) * 5
        values = 120 + 5 * np.sin(minutes / 32)
        if pid != 'stable':
            values = values + 110 * np.exp(-((minutes - 435) / 55) ** 2)
        if pid == 'gap':
            values[(minutes >= 395) & (minutes <= 430)] = np.nan
        self.glucose = pd.Series(np.round(values, 1), index=self.clock)
        self.start = 73  # 06:05 issue time, with readings available through 06:00.
        self.profile = {'Age': '48 years (fictional)', 'Recorded sex': 'F (fictional)',
                        'Baseline glucose': '120 mg/dL (synthetic)'}
        self.reset()

    def reset(self):
        self.position = self.start
        self.ledger = []
        self.event_ledger = []
        self.issue()

    def advance(self, minutes):
        if type(minutes) is not int or minutes not in (5, 30, 60):
            raise ValueError('Step must be 5, 30 or 60 minutes')
        end = min(self.position + minutes // 5, len(self.clock) - 1)
        while self.position < end:
            self.position += 1
            self.issue()

    def issue(self):
        now = self.clock[self.position]
        if self.ledger and self.ledger[-1]['issued_at'] == now:
            return
        cutoff = now - pd.Timedelta(minutes=5)
        history = self.glucose.reindex(pd.date_range(cutoff - pd.Timedelta(minutes=60), cutoff, freq='5min'))
        usable = history.dropna()
        latest = history.iloc[-1]
        eligible = bool(np.isfinite(latest) and history.notna().all())
        slope = (history.iloc[-1] - history.iloc[-7]) / 30 if eligible else 0.
        for horizon in (30, 60):
            # Only past measurements and the declared fictional baseline enter this rule.
            estimate = .9 * (latest + slope * (horizon + 5)) + .1 * 120 if eligible else None
            self.ledger.append(dict(issued_at=now, horizon=horizon,
                target_time=now + pd.Timedelta(minutes=horizon),
                available_at=now + pd.Timedelta(minutes=horizon + 5),
                prediction=float(estimate) if estimate is not None else None,
                persistence=float(latest) if eligible else None,
                status='Forecast issued' if eligible else 'Insufficient history',
                model_inputs=['cgm_current', 'cgm_trend_30m', 'synthetic_baseline_glucose'],
                latest_glucose=float(latest), cgm_count=len(usable)))
        score = self.ledger[-2]['prediction'] if eligible and latest <= 180 else None
        cooldown = any(r['research_flag'] and now-r['issued_at'] < pd.Timedelta(minutes=60)
                       for r in self.event_ledger)
        flag = score is not None and score >= 180 and not cooldown
        status = ('Insufficient history' if not eligible else 'Already above threshold' if latest > 180
                  else 'Illustrative flag' if flag else 'Cooldown' if score >= 180 and cooldown else 'Below cutoff')
        self.event_ledger.append(dict(issued_at=now, window_start=now+pd.Timedelta(minutes=5),
            window_end=now+pd.Timedelta(minutes=30), available_at=now+pd.Timedelta(minutes=50),
            score=score, cutoff=180., research_flag=bool(flag), status=status))

    def snapshot(self):
        now = self.clock[self.position]
        cutoff = now-pd.Timedelta(minutes=5)
        visible = self.glucose.loc[:cutoff]
        rows = []
        for issued in self.ledger:
            row = dict(issued, outcome='Pending', actual=None, ridge_error=None, persistence_error=None)
            if row['prediction'] is None:
                row['outcome'] = 'Not evaluated'
            elif row['available_at'] <= now:
                value = visible.get(row['target_time'], np.nan)
                row['outcome'] = 'Observed' if np.isfinite(value) else 'Missing observation'
                if np.isfinite(value):
                    row.update(actual=float(value), ridge_error=abs(value-row['prediction']),
                               persistence_error=abs(value-row['persistence']))
            rows.append(row)
        events = onsets(visible, 'high')
        event_rows = []
        for issued in self.event_ledger:
            row = dict(issued, outcome='Not evaluated', event_at=None, lead_minutes=None)
            if row['score'] is not None:
                row['outcome'] = 'Pending'
                if row['available_at'] <= now:
                    matches = events[(events >= row['window_start']) & (events <= row['window_end'])]
                    window = visible.reindex(pd.date_range(row['window_start'], row['window_end']+pd.Timedelta(minutes=15), freq='5min'))
                    row['outcome'] = 'No qualifying onset' if window.notna().all() else 'Incomplete observations'
                    if len(matches):
                        row.update(outcome='Qualifying onset observed', event_at=matches[0],
                                   lead_minutes=(matches[0]-row['issued_at']).total_seconds()/60)
            event_rows.append(row)
        done = [r for r in rows if r['actual'] is not None]
        return dict(cohort='demo', synthetic=True, patient_label='Synthetic · '+SCENARIOS[self.pid],
            issue_time=now, data_cutoff=cutoff, sensor_delay_minutes=5, profile=self.profile,
            profile_note='Fictional profile + past sensor trend feed an illustrative rule. No fitted ML model or clinical evidence.',
            latest=self.ledger[-1]['latest_glucose'], coverage=self.ledger[-1]['cgm_count'],
            forecasts=self.ledger[-2:], ledger=rows,
            chart=[dict(time=t, glucose=v) for t,v in visible.loc[cutoff-pd.Timedelta(hours=6):].items()],
            comparison=dict(evaluated=len(done), ridge_mae=float(np.mean([r['ridge_error'] for r in done])) if done else None,
                            persistence_mae=float(np.mean([r['persistence_error'] for r in done])) if done else None),
            event_research=dict(available=True, synthetic=True, current=self.event_ledger[-1], ledger=event_rows,
                metadata={}, probability_display_approved=False, operational_alerts_approved=False),
            model_name='Illustrative trend + fictional baseline v1', event_model_name='Synthetic trend rule · 180 mg/dL cutoff',
            at_end=self.position == len(self.clock)-1)
