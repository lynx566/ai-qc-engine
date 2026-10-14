"""Tests for promoted Comparison Finding Assessment formal prompts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.prompts as prompts_package
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.prompts import (
    INPUT_PLACEHOLDER,
    PROMPT_DIR_SYSTEM_FILE,
    PROMPT_DIR_USER_FILE,
    formal_prompt_dir,
    load_formal_prompt_definition,
    render_formal_prompt_messages,
    resolve_formal_prompt_directory_name,
    resolve_formal_prompt_id,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.prompts import (
    formal_prompt as formal_prompt_module,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.prompts.formal_prompt import (
    PROMPT_MANIFEST_FILENAME,
)

_FORMAL_PROMPT_IDS = (
    "comparison_finding_assessment.scope_local",
    "comparison_finding_assessment.focus_comparison",
    "comparison_finding_assessment.ib_to_dsur",
    "comparison_finding_assessment.dsur_to_ib",
)


@pytest.mark.parametrize("prompt_id", _FORMAL_PROMPT_IDS)
def test_manifest_loads_formal_prompt_definition(prompt_id: str) -> None:
    definition = load_formal_prompt_definition(prompt_id)  # type: ignore[arg-type]
    assert definition.prompt_id == prompt_id
    expected_version = {
        "comparison_finding_assessment.scope_local": "0.3.3",
        "comparison_finding_assessment.focus_comparison": "0.3.2",
        "comparison_finding_assessment.ib_to_dsur": "0.3.2",
        "comparison_finding_assessment.dsur_to_ib": "0.3.2",
    }[prompt_id]
    assert definition.version == expected_version
    prompt_dir = formal_prompt_dir(prompt_id)  # type: ignore[arg-type]
    assert definition.system_text == (
        prompt_dir / PROMPT_DIR_SYSTEM_FILE
    ).read_bytes().decode("utf-8")
    assert definition.user_text == (
        prompt_dir / PROMPT_DIR_USER_FILE
    ).read_bytes().decode("utf-8")


@pytest.mark.parametrize("prompt_id", _FORMAL_PROMPT_IDS)
def test_candidate_focus_requires_chinese_quotation_marks(prompt_id: str) -> None:
    definition = load_formal_prompt_definition(prompt_id)  # type: ignore[arg-type]
    candidate_focus_requirements = [
        line
        for line in definition.system_text.splitlines()
        if line.startswith("- `candidate_focus`:")
    ]
    assert len(candidate_focus_requirements) == 1
    assert candidate_focus_requirements[0].endswith(
        "When quotation marks are needed, use Chinese quotation marks `“…”`."
    )
    assert (
        "When quotation marks are needed in `candidate_focus`"
        not in definition.system_text
    )


def test_manifest_prompt_id_mismatch_fails_fast() -> None:
    with pytest.raises(ValueError, match="does not match requested formal prompt"):
        formal_prompt_module._validate_manifest(
            {"prompt_id": "focus_comparison", "version": "0.1.0"},
            requested_prompt_id="comparison_finding_assessment.scope_local",
        )


def test_manifest_legacy_short_prompt_id_fails_fast(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "dsur_to_ib"
    prompt_dir.mkdir()
    (prompt_dir / PROMPT_MANIFEST_FILENAME).write_text(
        json.dumps({"prompt_id": "dsur_to_ib", "version": "0.2.0"}),
        encoding="utf-8",
    )
    (prompt_dir / PROMPT_DIR_SYSTEM_FILE).write_text("system", encoding="utf-8")
    (prompt_dir / PROMPT_DIR_USER_FILE).write_text("{{INPUT}}", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match requested formal prompt"):
        formal_prompt_module.load_formal_prompt_definition(
            "comparison_finding_assessment.dsur_to_ib",
            prompt_dir=prompt_dir,
        )


def test_unknown_formal_prompt_id_fails_fast() -> None:
    with pytest.raises(ValueError, match="unknown formal prompt id"):
        resolve_formal_prompt_directory_name("comparison_finding_assessment.unknown")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("prompt_id", "directory_name"),
    [
        ("comparison_finding_assessment.scope_local", "scope_local"),
        ("comparison_finding_assessment.focus_comparison", "focus_comparison"),
        ("comparison_finding_assessment.ib_to_dsur", "ib_to_dsur"),
        ("comparison_finding_assessment.dsur_to_ib", "dsur_to_ib"),
    ],
)
def test_formal_prompt_id_resolves_storage_directory(
    prompt_id: str,
    directory_name: str,
) -> None:
    assert resolve_formal_prompt_directory_name(prompt_id) == directory_name  # type: ignore[arg-type]
    assert formal_prompt_dir(prompt_id).name == directory_name  # type: ignore[arg-type]


def test_independent_manifest_versions_can_differ(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for prompt_id, directory_name, version in (
        ("comparison_finding_assessment.scope_local", "scope_local", "0.2.1"),
        ("comparison_finding_assessment.focus_comparison", "focus_comparison", "0.2.1"),
        ("comparison_finding_assessment.ib_to_dsur", "ib_to_dsur", "0.1.1"),
        ("comparison_finding_assessment.dsur_to_ib", "dsur_to_ib", "0.2.1"),
    ):
        source_dir = formal_prompt_dir(prompt_id)  # type: ignore[arg-type]
        target_dir = tmp_path / directory_name
        target_dir.mkdir()
        for filename in (
            PROMPT_DIR_SYSTEM_FILE,
            PROMPT_DIR_USER_FILE,
            PROMPT_MANIFEST_FILENAME,
        ):
            (target_dir / filename).write_bytes((source_dir / filename).read_bytes())
        manifest = json.loads((target_dir / PROMPT_MANIFEST_FILENAME).read_text())
        manifest["version"] = version
        (target_dir / PROMPT_MANIFEST_FILENAME).write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

    monkeypatch.setattr(prompts_package, "_PROMPTS_ROOT", tmp_path)
    assert (
        load_formal_prompt_definition(
            "comparison_finding_assessment.scope_local"
        ).version
        == "0.2.1"
    )
    assert (
        load_formal_prompt_definition(
            "comparison_finding_assessment.focus_comparison"
        ).version
        == "0.2.1"
    )
    assert (
        load_formal_prompt_definition(
            "comparison_finding_assessment.ib_to_dsur"
        ).version
        == "0.1.1"
    )
    assert (
        load_formal_prompt_definition(
            "comparison_finding_assessment.dsur_to_ib"
        ).version
        == "0.2.1"
    )


def test_rendered_messages_unchanged_after_manifest_introduction() -> None:
    evidence_input = "## Scope\n\nexample evidence body"
    for prompt_id in _FORMAL_PROMPT_IDS:
        definition = load_formal_prompt_definition(prompt_id)  # type: ignore[arg-type]
        expected_user = definition.user_text.replace(
            INPUT_PLACEHOLDER, evidence_input, 1
        )
        messages = render_formal_prompt_messages(
            prompt_id=prompt_id,  # type: ignore[arg-type]
            evidence_input=evidence_input,
        )
        assert messages == [
            {"role": "system", "content": definition.system_text},
            {"role": "user", "content": expected_user},
        ]


@pytest.mark.parametrize(
    ("comparison_mode_id", "expected_prompt_id"),
    [
        ("scope_local", "comparison_finding_assessment.scope_local"),
        ("focus_comparison", "comparison_finding_assessment.focus_comparison"),
        ("ib_to_dsur", "comparison_finding_assessment.ib_to_dsur"),
        ("dsur_to_ib", "comparison_finding_assessment.dsur_to_ib"),
    ],
)
def test_comparison_mode_maps_to_formal_prompt_id(
    comparison_mode_id: str,
    expected_prompt_id: str,
) -> None:
    assert resolve_formal_prompt_id(comparison_mode_id) == expected_prompt_id  # type: ignore[arg-type]


def test_unknown_comparison_mode_fails_fast() -> None:
    with pytest.raises(ValueError, match="unknown comparison_mode_id"):
        resolve_formal_prompt_id("unknown_view")  # type: ignore[arg-type]
