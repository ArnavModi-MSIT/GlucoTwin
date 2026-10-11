"""Full processed-cohort audit; no interpolation, feature fitting or prediction.

Public output contains cohort aggregates only. Linked participant diagnostics and
source hashes go to an ignored private file. Timestamp overlap is descriptive:
the release has no entry/upload timestamps proving prospective availability.
"""
from pathlib import Path
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import time

import numpy as np
import pandas as pd
import psutil


CHANNELS = ('bg', 'insulin', 'carbs', 'hr', 'dist', 'steps', 'cals')
REQUIRED = {'timestamp', 'device', *CHANNELS, 'activity'}
MG_DL_PER_MMOL_L = 18.0182


def canonical_stream(data, channel):
    """Reconcile identical readings; exclude conflicts and invalid numeric keys."""
    rows = data.loc[data[channel].notna(), ['timestamp', 'device', channel]].copy()
    numeric = pd.to_numeric(rows[channel], errors='coerce')
    finite = np.isfinite(numeric)
    positive_required = channel in ('bg', 'hr')
    valid = finite & (numeric > 0 if positive_required else numeric >= 0)
    rows['value'] = numeric
    rows['valid'] = valid
    grouped = rows.groupby('timestamp').agg(
        value=('value', 'first'), distinct_values=('value', 'nunique'),
        all_values_valid=('valid', 'all'), observations=('value', 'size'))
    conflicts = grouped.distinct_values > 1
    stream = grouped.loc[~conflicts & grouped.all_values_valid, 'value'].sort_index()
    gaps = stream.index.to_series().diff().dt.total_seconds().div(60).dropna()
    info = {
        'observed_rows': len(rows),
        'nonnumeric_or_nonfinite_rows': int((~finite).sum()),
        'negative_rows': int((finite & (numeric < 0)).sum()),
        'zero_rows': int((finite & (numeric == 0)).sum()),
        'invalid_rows': int((~valid).sum()),
        'distinct_timestamps': len(grouped),
        'conflicting_timestamps': int(conflicts.sum()),
        'identical_extra_rows': int((grouped.loc[(~conflicts) & grouped.all_values_valid,
                                                  'observations'] - 1).sum()),
        'retained_timestamps': len(stream),
        'median_gap_minutes': float(gaps.median()) if len(gaps) else None,
        'modal_gap_minutes': float(gaps.mode().iloc[0]) if len(gaps) else None,
        'gaps_over15_minutes': int((gaps > 15).sum()),
        'maximum_gap_minutes': float(gaps.max()) if len(gaps) else None,
        'observed_calendar_days': int(stream.index.normalize().nunique()),
        'devices': sorted(rows.device.dropna().astype(str).str.strip().unique().tolist()),
    }
    if len(stream):
        info['first_timestamp'] = stream.index.min().isoformat()
        info['last_timestamp'] = stream.index.max().isoformat()
        info['span_days'] = float((stream.index.max() - stream.index.min()).total_seconds()/86400)
        info['minimum_value'] = float(stream.min())
        info['maximum_value'] = float(stream.max())
    return stream, info


def recent_mask(anchors, stream, freshness_minutes, assumed_delay_minutes=0):
    """As-of matching only; a future observation never satisfies an anchor."""
    if not len(stream):
        return np.zeros(len(anchors), dtype=bool)
    available_before = anchors - pd.Timedelta(minutes=assumed_delay_minutes)
    positions = stream.index.searchsorted(available_before, side='right') - 1
    ages = (anchors - stream.index[np.maximum(positions, 0)]).total_seconds()/60
    return (positions >= 0) & (ages >= 0) & (ages <= freshness_minutes)


