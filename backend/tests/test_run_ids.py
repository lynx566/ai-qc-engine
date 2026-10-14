from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from runtime.run_ids import format_run_timestamp, utc_run_stamp


def test_utc_run_stamp_is_timezone_aware() -> None:
    stamp = utc_run_stamp()
    assert stamp.tzinfo is not None
    assert stamp.utcoffset().total_seconds() == 0


def test_format_run_timestamp_utc_with_z_suffix() -> None:
    stamp = datetime(2026, 6, 30, 13, 43, 12, 184512, tzinfo=timezone.utc)
    assert format_run_timestamp(stamp) == "20260630_134312_184512Z"


def test_format_run_timestamp_rejects_naive() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        format_run_timestamp(datetime(2026, 6, 30, 13, 43, 12))
