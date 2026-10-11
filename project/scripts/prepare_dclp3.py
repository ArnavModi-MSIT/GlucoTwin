"""Freeze roles and prepare development-only DCLP3 endpoint matrices."""
from pathlib import Path
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from glucotwin.dclp3 import assign_roles, canonical_cgm, issue_times, measured_targets, make_features, feature_arms
from audit_dclp3 import read, dates

def configure(version):
    global PROTOCOL, ROLES, CACHE, CONTRACT_REPORT, PREPARATION_REPORT
    PROTOCOL = ROOT/f'configs/dclp3_contract_v{version}.json'
    ROLES = ROOT/f'configs/dclp3_roles_v{version}.json'
    CACHE = ROOT/f'data/processed/dclp3_v{version}'
    CONTRACT_REPORT = ROOT/f'reports/dclp3_contract_summary_v{version}.json'
    PREPARATION_REPORT = ROOT/f'reports/dclp3_preparation_v{version}.json'


configure(2)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for part in iter(lambda: handle.read(8*1024*1024), b''):
            result.update(part)
    return result.hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def numeric(row, field, unknown=None):
    if unknown is not None and row.get(unknown) == '1':
        return None
    value = pd.to_numeric(row.get(field, ''), errors='coerce')
    return float(value) if np.isfinite(value) else None


def clinical_profiles(source, ids):
    screening = read(source/'DiabScreening_a.txt').set_index('PtID')
    exam = read(source/'DiabPhysExam_a.txt').set_index('PtID')
    visits = read(source/'VisitInfo_a.txt').set_index('ParentLoginVisitID')
    labs = read(source/'DiabLocalHbA1c_a.txt')
    profiles = {}
    for pid in ids:
        row, physical = screening.loc[pid], exam.loc[pid]
        if isinstance(row, pd.DataFrame) or isinstance(physical, pd.DataFrame):
            raise ValueError('Multiple screening rows require a new contract')
        screen_visit = visits.loc[row.ParentLoginVisitID]
        phys_visit = visits.loc[physical.ParentLoginVisitID]
        if screen_visit.PtID != pid or phys_visit.PtID != pid or screen_visit.Visit != 'Screening' or phys_visit.Visit != 'Screening':
            raise ValueError('Clinical visit linkage mismatch')
        screen_available = dates(pd.Series([screen_visit.VisitDt])).iloc[0] + pd.Timedelta(days=1)
        phys_available = dates(pd.Series([phys_visit.VisitDt])).iloc[0] + pd.Timedelta(days=1)
        if pd.isna(screen_available) or pd.isna(phys_available):
            raise ValueError('Missing screening date')
        weight = numeric(physical, 'Weight', 'WeightUnk')
        height = numeric(physical, 'Height', 'HeightUnk')
        if weight is not None:
            weight = weight if physical.WeightUnits == 'kg' else weight*.45359237 if physical.WeightUnits == 'lbs' else None
        if height is not None:
            height = height if physical.HeightUnits == 'cm' else height*2.54 if physical.HeightUnits == 'in' else None
        bmi = weight/(height/100)**2 if weight is not None and height is not None and weight > 0 and height > 0 else None
        items = {}
        def add(name, value, available):
            items[name] = {'value': value, 'available_at': available.isoformat() if available is not None else None}
        add('age', numeric(row, 'AgeAtEnrollment'), screen_available)
        add('sex_f', float(row.Gender == 'F') if row.Gender in ('M', 'F') else None, screen_available)
        add('diagnosis_age', numeric(row, 'DiagAge', 'DiagAgeUnk'), screen_available)
        add('diagnosis_age_approximate', float(row.DiagAgeApprox == '1'), screen_available)
        add('reported_daily_insulin', numeric(row, 'UnitsInsTotal', 'UnitsInsUnk'), screen_available)
        add('bmi', bmi, phys_available)
        add('systolic_bp', numeric(physical, 'BldPrSys', 'BldPrUnk'), phys_available)
        add('diastolic_bp', numeric(physical, 'BldPrDia', 'BldPrUnk'), phys_available)
        local = labs.loc[labs.PtID.eq(pid) & labs.Visit.eq('Screening')].copy()
        # Keep visit provenance as well as test date. Result arrival is the later
        # of screening/test day plus one day, explicitly an assumption.
        if len(local) != 1:
            raise ValueError('Expected a single screening HbA1c form')
        lab = local.iloc[0]
        lab_visit = visits.loc[lab.ParentLoginVisitID]
        if lab_visit.PtID != pid or lab_visit.Visit != 'Screening':
            raise ValueError('HbA1c visit linkage mismatch')
        test = dates(pd.Series([lab.HbA1cTestDt])).iloc[0]
        visit_date = dates(pd.Series([lab_visit.VisitDt])).iloc[0]
        available = max(test, visit_date)+pd.Timedelta(days=1) if pd.notna(test) and pd.notna(visit_date) else None
        add('hba1c', numeric(lab, 'HbA1cTestRes', 'HbA1cNotDone'), available)
        profiles[pid] = items
    return profiles