def target_support(glucose, nominal_minutes):
    """Count measured endpoints and a declared descriptive past-hour screen.

    Anchors are observation timestamps, not assertions of real ingestion times.
    This screen does not create a training matrix or fix the eventual protocol.
    """
    if not len(glucose) or nominal_minutes is None or nominal_minutes <= 0:
        return {'eligible_history_anchors': 0, 'horizons': {}}
    minimum_samples = math.ceil(.8 * (60/nominal_minutes + 1))
    counts = glucose.rolling('60min', closed='both').count()
    gaps = glucose.index.to_series().diff().dt.total_seconds().div(60)
    max_gap = gaps.rolling('60min', closed='both').max()
    history = ((glucose.index >= glucose.index[0] + pd.Timedelta(minutes=60))
               & (counts.to_numpy() >= minimum_samples)
               & (max_gap.to_numpy() <= 2*nominal_minutes))
    result = {'eligible_history_anchors': int(history.sum()),
              'minimum_past_hour_samples': minimum_samples, 'horizons': {}}
    for horizon in (30, 60):
        future = glucose.reindex(glucose.index + pd.Timedelta(minutes=horizon)).to_numpy()
        present = np.isfinite(future)
        eligible = present & history
        levels = future[eligible] * MG_DL_PER_MMOL_L
        result['horizons'][str(horizon)] = {
            'exact_measured_targets': int(present.sum()),
            'exact_targets_with_history_screen': int(eligible.sum()),
            'low_target_rows_below70_mg_dl': int((levels < 70).sum()),
            'high_target_rows_above180_mg_dl': int((levels > 180).sum()),
        }
    return result


def audit_participant(frame):
    if not REQUIRED.issubset(frame):
        raise ValueError(f'Missing source columns: {sorted(REQUIRED-set(frame))}')
    data = frame.copy()
    data['timestamp'] = pd.to_datetime(data.timestamp, errors='raise')
    if data.timestamp.isna().any():
        raise ValueError('Missing timestamps require explicit reconciliation')
    if data.timestamp.dt.tz is not None:
        raise ValueError('Unexpected timezone-aware source; specify normalization first')
    result = {'rows': len(data),
              'duplicate_timestamp_rows_across_devices': int(data.timestamp.duplicated().sum()),
              'missing_device_rows': int(data.device.isna().sum()),
              'source_timestamp_ordered': bool(data.timestamp.is_monotonic_increasing),
              'channels': {}, 'overlap': {}}
    streams = {}
    for channel in CHANNELS:
        streams[channel], result['channels'][channel] = canonical_stream(data, channel)
    anchors = streams['bg'].index
    masks = {}
    for channel in ('insulin', 'hr', 'dist', 'steps', 'cals'):
        masks[channel] = recent_mask(anchors, streams[channel], 5)
        result['overlap'][channel] = {
            'within_past5_minutes': int(masks[channel].sum()), 'glucose_anchors': len(anchors)}
    result['joint_past5_insulin_and_hr'] = int((masks['insulin'] & masks['hr']).sum())
    result['assumed_availability_scenarios'] = {}
    for delay in (0, 5, 15, 30):
        insulin = recent_mask(anchors, streams['insulin'], 30, delay)
        hr = recent_mask(anchors, streams['hr'], 30, delay)
        result['assumed_availability_scenarios'][str(delay)] = {
            'freshness_limit_minutes': 30,
            'insulin_matched': int(insulin.sum()), 'hr_matched': int(hr.sum()),
            'both_matched': int((insulin & hr).sum()), 'glucose_anchors': len(anchors)}
    result['target_support'] = target_support(streams['bg'], result['channels']['bg']['modal_gap_minutes'])
    return result


def metadata_records(path):
    data = pd.read_csv(path, encoding='cp1252', dtype=str, keep_default_na=False)
    columns = ['Participant Number', 'How old are you?',
               'What would you describe your gender as?', 'How long have you had type 1 diabetes?']
    if not set(columns).issubset(data):
        raise ValueError('Unexpected demographic schema')
    records = {}
    for _, row in data.iterrows():
        source_id = row[columns[0]].strip()
        if not re.fullmatch(r'\d{1,2}', source_id):
            raise ValueError('Unexpected demographic participant key')
        pid = f'P{int(source_id):02d}'
        if pid in records:
            raise ValueError('Duplicate demographic participant key')
        age = float(row[columns[1]])
        if not np.isfinite(age) or not 0 < age < 120:
            raise ValueError('Invalid demographic age')
        raw_gender = row[columns[2]].strip()
        normalized = raw_gender.casefold().replace('-', ' ').strip()
        categories = {'female': 'female', 'cis female': 'female', 'male': 'male',
                      'non binary': 'non_binary'}
        duration_text = row[columns[3]].strip()
        exact = re.fullmatch(r'(\d+(?:\.\d+)?)\s*years?', duration_text, flags=re.I)
        records[pid] = {'age': age, 'self_reported_gender_raw': raw_gender,
                        'gender_category': categories.get(normalized, 'unmapped'),
                        'diabetes_duration_raw': duration_text,
                        'diabetes_duration_exact_years': float(exact[1]) if exact else None}
    return records


