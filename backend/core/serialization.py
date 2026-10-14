"""Deterministic JSON serialization helpers."""

from __future__ import annotations

import json
from typing import Any


def stable_json_dumps(payload: Any) -> str:
    """Deterministic JSON serialization for hash inputs."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
