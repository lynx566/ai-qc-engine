from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.privacy.profile import (
    CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
)
from privacy.date_shift import DateShiftConfig, DateShifter
from runtime.date_shift_offset import resolve_effective_date_shift_offset_days
from tests.clinical_program_fixtures import canonical_clinical_program_fields


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("版本日期：2024.03.15", "版本日期：2024.04.01"),
        ("报告日期：2024/03/15", "报告日期：2024/04/01"),
        ("签署日期：2024-03-15", "签署日期：2024-04-01"),
        ("数据截至2023年11月30日", "数据截至2023年12月17日"),
    ],
)
def test_date_shifter_preserves_input_format(text: str, expected: str) -> None:
    shifter = DateShifter(DateShiftConfig(offset_days=17))
    assert shifter.shift_text(text) == expected


def test_date_shifter_skips_invalid_dot_date() -> None:
    shifter = DateShifter(DateShiftConfig(offset_days=17))
    text = "版本日期：2024.13.45"
    assert shifter.shift_text(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "版本号：1.3",
        "Version 2.0",
        "方案版本：V1.2",
        "表 1.3",
        "章节 12.1.3",
    ],
)
def test_date_shifter_does_not_shift_version_like_tokens(text: str) -> None:
    shifter = DateShifter(DateShiftConfig(offset_days=17))
    assert shifter.shift_text(text) == text


def test_date_shifter_shifts_cover_block_with_version_date() -> None:
    shifter = DateShifter(DateShiftConfig(offset_days=17))
    text = (
        "通用名称：GenericName_001 代号：StudyDrug_001 版本号：1.3 "
        "版本日期：2024.03.15 适用范围：Protocol_001 申办者：Sponsor_001"
    )
    shifted = shifter.shift_text(text)
    assert "版本号：1.3" in shifted
    assert "版本日期：2024.04.01" in shifted
    assert "2024.03.15" not in shifted


def test_shift_iso_date_value_shifts_single_and_range_values() -> None:
    from privacy.date_shift import shift_iso_date_value

    assert shift_iso_date_value("2021-12-16", 17) == "2022-01-02"
    assert shift_iso_date_value("2021-12-16/2023-03-20", 17) == "2022-01-02/2023-04-06"


def test_shift_iso_date_value_shifts_open_ended_interval_values() -> None:
    from privacy.date_shift import shift_iso_date_value

    assert shift_iso_date_value("2023-04-18/", 17) == "2023-05-05/"
    assert shift_iso_date_value("/2023-11-30", 17) == "/2023-12-17"


def test_shift_iso_date_value_preserves_masked_tokens_and_unparseable_values() -> None:
    from privacy.date_shift import shift_iso_date_value

    assert shift_iso_date_value("Date_001", 17) == "Date_001"
    assert shift_iso_date_value("not-a-date", 17) == "not-a-date"
    assert shift_iso_date_value(None, 17) is None
    assert shift_iso_date_value("2021-12-16", 0) == "2021-12-16"


def test_resolve_effective_offset_uses_profile() -> None:
    profile = replace(
        CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        date_shift_offset_days=3,
    )
    assert resolve_effective_date_shift_offset_days(profile=profile) == 3


def test_program_registry_has_no_date_shift_offset_accessor() -> None:
    import plugins.clinical_trial_doc.privacy.registry.loader as loader_module

    assert not hasattr(loader_module, "clinical_program_date_shift_offset_days")


def test_prepare_analysis_runner_parse_args_no_clinical_program_ok_without_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--clinical-program is no longer argparse required=True; omitting it is valid
    when the registry detector is not in use."""
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        '{"doc_id":"d","document_meta":{"language":"zh"}}', encoding="utf-8"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_analysis_runner.py",
            "--bundle",
            str(bundle),
            "--language",
            "zh",
        ],
    )
    from scripts.stage_runners import prepare_analysis_runner

    args = prepare_analysis_runner.parse_args()
    assert args.clinical_program is None


def test_prepare_analysis_standalone_requires_clinical_program_for_registry(
    tmp_path: Path,
) -> None:
    """Registry masking requires explicit Program selection in privacy config."""
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        '{"doc_id":"d","document_meta":{"language":"zh"}}', encoding="utf-8"
    )
    from plugins.clinical_trial_doc.prepare_analysis import (
        build_clinical_prepare_analysis_standalone_invocation,
    )

    with pytest.raises(RuntimeError, match="clinical_program_id must be set"):
        build_clinical_prepare_analysis_standalone_invocation(
            clinical_program_id=None,
            bundle_path=bundle,
            privacy_after_extract_detectors="registry",
        )


def test_prepare_analysis_shifts_cover_version_date_dot_format() -> None:
    from clinical_program_fixtures import (
        prepare_analysis_bundle_for_test as prepare_analysis_bundle,
    )
    from privacy.config import PrivacyConfig

    text = (
        "通用名称：GenericName_001 代号：StudyDrug_001 版本号：1.3 "
        "版本日期：2024.03.15 适用范围：Protocol_001 申办者：Sponsor_001"
    )
    bundle = {
        "doc_id": "doc_cover",
        "file_name": "ib.docx",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": "C0001",
                "kind": "paragraph",
                "normalized_text": text,
            }
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }
    result = prepare_analysis_bundle(
        bundle,
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
        language="zh",
        privacy_config=PrivacyConfig.from_dict(
            {
                "transforms": {
                    "after_extract": {"detectors": ["registry", "regex"]},
                    "after_filter": {"detectors": []},
                }
            }
        ),
        date_shift_offset_days=17,
        **canonical_clinical_program_fields(),
    )
    analysis_text = result.analysis_bundle["content_blocks"][0]["analysis_text"]
    assert "版本号：1.3" in analysis_text
    assert "版本日期：2024.04.01" in analysis_text
    assert "2024.03.15" not in analysis_text