def freeze(protocol, source):
    roster = read(source/'PtRoster_a.txt')
    basal_ids = set(read(source/'Pump_BasalRateChange.txt', usecols=['PtID']).PtID)
    bolus_ids = set(read(source/'Pump_BolusDelivered.txt', usecols=['PtID']).PtID)
    pump_ids = basal_ids & bolus_ids
    roles = assign_roles(roster, pump_ids, protocol)
    first_roles = ROOT/'configs/dclp3_roles_v1.json'
    if protocol.get('issue_schedule_kind') == 'native_observation' and first_roles.exists():
        original = json.loads(first_roles.read_text())
        for key in ('development', 'reserved', 'folds', 'strata'):
            if roles[key] != original[key]:
                raise ValueError('V2 must retain the original patient roles')
    filenames = ('PtRoster_a.txt', 'DiabScreening_a.txt', 'DiabPhysExam_a.txt',
        'VisitInfo_a.txt', 'DiabLocalHbA1c_a.txt', 'cgm.txt', 'Pump_BasalRateChange.txt', 'Pump_BolusDelivered.txt')
    manifest = {'version': protocol['version'], 'protocol_sha256': digest(PROTOCOL),
        'source_sha256': {name: digest(source/name) for name in filenames}, **roles,
        'pump_participants': sorted(pump_ids & set(roles['development']+roles['reserved'])),
        'profiles': clinical_profiles(source, roles['development'])}
    if ROLES.exists() and json.loads(ROLES.read_text()) != manifest:
        raise ValueError('Existing frozen source, protocol or roles differ; refusing overwrite')
    write(ROLES, manifest)
    cohort = {role: dict(Counter(manifest['strata'][pid] for pid in manifest[role]))
              for role in ('development', 'reserved')}
    fold_sizes = [{'fold': f['fold'], 'fit': len(f['fit']), 'evaluation': len(f['evaluation']),
                   'evaluation_strata': dict(Counter(manifest['strata'][p] for p in f['evaluation']))}
                  for f in manifest['folds']]
    write(CONTRACT_REPORT, {'version': protocol['version'],
        'protocol_sha256': digest(PROTOCOL), 'manifest_sha256': digest(ROLES),
        'patients': protocol['participants'], 'development': len(roles['development']),
        'reserved': len(roles['reserved']), 'role_strata': cohort, 'folds': fold_sizes,
        'reserved_status': protocol['reserved_status'], 'models_fitted': 0})
    return manifest


def source_streams(source, manifest, protocol):
    ids = set(manifest['development'])
    cgms, basals, boluses = defaultdict(list), defaultdict(list), defaultdict(list)
    for chunk in read(source/'cgm.txt', chunksize=250_000):
        chunk = chunk.loc[chunk.PtID.isin(ids) & chunk.Period.eq(protocol['phase'])].copy()
        chunk['time'] = dates(chunk.DataDtTm, sas=True)
        chunk['value'] = pd.to_numeric(chunk.CGM, errors='raise')
        if chunk.time.isna().any():
            raise ValueError('Unparseable CGM timestamp')
        for pid, group in chunk.groupby('PtID', sort=False):
            cgms[pid].append(group[['time', 'value']])
    for filename, field, storage in [('Pump_BasalRateChange.txt', 'CommandedBasalRate', basals),
                                     ('Pump_BolusDelivered.txt', 'BolusAmount', boluses)]:
        for chunk in read(source/filename, chunksize=250_000):
            chunk = chunk.loc[chunk.PtID.isin(ids)].copy()
            if field == 'BolusAmount':
                # This removes only source-identical duplicated records. Distinct
                # simultaneous deliveries and reused RecIDs remain represented.
                # Cross-chunk duplicates are reconciled after concatenation.
                chunk['source_key'] = chunk.apply(lambda row: tuple(row.values), axis=1)
            supplied = chunk.DataDtTm_adjusted.ne('')
            chunk['time'] = dates(chunk.DataDtTm_adjusted.where(supplied, chunk.DataDtTm))
            chunk['amount' if field == 'BolusAmount' else 'value'] = pd.to_numeric(chunk[field], errors='raise')
            if chunk.time.isna().any():
                raise ValueError('Unparseable pump timestamp')
            cols = ['time', 'amount', 'BolusType', 'source_key'] if field == 'BolusAmount' else ['time', 'value']
            for pid, group in chunk.groupby('PtID', sort=False):
                storage[pid].append(group[cols])
    return cgms, basals, boluses


