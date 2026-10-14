"""Flow-neutral execution-flow mechanisms.

Product-specific orchestration lives under ``execution_flow.document_consistency_qc``.
"""

from execution_flow.processing_launch import (
    launch_document_processing_from_intake,
    launched_document_identity,
)

__all__ = [
    "launch_document_processing_from_intake",
    "launched_document_identity",
]
