"""Exact Ridge arithmetic, grouped by input stream; not causal explanations."""
import numpy as np
import pandas as pd


def explain_ridge(artifact, inputs, persistence):
    model = artifact['model']
    if not hasattr(model, 'named_steps') or not {'imputer','scale','ridge'}<=set(model.named_steps):
        return None
    columns = artifact['features']
    values = np.asarray(inputs, dtype=np.float32 if artifact.get('sensor_delay_minutes')==5 else float).reshape(1,-1)
    imputer, scale, ridge = (model.named_steps[k] for k in ('imputer','scale','ridge'))
    filled = imputer.transform(pd.DataFrame(values,columns=columns) if hasattr(imputer,'feature_names_in_') else values)
    normalized = scale.transform(filled)
    names = imputer.get_feature_names_out(columns)
    contributions = normalized[0]*ridge.coef_
    groups = dict(glucose=0.,clinical=0.,heart_rate=0.,missingness=0.)
    for name, value in zip(names, contributions):
        group = 'missingness' if name.startswith('missingindicator_') else 'glucose' if name.startswith('cgm_') else 'heart_rate' if name.startswith('hr_') else 'clinical'
        groups[group] += float(value)
    reference = float(ridge.intercept_)
    prediction = reference+float(np.sum(contributions))
    return dict(reference=reference, persistence=float(persistence),
                reference_offset=reference-float(persistence), groups=groups,
                reconstructed_prediction=prediction,
                imputed=[name for name,value in zip(columns,values[0]) if not np.isfinite(value)],
                note='Exact arithmetic in the fitted Ridge model. Contributions depend on scaling and correlated inputs; they do not establish physiological or treatment effects.')
