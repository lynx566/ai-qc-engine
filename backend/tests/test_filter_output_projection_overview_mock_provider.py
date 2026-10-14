"""Tests for overview standalone mock provider used by FOP dev runner."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.stage_runners.filter_output_projection_overview_mock_provider import (
    OverviewStandaloneMockProvider,
)


def test_overview_standalone_mock_provider_builds_valid_response_from_prompt_aliases() -> None:
    provider = OverviewStandaloneMockProvider()
    payload = [
        {
            "source_items": [
                {"source_id": "O001"},
                {"source_id": "O002"},
            ]
        }
    ]
    messages = [
        {
            "role": "user",
            "content": "## Overview source\n\n"
            + json.dumps(payload, ensure_ascii=False),
        }
    ]

    result = provider.generate(messages)

    parsed = json.loads(result.raw_text)
    assert parsed == {
        "sentence_assessments": [
            {"source_id": "O001", "content_modules": ["clinical_safety"]},
            {"source_id": "O002", "content_modules": ["clinical_safety"]},
        ]
    }
    assert result.provider_name == "mock"
    assert result.model == "overview-standalone-mock"
