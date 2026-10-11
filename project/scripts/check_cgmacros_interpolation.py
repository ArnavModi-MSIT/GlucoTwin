"""Diagnose interpolation knots; do not claim these recover every raw sample."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
results = []
for path in sorted((ROOT/'data/raw/cgmacros/CGMacros').glob('CGMacros-*/CGMacros-*.csv')):
    frame = pd.read_csv(path)
    times = pd.to_datetime(frame.Timestamp).to_numpy(dtype='datetime64[ns]').astype('int64')/60e9
    for sensor, cadence in [('Dexcom GL',5),('Libre GL',15)]:
        values = pd.to_numeric(frame[sensor],errors='coerce').to_numpy()
        good = np.isfinite(values)
        # Only interior triples with actual consecutive CSV minutes.
        interior = good[:-2]&good[1:-1]&good[2:]&(np.diff(times)[:-1]==1)&(np.diff(times)[1:]==1)
        curved = interior & (np.abs(values[2:]-2*values[1:-1]+values[:-2])>1e-6)
        indices = np.flatnonzero(curved)+1
        phases = np.mod(times[indices].astype(np.int64),cadence)
        counts = np.bincount(phases,minlength=cadence)
        phase = int(np.argmax(counts))
        grid = good & (np.mod(times.astype(np.int64),cadence)==phase)
        # Rebuild only intervals between inferred lattice anchors, with no extrapolation.
        anchors = np.flatnonzero(grid)
        if len(anchors)>1:
            rebuilt = np.interp(times,times[anchors],values[anchors])
            valid = good & (times>=times[anchors[0]]) & (times<=times[anchors[-1]])
            errors = np.abs(rebuilt[valid]-values[valid])
            mismatch = int((errors>1e-5).sum())
            max_error = float(errors.max())
        else: mismatch,max_error = None,None
        results.append({'patient_id':int(path.stem.split('-')[-1]),'sensor':sensor,'cadence_minutes':cadence,
                        'slope_changes':len(indices),'modal_phase':phase,'changes_on_modal_phase_fraction':float(counts[phase]/len(indices)) if len(indices) else None,
                        'noninteger_slope_change_values':int((np.abs(values[indices]-np.round(values[indices]))>1e-5).sum()),
                        'lattice_anchors':len(anchors),'noninteger_lattice_values':int((np.abs(values[anchors]-np.round(values[anchors]))>1e-5).sum()),
                        'lattice_rebuild_mismatched_rows':mismatch,'lattice_rebuild_max_error':max_error})
pd.DataFrame(results).to_csv(ROOT/'reports/cgmacros_interpolation_diagnostics.csv',index=False)
for sensor in ['Dexcom GL','Libre GL']:
    sub = [r for r in results if r['sensor']==sensor]
    print(json.dumps({'sensor':sensor,'patients':len(sub),'phase_counts':pd.Series([r['modal_phase'] for r in sub]).value_counts().to_dict(),
                      'min_phase_agreement':min(r['changes_on_modal_phase_fraction'] for r in sub if r['changes_on_modal_phase_fraction'] is not None),
                      'noninteger_knots':sum(r['noninteger_slope_change_values'] for r in sub),
                      'noninteger_anchors':sum(r['noninteger_lattice_values'] for r in sub),
                      'patients_with_rebuild_mismatch':sum(r['lattice_rebuild_mismatched_rows']>0 for r in sub),
                      'worst_rebuild_error':max(r['lattice_rebuild_max_error'] for r in sub)}))
