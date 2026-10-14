"""Naming contract for the shared Document Consistency QC HTTP bridge."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from bridge.document_consistency_qc import bridge_runtime, errors


def test_shared_bridge_runtime_uses_domain_neutral_symbols() -> None:
    assert hasattr(bridge_runtime, "DocumentConsistencyQcBridgeConfig")

    assert hasattr(errors, "DocumentConsistencyQcBridgeError")
    assert hasattr(errors, "DocumentConsistencyQcBridgeValidationError")
    assert hasattr(errors, "DocumentConsistencyQcBridgeRuntimeError")
