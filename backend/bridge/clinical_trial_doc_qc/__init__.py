"""HTTP composition root for the Clinical Trial Document QC Product."""

from bridge.clinical_trial_doc_qc.app import app, create_app

__all__ = [
    "app",
    "create_app",
]