def aggregate(records, metadata):
    pids = [r['participant_id'] for r in records]
    if len(set(pids)) != len(pids):
        raise ValueError('Duplicate participant file key')
    missing = set(pids)-set(metadata)
    if missing:
        raise ValueError(f'Unlinked participant records: {sorted(missing)}')
    linked = [metadata[p] for p in pids]
    result = {
        'scope': 'full downloaded processed cohort; descriptive audit only',
        'participants_audited': len(records), 'source_rows': sum(r['rows'] for r in records),
        'no_models_fitted': True, 'no_interpolation': True,
        'metadata': {'rows': len(metadata), 'linked_participants': len(linked),
                     'metadata_only_participants': len(set(metadata)-set(pids)),
                     'age_minimum': min(p['age'] for p in linked),
                     'age_maximum': max(p['age'] for p in linked),
                     'gender_category_counts': dict(Counter(p['gender_category'] for p in linked)),
                     'exact_duration_values': sum(p['diabetes_duration_exact_years'] is not None for p in linked),
                     'free_text_duration_values': sum(p['diabetes_duration_exact_years'] is None for p in linked)},
        'duplicate_timestamp_rows_across_devices': sum(r['duplicate_timestamp_rows_across_devices'] for r in records),
        'missing_device_rows': sum(r['missing_device_rows'] for r in records),
        'participants_with_unordered_rows': sum(not r['source_timestamp_ordered'] for r in records),
        'channels': {}, 'overlap': {}, 'assumed_availability_scenarios': {},
        'target_support': {'eligible_history_anchors': sum(r['target_support']['eligible_history_anchors'] for r in records),
                           'horizons': {}},
    }
    keys = ('observed_rows', 'nonnumeric_or_nonfinite_rows', 'negative_rows', 'zero_rows',
            'invalid_rows', 'distinct_timestamps', 'conflicting_timestamps', 'identical_extra_rows',
            'retained_timestamps', 'gaps_over15_minutes', 'observed_calendar_days')
    for channel in CHANNELS:
        stats = [r['channels'][channel] for r in records]
        out = {key: sum(p[key] for p in stats) for key in keys}
        out['participants_with_observations'] = sum(p['retained_timestamps'] > 0 for p in stats)
        out['participants_with_conflicts'] = sum(p['conflicting_timestamps'] > 0 for p in stats)
        out['modal_cadence_minutes_participant_counts'] = dict(Counter(
            str(p['modal_gap_minutes']) for p in stats if p['modal_gap_minutes'] is not None))
        out['maximum_gap_minutes'] = max((p['maximum_gap_minutes'] for p in stats if p['maximum_gap_minutes'] is not None), default=None)
        out['devices'] = sorted({name for p in stats for name in p['devices']})
        result['channels'][channel] = out
    denominator = result['channels']['bg']['retained_timestamps']
    for channel in ('insulin', 'hr', 'dist', 'steps', 'cals'):
        numerator = sum(r['overlap'][channel]['within_past5_minutes'] for r in records)
        result['overlap'][channel] = {'glucose_anchors': denominator, 'within_past5_minutes': numerator,
                                      'fraction': numerator/denominator if denominator else None}
    joint = sum(r['joint_past5_insulin_and_hr'] for r in records)
    result['joint_past5_insulin_and_hr'] = {'matched': joint, 'glucose_anchors': denominator,
                                           'fraction': joint/denominator if denominator else None}
    for delay in ('0', '5', '15', '30'):
        out = {'freshness_limit_minutes': 30, 'glucose_anchors': denominator}
        for key in ('insulin_matched', 'hr_matched', 'both_matched'):
            out[key] = sum(r['assumed_availability_scenarios'][delay][key] for r in records)
            out[key+'_fraction'] = out[key]/denominator if denominator else None
        result['assumed_availability_scenarios'][delay] = out
    for horizon in ('30', '60'):
        eligible = [r['target_support']['horizons'][horizon] for r in records if horizon in r['target_support']['horizons']]
        fields = ('exact_measured_targets', 'exact_targets_with_history_screen',
                  'low_target_rows_below70_mg_dl', 'high_target_rows_above180_mg_dl')
        result['target_support']['horizons'][horizon] = {key: sum(r[key] for r in eligible) for key in fields}
        result['target_support']['horizons'][horizon]['participants_with_screened_targets'] = sum(r['exact_targets_with_history_screen'] > 0 for r in eligible)
        result['target_support']['horizons'][horizon]['participants_with_low_targets'] = sum(r['low_target_rows_below70_mg_dl'] > 0 for r in eligible)
        result['target_support']['horizons'][horizon]['participants_with_high_targets'] = sum(r['high_target_rows_above180_mg_dl'] > 0 for r in eligible)
    result['interpretation'] = {
        'source_units': 'bg mmol/L, insulin units per prior five minutes, carbs grams, hr bpm',
        'glucose_mg_dl_conversion': MG_DL_PER_MMOL_L,
        'availability': 'Recorded timestamps do not prove entry/upload availability; lag scenarios are assumptions, not measured latencies.',
        'food_missingness': 'Missing carbohydrate entries remain unreported, not zero or evidence of no meal.',
        'gender': 'Self-reported gender, not biological sex; raw values retained privately; non-binary responses are preserved.',
        'duration': 'Approximate and fractional free-text durations are not silently rounded to exact years.',
        'calendar_days': 'Sum of participant calendar days with any observed channel reading, not uninterrupted monitoring exposure.',
        'history_screen': 'At native modal CGM cadence, require one-hour source warm-up, >=80% expected inclusive past-hour samples, and no observed past-hour gap >2 cadence intervals.',
        'targets': 'Exact future observed samples only; overlapping rows are not independent episodes or patients; source time anchors do not assert real ingestion times.',
        'conflicts': 'Different values at the same participant/channel/time are excluded; identical values are reconciled. Positive glucose/HR and nonnegative action/activity values required.',
        'benchmark': 'Keep this Type 1 cohort separate from CGMacros/RBG; no train/validation/test split or score was selected.',
    }
    return result


