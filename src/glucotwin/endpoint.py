"""Fail-closed probability access for the experimental endpoint artifact."""

def endpoint_probability(features, artifact):
    if not artifact.get('probability_display_approved', False):
        raise RuntimeError('Probability display disabled: development calibration checks did not pass')
    columns=artifact['features']
    missing=set(columns)-set(features.columns)
    if missing:
        raise ValueError('Missing required endpoint features: '+', '.join(sorted(missing)))
    score=artifact['model'].decision_function(features[columns]).reshape(-1,1)
    return artifact['calibrator'].predict_proba(score)[:,1]
