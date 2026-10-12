"""Retrospective error descriptions; never used as model inputs or new labels."""
from collections import Counter
import numpy as np
import pandas as pd
from glucotwin.episodes import alarm_times, assess


def audit_errors(record, scores, cutoff):
    times = pd.DatetimeIndex(record['times'])
    episodes = pd.DatetimeIndex(record['episodes'])
    glucose = record['glucose']
    alarms = alarm_times(times, scores, cutoff, 60)
    metrics = assess(alarms, episodes, times, glucose)
    categories = Counter()
    matched = set()
    for alarm in alarms:
        candidates = episodes[(episodes >= alarm+pd.Timedelta(minutes=5)) &
                              (episodes <= alarm+pd.Timedelta(minutes=30))]
        available = [e for e in candidates if e not in matched]
        if available:
            matched.add(available[0]); categories['matched'] += 1
        elif len(candidates):
            categories['redundant'] += 1
        else:
            future = glucose.reindex(pd.date_range(alarm+pd.Timedelta(minutes=5), periods=9, freq='5min'))
            if not np.isfinite(future).all():
                categories['unknown'] += 1
            elif any((episodes >= alarm-pd.Timedelta(minutes=30)) & (episodes <= alarm)):
                categories['false_after_recent_onset'] += 1
            elif any((episodes > alarm+pd.Timedelta(minutes=30)) & (episodes <= alarm+pd.Timedelta(minutes=60))):
                categories['false_before_later_onset'] += 1
            elif (future.iloc[:6] > 180).any():
                categories['false_high_readings_without_qualifying_onset'] += 1
            else:
                categories['false_no_high_reading_in_window'] += 1
    misses = Counter()
    for onset in episodes:
        eligible = (times >= onset-pd.Timedelta(minutes=30)) & (times <= onset-pd.Timedelta(minutes=5))
        if not eligible.any():
            misses['no_eligible_opportunity'] += 1
        elif onset in matched:
            misses['detected'] += 1
        elif (np.asarray(scores)[eligible] >= cutoff).any():
            misses['missed_with_cutoff_crossing_during_cooldown'] += 1
        else:
            misses['missed_below_cutoff'] += 1
    assert sum(categories.values()) == metrics['alarms']
    assert sum(v for k,v in categories.items() if k.startswith('false_')) == metrics['false_alarms']
    assert categories['matched'] == metrics['detected_episodes']
    assert categories['unknown'] == metrics['unknown_alarms']
    assert sum(misses.values()) == metrics['qualifying_episodes']
    assert misses['detected'] == metrics['detected_episodes']
    assert sum(misses[k] for k in ('detected','missed_with_cutoff_crossing_during_cooldown','missed_below_cutoff')) == metrics['evaluable_episodes']
    return dict(metrics=metrics, alarm_categories=dict(categories), episode_categories=dict(misses))