def run(folder, metadata_path, output, private_output):
    started = time.perf_counter()
    files = sorted(p for p in Path(folder).glob('P*.csv') if re.fullmatch(r'P\d{2}', p.stem))
    if not files:
        raise ValueError('No participant CSVs found')
    metadata = metadata_records(metadata_path)
    if any(p.stem not in metadata for p in files):
        raise ValueError('Participant file lacks demographic linkage')
    records = []
    sampled_rss = 0
    process = psutil.Process()
    for index, path in enumerate(files, 1):
        frame = pd.read_csv(path, dtype={'device': 'string', 'activity': 'string'})
        report = audit_participant(frame)
        sampled_rss = max(sampled_rss, process.memory_info().rss)
        records.append({'participant_id': path.stem, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'profile': metadata[path.stem], **report})
        print(f'Audited participant file {index}/{len(files)}', flush=True)
    summary = aggregate(records, metadata)
    summary['source_provenance'] = {'demographics_sha256': hashlib.sha256(Path(metadata_path).read_bytes()).hexdigest()}
    summary['runtime'] = {'seconds': round(time.perf_counter()-started, 3),
                          'sampled_after_patient_audit_rss_mib': round(sampled_rss/1048576, 2)}
    summary['audited_at_utc'] = datetime.now(timezone.utc).isoformat()
    private = Path(private_output)
    private.parent.mkdir(parents=True, exist_ok=True)
    private.write_text(json.dumps({'participants': records}, indent=2, allow_nan=False), encoding='utf-8')
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'participants': summary['participants_audited'], 'rows': summary['source_rows'],
                      'glucose_readings': summary['channels']['bg']['retained_timestamps'],
                      'seconds': summary['runtime']['seconds']}), flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', default='data/raw/33z5jc8fa6tob21ptrugzqog08/device_data/processed_state')
    parser.add_argument('--metadata', default='data/raw/33z5jc8fa6tob21ptrugzqog08/demographic_data.csv')
    parser.add_argument('--output', default='reports/brist1d_cohort_audit.json')
    parser.add_argument('--private-output', default='data/processed/brist1d_cohort_audit_private.json')
    args = parser.parse_args()
    run(args.folder, args.metadata, args.output, args.private_output)
