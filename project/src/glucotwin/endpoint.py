"""Fail-closed probability access for the experimental endpoint artifact."""
import numpy as np

def calibration_score(features, artifact):
    """Reproduce the score representation used when fitting the calibrator."""
    kind=artifact.get('calibration_input','decision_function')
    if kind=='decision_function':
        return artifact['model'].decision_function(features).reshape(-1,1)
    if kind=='clipped_log_odds':
        clip=artifact.get('probability_clip',1e-6)
        p=np.clip(artifact['model'].predict_proba(features)[:,1],clip,1-clip)
        return np.log(p/(1-p)).reshape(-1,1)
    raise ValueError('Unsupported calibration input')

def endpoint_probability(features, artifact):
    if not artifact.get('probability_display_approved', False):
        raise RuntimeError('Probability display disabled: development calibration checks did not pass')
    columns=artifact['features']
    missing=set(columns)-set(features.columns)
    if missing:
        raise ValueError('Missing required endpoint features: '+', '.join(sorted(missing)))
    score=calibration_score(features[columns],artifact)
    return artifact['calibrator'].predict_proba(score)[:,1]