def prepare(protocol, manifest, source):
    started = time.perf_counter()
    cgms, basals, boluses = source_streams(source, manifest, protocol)
    if set(cgms) != set(manifest['development']):
        raise ValueError('Development CGM coverage differs from frozen roles')
    CACHE.mkdir(parents=True, exist_ok=True)
    columns, rows, hashes = None, [], {}
    empty = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    for i, pid in enumerate(manifest['development'], 1):
        frame = pd.concat(cgms.pop(pid), ignore_index=True)
        raw, quality = canonical_cgm(frame.time, frame.value, protocol)
        if not len(raw):
            raise ValueError('Empty post-randomization CGM stream')
        basal_conflicts = 0
        if pid in basals:
            rates = pd.concat(basals.pop(pid), ignore_index=True).groupby('time').value.agg(['first', 'nunique'])
            basal_conflicts = int(rates['nunique'].gt(1).sum())
            basal = rates['first'].where(rates['nunique'].eq(1))
            basal.loc[basal < 0] = np.nan
        else:
            basal = empty
        duplicate_bolus = 0
        if pid in boluses:
            doses = pd.concat(boluses.pop(pid), ignore_index=True)
            duplicate_bolus = int(doses.source_key.duplicated().sum())
            doses = doses.drop_duplicates('source_key')
            if not doses.BolusType.isin(['Standard', 'Extended']).all() or (doses.amount < 0).any():
                raise ValueError('Unexpected pump delivery semantics')
            bolus = doses.set_index('time')[['amount', 'BolusType']].rename(columns={'BolusType': 'kind'}).sort_index()
        else:
            bolus = pd.DataFrame(columns=['amount', 'kind'], index=pd.DatetimeIndex([]))
        issues = issue_times(raw, protocol)
        features = make_features(raw, issues, manifest['profiles'][pid], basal, bolus, protocol)
        selected = features.loc[features.history_eligible].drop(columns='history_eligible')
        if columns is not None and columns != selected.columns.tolist():
            raise ValueError('Feature columns changed across participants')
        columns = selected.columns.tolist()
        arrays = {'X': selected.to_numpy(dtype=np.float32), 'times': selected.index.asi8}
        targets = {}
        for horizon in protocol['horizons_minutes']:
            target = measured_targets(raw, selected.index, horizon, protocol)
            arrays.update({f'{key}{horizon}': value for key, value in target.items()})
            targets[str(horizon)] = {'point_rows': int(np.isfinite(target['y']).sum()),
                'strict_rows': int(target['strict'].sum()), 'boundary_rows': int(target['boundary'].sum()),
                'missing_or_conflicting_rows': int((~np.isfinite(target['y']) & ~target['boundary']).sum())}
        path = CACHE/(pid+'.npz')
        np.savez_compressed(path, **arrays)
        hashes[pid] = digest(path)
        rows.append({'participant_id': pid, 'stratum': manifest['strata'][pid],
            'has_pump_streams': pid in manifest['pump_participants'],
            'source_cgm': len(raw), 'potential_issues': len(issues), 'eligible_history': len(selected),
            'cgm_quality': quality, 'conflicting_basal_timestamps': basal_conflicts,
            'identical_bolus_source_duplicates': duplicate_bolus, 'targets': targets})
        print(f'Prepared DCLP3 development participant {i}/{len(manifest["development"])}', flush=True)
    stamp = {'version': protocol['version'], 'protocol_sha256': digest(PROTOCOL),
        'manifest_sha256': digest(ROLES), 'prepared_participants': manifest['development'],
        'features': columns, 'arms': feature_arms(columns), 'cache_sha256': hashes}
    write(CACHE/'manifest.json', stamp)
    write(CACHE/'counts_private.json', rows)
    aggregate = {'version': protocol['version'], 'protocol_sha256': digest(PROTOCOL),
        'manifest_sha256': digest(ROLES), 'development_patients': len(rows),
        'reserved_patients_prepared': 0, 'feature_count': len(columns),
        'arm_feature_counts': {name: len(indices) for name, indices in stamp['arms'].items()},
        'history_eligible': sum(r['eligible_history'] for r in rows),
        'potential_issue_times': sum(r['potential_issues'] for r in rows),
        'targets': {str(h): {key: sum(r['targets'][str(h)][key] for r in rows)
            for key in ('point_rows', 'strict_rows', 'boundary_rows', 'missing_or_conflicting_rows')}
            for h in protocol['horizons_minutes']},
        'pump_development_patients': sum(r['has_pump_streams'] for r in rows),
        'identical_bolus_source_duplicates': sum(r['identical_bolus_source_duplicates'] for r in rows),
        'conflicting_basal_timestamps': sum(r['conflicting_basal_timestamps'] for r in rows),
        'seconds': round(time.perf_counter()-started, 2), 'models_fitted': 0,
        'target_note': 'Observed point values within +/-30 seconds; strict-timestamp subset retained; boundary-coded outcomes counted separately.'}
    write(PREPARATION_REPORT, aggregate)
    print(json.dumps(aggregate, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-only', action='store_true')
    parser.add_argument('--version', type=int, choices=[1, 2], default=2)
    args = parser.parse_args()
    configure(args.version)
    protocol = json.loads(PROTOCOL.read_text())
    source = ROOT/'data/raw'/protocol['source_release']/'Data Files'
    manifest = freeze(protocol, source)
    if not args.freeze_only:
        prepare(protocol, manifest, source)
