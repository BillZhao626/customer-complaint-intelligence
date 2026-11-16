"""Resolve reviewed, committed example inputs without a private workspace.

Original research deployments keep their existing paths. The public checkout
falls back to explicit synthetic example files, never to another local project.
"""
from pathlib import Path

_FILES = {
    'data/synthetic/customer_emails_full_v1.csv': 'historical80/emails.csv',
    'data/golden/golden_labels_review_sample_v1_reviewed.csv': 'historical80/reference.csv',
    'outputs/i4e2_reviewed_80_predictions_v1.csv': 'historical80/normalized-predictions.csv',
    'outputs/i4e2_reviewed_80_raw_predictions_v1.csv': 'historical80/raw-predictions.csv',
    '.local/p35/calibration-decision-v1.1/snapshot.json': 'calibration24.json',
    '.local/p5b7/dataset': 'emails',
    '.local/p5b8/analysis': 'analyses',
}


def research_path(root, relative):
    root = Path(root)
    legacy = root / relative
    if legacy.exists():
        return legacy
    for prefix, target in _FILES.items():
        if relative == prefix or relative.startswith(prefix + '/'):
            return root / 'examples/research' / target / relative[len(prefix):].lstrip('/')
    return legacy
