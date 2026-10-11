"""Audit original DCLP3 files without interpolation, cohort selection or fitting.

Only aggregates are written to the public report. Event-level files, participant
keys and source document conversions stay under ignored data directories.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import json
import time

import numpy as np
import pandas as pd


def encoding(path):
    with path.open('rb') as handle:
        return 'utf-16' if handle.read(2) in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig'


def read(path, **kwargs):
    return pd.read_csv(path, sep='|', encoding=encoding(path), dtype=str,
                       keep_default_na=False, **kwargs)


def dates(values, sas=False):
    return pd.to_datetime(values, format='%d%b%y:%H:%M:%S' if sas else
                          '%Y-%m-%d %H:%M:%S', errors='coerce')


def counts(values):
    return {str(k): int(v) for k, v in values.value_counts(dropna=False).items()}


def distribution(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return dict(zip(('min', 'p25', 'median', 'p75', 'max'),
                    map(float, np.quantile(values, (0, .25, .5, .75, 1))))) if len(values) else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(
        'data/raw/DCLP3 Public Dataset - Release 3 - 2022-08-04'))
    parser.add_argument('--output', type=Path, default=Path('reports/dclp3_audit.json'))
    args = parser.parse_args()
    started = time.monotonic()
    source = args.source / 'Data Files'
    report = {'audit_utc': datetime.now(timezone.utc).isoformat(),
              'release': args.source.name,
              'scope': 'Source audit only; no modeling or final cohort admission',
              'files': {p.name: {'bytes': p.stat().st_size, 'encoding': encoding(p)}
                        for p in sorted(source.glob('*.txt'))}}
    for name, info in report['files'].items():
        info['columns'] = read(source / name, nrows=0).columns.tolist()
    roster = read(source / 'PtRoster_a.txt')
    screening = read(source / 'DiabScreening_a.txt')
    visits = read(source / 'VisitInfo_a.txt')
    assert not roster.PtID.duplicated().any(), 'Roster IDs must be unique'
    assert not visits.ParentLoginVisitID.duplicated().any(), 'Visit keys must be unique'
    report['roster'] = {'participants': len(roster), 'treatment_groups': counts(roster.trtGroup),
                        'statuses': counts(roster.PtStatus),
                        'has_randomization_date': int(roster.RandDt.ne('').sum())}
    report['screening'] = {'rows': len(screening), 'participants': screening.PtID.nunique(),
                           'age_years': distribution(pd.to_numeric(screening.AgeAtEnrollment, errors='coerce')),
                           'sex': counts(screening.Gender)}
    report['screening']['fields_present_participants'] = {
        col: int(screening.loc[screening[col].ne(''), 'PtID'].nunique())
        for col in ('AgeAtEnrollment', 'Gender', 'Weight', 'Height', 'DiagAge',
                    'UnitsInsTotal', 'SHMostRecent', 'DKAMostRecent')}
    report['screening']['weight_units'] = counts(screening.WeightUnits)
    report['screening']['height_units'] = counts(screening.HeightUnits)
    screening_visit = screening.merge(visits[['ParentLoginVisitID', 'PtID', 'Visit', 'VisitDt']],
        on=['ParentLoginVisitID', 'PtID'], how='left', validate='many_to_one')
    report['screening']['unmatched_visit_rows'] = int(screening_visit.Visit.isna().sum())
    phys = read(source / 'DiabPhysExam_a.txt')
    report['physical_exam'] = {'rows': len(phys), 'participants': phys.PtID.nunique(),
        'visits': counts(phys.Visit), 'weight_units': counts(phys.WeightUnits),
        'height_units': counts(phys.HeightUnits),
        'numeric_weight_participants': phys.loc[pd.to_numeric(phys.Weight, errors='coerce').notna(), 'PtID'].nunique(),
        'numeric_height_participants': phys.loc[pd.to_numeric(phys.Height, errors='coerce').notna(), 'PtID'].nunique()}

    # Read CGM in chunks and retain compact arrays, rather than every text field.
    series = defaultdict(list)
    periods = Counter()
    outside_values = Counter()
    bad_time = bad_value = out_of_range = total = 0
    for chunk in read(source / 'cgm.txt', chunksize=250_000):
        total += len(chunk)
        periods.update(chunk.Period)
        stamp = dates(chunk.DataDtTm, sas=True)
        value = pd.to_numeric(chunk.CGM, errors='coerce')
        bad_time += int(stamp.isna().sum())
        finite = np.isfinite(value)
        bad_value += int((~finite).sum())
        out_of_range += int((finite & ~value.between(40, 400)).sum())
        outside_values.update(chunk.loc[finite & ~value.between(40, 400), 'CGM'])
        valid = stamp.notna() & finite & value.between(40, 400)
        compact = pd.DataFrame({'PtID': chunk.PtID, 'Period': chunk.Period,
                                'time': stamp.astype('int64') // 1_000_000_000,
                                'value': value.astype('float32')}).loc[valid]
        for key, group in compact.groupby(['PtID', 'Period'], sort=False):
            series[key].append(group[['time', 'value']].to_numpy())
    print(f'CGM read: {total:,} rows', flush=True)
    cgm_ids = {key[0] for key in series}
    summary = {'rows': total, 'participants': len(cgm_ids), 'period_rows': dict(periods),
               'invalid_time_rows': bad_time, 'nonnumeric_or_nonfinite_rows': bad_value,
               'outside_40_400_rows': out_of_range, 'periods': {}}
    summary['outside_40_400_value_counts'] = dict(outside_values)
    summary['range_screen_note'] = ('40-400 used for descriptive exact-valued audit only. '
        'Out-of-range codes need a censoring policy before modeling; not automatically missing data.')
    post_spans = {}
    for period in sorted(periods):
        spans, days, cadence = [], [], Counter()
        duplicates = conflicts = gaps15 = exact30 = exact60 = retained = 0
        patient_count = 0
        low = high = 0
        for (patient, phase), arrays in series.items():
            if phase != period:
                continue
            patient_count += 1
            data = np.concatenate(arrays)
            frame = pd.DataFrame(data, columns=['time', 'value'])
            frame['time'] = frame.time.astype('int64')
            grouped = frame.groupby('time').value.agg(['first', 'nunique', 'size'])
            duplicates += int((grouped['size'] - 1).sum())
            conflicts += int((grouped['nunique'] > 1).sum())
            clean = grouped.loc[grouped['nunique'].eq(1)]
            ts = clean.index.to_numpy()
            vals = clean['first'].to_numpy()
            if not len(ts):
                continue
            if period == '2. Post Randomization':
                post_spans[patient] = (int(ts[0]), int(ts[-1]))
            retained += len(ts)
            low += int((vals < 70).sum())
            high += int((vals > 180).sum())
            spans.append((ts[-1] - ts[0]) / 86400)
            days.append(len(np.unique(ts // 86400)))
            delta = np.diff(ts)
            cadence.update({'exact_300_seconds': int((delta == 300).sum()),
                            'within_270_330_seconds': int(((delta >= 270) & (delta <= 330)).sum()),
                            'positive_intervals': len(delta),
                            'under_270_seconds': int((delta < 270).sum())})
            gaps15 += int((delta > 900).sum())
            exact30 += int(np.isin(ts + 1800, ts).sum())
            exact60 += int(np.isin(ts + 3600, ts).sum())
        summary['periods'][period] = {'participants': patient_count,
            'valid_unique_nonconflicting_readings': retained,
            'extra_duplicate_rows': duplicates, 'conflicting_timestamps': conflicts,
            'span_days_per_participant': distribution(spans),
            'observed_days_per_participant': distribution(days), 'intervals': dict(cadence),
            'gaps_over_15_minutes': gaps15, 'measured_below70': low,
            'measured_above180': high, 'exact_plus30_minute_matches': exact30,
            'exact_plus60_minute_matches': exact60}
    report['cgm'] = summary
    # Pump clocks: prefer adjusted event times when populated, original otherwise.
    stream_ids = {}
    for filename, field in [('Pump_BasalRateChange.txt', 'CommandedBasalRate'),
                            ('Pump_BolusDelivered.txt', 'BolusAmount'),
                            ('RocheMeter_a.txt', 'Carbs')]:
        rows = adjusted = changed = bad = numeric_rows = positive = 0
        ids, positive_ids = set(), set()
        categories = Counter()
        events_in_post_span = 0
        overlap_ids = set()
        minima, maxima = [], []
        for chunk in read(source / filename, chunksize=250_000):
            rows += len(chunk)
            ids.update(chunk.PtID)
            supplied = chunk.DataDtTm_adjusted.ne('')
            adjusted += int(supplied.sum())
            changed += int((supplied & chunk.DataDtTm_adjusted.ne(chunk.DataDtTm)).sum())
            stamp = dates(chunk.DataDtTm_adjusted.where(supplied, chunk.DataDtTm))
            bad += int(stamp.isna().sum())
            number = pd.to_numeric(chunk[field], errors='coerce')
            finite = np.isfinite(number)
            numeric_rows += int(finite.sum())
            positive += int((finite & (number > 0)).sum())
            positive_ids.update(chunk.loc[finite & (number > 0), 'PtID'])
            stamp_seconds = stamp.astype('int64') // 1_000_000_000
            lower = chunk.PtID.map({p: bounds[0] for p, bounds in post_spans.items()})
            upper = chunk.PtID.map({p: bounds[1] for p, bounds in post_spans.items()})
            in_span = finite & stamp.notna() & stamp_seconds.between(lower, upper)
            events_in_post_span += int(in_span.sum())
            overlap_ids.update(chunk.loc[in_span, 'PtID'])
            if finite.any():
                minima.append(float(number[finite].min()))
                maxima.append(float(number[finite].max()))
            for col in ('BolusType', 'IsQCtestJaeb'):
                if col in chunk:
                    categories.update(chunk[col])
        stream_ids[field] = ids
        report[field] = {'rows': rows, 'participants': len(ids),
            'numeric_rows': numeric_rows, 'positive_rows': positive,
            'participants_with_positive_values': len(positive_ids),
            'adjusted_timestamp_rows': adjusted, 'adjusted_timestamp_differs_rows': changed,
            'unparseable_effective_timestamps': bad,
            'minimum_numeric_value': min(minima) if minima else None,
            'maximum_numeric_value': max(maxima) if maxima else None,
            'numeric_events_within_post_cgm_calendar_span': events_in_post_span,
            'participants_with_numeric_events_in_post_cgm_span': len(overlap_ids),
            'categories': dict(categories)}
        print(f'{filename}: {rows:,} rows, {len(ids)} participants', flush=True)
    pump_cohort = cgm_ids & stream_ids['CommandedBasalRate'] & stream_ids['BolusAmount']
    report['linkage'] = {'cgm_basal_bolus_intersection_participants': len(pump_cohort),
        'cgm_and_screening_participants': len(cgm_ids & set(screening.PtID)),
        'pump_intersection_treatment_groups': counts(roster.loc[roster.PtID.isin(pump_cohort), 'trtGroup'])}
    labs = read(source / 'SampleResults_a.txt')
    report['central_labs'] = {'rows': len(labs), 'participants': labs.PtID.nunique(),
                             'result_types': counts(labs.ResultName), 'units': counts(labs.Units)}
    hb = labs.loc[labs.ResultName.eq('GLYHB')].copy()
    hb['analysis'] = dates(hb.AnalysisDt)
    hb['collection'] = dates(hb.CollectionDt)
    hb['rand'] = hb.PtID.map(roster.set_index('PtID').RandDt.map(
        lambda x: pd.to_datetime(x, errors='coerce')))
    usable = pd.to_numeric(hb.Value, errors='coerce').notna()
    prior = usable & hb.analysis.notna() & hb['rand'].notna() & (hb.analysis < hb['rand'])
    report['central_labs'].update({'hba1c_participants': hb.PtID.nunique(),
        'hba1c_numeric_rows': int(usable.sum()),
        'hba1c_analysis_before_randomization_participants': hb.loc[prior, 'PtID'].nunique(),
        'collection_to_analysis_days': distribution((hb.analysis - hb.collection).dt.total_seconds() / 86400),
        'hba1c_visit_labels': counts(hb.Visit)})
    local = read(source / 'DiabLocalHbA1c_a.txt')
    local['test'] = dates(local.HbA1cTestDt)
    local['rand'] = local.PtID.map(roster.set_index('PtID').RandDt.map(
        lambda x: pd.to_datetime(x, errors='coerce')))
    local_numeric = pd.to_numeric(local.HbA1cTestRes, errors='coerce').notna()
    local_pre_rand = local_numeric & local.test.notna() & local['rand'].notna() & (local.test < local['rand'])
    report['local_hba1c'] = {'rows': len(local), 'participants': local.PtID.nunique(),
        'numeric_result_participants': local.loc[local_numeric, 'PtID'].nunique(),
        'numeric_test_before_randomization_participants': local.loc[local_pre_rand, 'PtID'].nunique(),
        'visits': counts(local.Visit),
        'availability_note': 'Test date is not a verified result-arrival timestamp; requires a declared assumption.'}
    assert set(screening.PtID) <= set(roster.PtID), 'Screening IDs outside roster'
    assert cgm_ids <= set(roster.PtID), 'CGM IDs outside roster'
    report['source_checks'] = {'roster_unique': True, 'visit_join_key_unique': True,
                               'screening_and_cgm_ids_in_roster': True}
    report['duration_seconds'] = round(time.monotonic() - started, 2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(f'Aggregate audit saved in {args.output}; {report["duration_seconds"]} seconds')


if __name__ == '__main__':
    main()
