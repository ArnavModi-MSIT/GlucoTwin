"""Verify frozen cache roles, support accounting and real-source timing probes."""
from collections import defaultdict
import json

import numpy as np
import pandas as pd

from prepare_dclp3 import ROOT, CACHE, PROTOCOL, ROLES, PREPARATION_REPORT, digest, write
from audit_dclp3 import read, dates
from glucotwin.dclp3 import canonical_cgm, make_features


def main():
    protocol = json.loads(PROTOCOL.read_text())
    roles = json.loads(ROLES.read_text())
    stamp = json.loads((CACHE/'manifest.json').read_text())
    aggregate = json.loads(PREPARATION_REPORT.read_text())
    assert roles['protocol_sha256'] == stamp['protocol_sha256'] == digest(PROTOCOL)
    assert stamp['manifest_sha256'] == digest(ROLES)
    assert sorted(stamp['prepared_participants']) == roles['development']
    assert {p.stem for p in CACHE.glob('*.npz')} == set(roles['development'])
    assert not set(roles['reserved']) & set(stamp['prepared_participants'])
    source = ROOT/'data/raw'/protocol['source_release']/'Data Files'
    for name, sha in roles['source_sha256'].items():
        assert digest(source/name) == sha, 'Frozen source changed'
    evaluation = []
    for fold in roles['folds']:
        assert not set(fold['fit']) & set(fold['evaluation'])
        assert set(fold['fit']+fold['evaluation']) == set(roles['development'])
        evaluation.extend(fold['evaluation'])
    assert sorted(evaluation) == roles['development']
    names = stamp['features']
    counts = {str(h): defaultdict(int) for h in protocol['horizons_minutes']}
    ages, offset_parts = [], defaultdict(list)
    history_rows = 0
    for pid in roles['development']:
        assert digest(CACHE/(pid+'.npz')) == stamp['cache_sha256'][pid]
        with np.load(CACHE/(pid+'.npz'), allow_pickle=False) as cache:
            x, times = cache['X'], cache['times']
            assert x.dtype == np.float32 and x.shape == (len(times), len(names))
            assert not np.isinf(x).any() and np.all(np.diff(times) > 0)
            history_rows += len(times)
            age = x[:, names.index('cgm_age_minutes')]
            assert np.isfinite(age).all() and (age >= protocol['availability_delay_minutes']['cgm']).all()
            assert (age*60 <= protocol['maximum_current_age_seconds']+.001).all()
            ages.append(age)
            assert (x[:, names.index('cgm_count_60m')] >= protocol['minimum_past_hour_samples']).all()
            assert (x[:, names.index('cgm_max_gap_60m')] <= protocol['maximum_past_hour_gap_seconds']).all()
            for col, cap in [('insulin_basal_recency_capped', protocol['basal_state_freshness_minutes']),
                             ('insulin_bolus_recency_capped', protocol['bolus_recency_cap_minutes'])]:
                values = x[:, names.index(col)]
                assert ((~np.isfinite(values)) | ((values >= 0) & (values <= cap))).all()
            for col, item in roles['profiles'][pid].items():
                values = x[:, names.index('profile_'+col)]
                available = item['available_at']
                if available is None or item['value'] is None:
                    assert np.isnan(values).all()
                else:
                    known = times >= pd.Timestamp(available).value
                    assert np.isnan(values[~known]).all()
                    np.testing.assert_allclose(values[known], item['value'], rtol=1e-6)
            for h in protocol['horizons_minutes']:
                y, offset, target = cache[f'y{h}'], cache[f'offset_seconds{h}'], cache[f'matched_time_ns{h}']
                boundary, strict = cache[f'boundary{h}'], cache[f'strict{h}']
                usable = np.isfinite(y)
                assert y.shape == offset.shape == target.shape == boundary.shape == strict.shape == times.shape
                assert (y[usable] >= 40).all() and (y[usable] <= 400).all()
                assert not (usable & boundary).any()
                np.testing.assert_array_equal(strict, usable & (offset == 0))
                matched = np.isfinite(offset)
                assert (np.abs(offset[matched]) <= protocol['target_tolerance_seconds']).all()
                np.testing.assert_allclose((target[matched]-times[matched]-h*60*1e9)/1e9, offset[matched])
                counts[str(h)]['point_rows'] += int(usable.sum())
                counts[str(h)]['strict_rows'] += int(strict.sum())
                counts[str(h)]['boundary_rows'] += int(boundary.sum())
                counts[str(h)]['missing_or_conflicting_rows'] += int((~usable & ~boundary).sum())
                offset_parts[str(h)].append(offset[usable])
    assert history_rows == aggregate['history_eligible']
    for h, count in counts.items():
        assert dict(count) == aggregate['targets'][h]

    # One source probe patient from each treatment/pump stratum. Only development
    # rows are converted; this never constructs a reserved-patient matrix.
    chosen = {}
    for pid in roles['development']:
        chosen.setdefault(roles['strata'][pid], pid)
    ids = set(chosen.values())
    glucose_parts, basal_parts, bolus_parts = defaultdict(list), defaultdict(list), defaultdict(list)
    for chunk in read(source/'cgm.txt', chunksize=250_000):
        chunk = chunk.loc[chunk.PtID.isin(ids) & chunk.Period.eq(protocol['phase'])].copy()
        chunk['time'] = dates(chunk.DataDtTm, sas=True)
        chunk['value'] = pd.to_numeric(chunk.CGM, errors='raise')
        for pid, group in chunk.groupby('PtID'):
            glucose_parts[pid].append(group[['time', 'value']])
    for filename, field, storage in [('Pump_BasalRateChange.txt', 'CommandedBasalRate', basal_parts),
                                     ('Pump_BolusDelivered.txt', 'BolusAmount', bolus_parts)]:
        for chunk in read(source/filename, chunksize=250_000):
            chunk = chunk.loc[chunk.PtID.isin(ids)].copy()
            if field == 'BolusAmount':
                chunk['source_key'] = chunk.apply(lambda row: tuple(row.values), axis=1)
            chunk = chunk.drop_duplicates()
            chunk['time'] = dates(chunk.DataDtTm_adjusted.where(chunk.DataDtTm_adjusted.ne(''), chunk.DataDtTm))
            chunk['value'] = pd.to_numeric(chunk[field], errors='raise')
            for pid, group in chunk.groupby('PtID'):
                storage[pid].append(group[['time', 'value']+(['BolusType', 'source_key'] if field == 'BolusAmount' else [])])
    feature_probes = target_probes = 0
    empty = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    for pid in sorted(ids):
        raw_data = pd.concat(glucose_parts[pid])
        raw, _ = canonical_cgm(raw_data.time, raw_data.value, protocol)
        if pid in basal_parts:
            rates = pd.concat(basal_parts[pid]).groupby('time').value.agg(['first', 'nunique'])
            basal = rates['first'].where(rates['nunique'].eq(1))
        else:
            basal = empty
        if pid in bolus_parts:
            bolus = pd.concat(bolus_parts[pid]).drop_duplicates('source_key').set_index('time').rename(columns={'value': 'amount', 'BolusType': 'kind'})[['amount', 'kind']].sort_index()
        else:
            bolus = pd.DataFrame(columns=['amount', 'kind'], index=pd.DatetimeIndex([]))
        with np.load(CACHE/(pid+'.npz'), allow_pickle=False) as cache:
            positions = np.linspace(0, len(cache['times'])-1, 12, dtype=int)
            for pos in positions:
                issue = pd.Timestamp(cache['times'][pos])
                cgm_cut = issue-pd.Timedelta(minutes=protocol['availability_delay_minutes']['cgm'])
                pump_cut = issue-pd.Timedelta(minutes=protocol['availability_delay_minutes']['pump'])
                prefix = make_features(raw.loc[:cgm_cut], pd.DatetimeIndex([issue]), roles['profiles'][pid],
                                       basal.loc[:pump_cut], bolus.loc[:pump_cut], protocol)
                assert prefix.history_eligible.iloc[0]
                np.testing.assert_allclose(prefix.drop(columns='history_eligible').to_numpy(dtype=np.float32)[0],
                                           cache['X'][pos], rtol=1e-6, atol=1e-4, equal_nan=True)
                feature_probes += 1
                for h in protocol['horizons_minutes']:
                    desired = issue+pd.Timedelta(minutes=h)
                    offsets = (raw.index-desired).total_seconds().to_numpy()
                    closest = int(np.argmin(np.abs(offsets)))
                    val = raw.iloc[closest]
                    matched = abs(offsets[closest]) <= protocol['target_tolerance_seconds']
                    expected = val if matched and np.isfinite(val) and 40 <= val <= 400 else np.nan
                    np.testing.assert_allclose(cache[f'y{h}'][pos], expected, equal_nan=True)
                    target_probes += 1
    def quantiles(parts):
        values = np.concatenate(parts)
        return dict(zip(['min', 'p25', 'median', 'p75', 'max'], map(float, np.quantile(values, [0, .25, .5, .75, 1]))))
    report = {'version': protocol['version'], 'status': 'passed',
        'development_cache_files_verified': len(roles['development']), 'reserved_cache_files': 0,
        'source_hashes_verified': len(roles['source_sha256']), 'causal_real_prefix_probes': feature_probes,
        'brute_force_measured_target_probes': target_probes, 'history_rows_verified': history_rows,
        'current_reading_age_minutes': quantiles(ages),
        'point_target_offset_seconds': {h: quantiles(parts) for h, parts in offset_parts.items()},
        'models_fitted': 0, 'contract_sha256': digest(PROTOCOL)}
    write(ROOT/'reports/dclp3_preparation_checks_v2.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
