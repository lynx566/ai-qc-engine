"""Tests for promoted Comparison Finding Verification formal prompts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification.prompts import (
    INPUT_PLACEHOLDER,
    PROMPT_DIR_SYSTEM_FILE,
    PROMPT_DIR_USER_FILE,
    formal_prompt_dir,
    load_formal_prompt_definition,
    render_formal_prompt_messages,
    resolve_formal_comparison_finding_verification_prompt_id,
    resolve_formal_prompt_directory_name,
    resolve_formal_prompt_id,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification.prompts import (
    formal_prompt as formal_prompt_module,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification.prompts.formal_prompt import (
    PROMPT_MANIFEST_FILENAME,
)

_FORMAL_PROMPT_IDS = (
    "comparison_finding_verification.scope_local",
    "comparison_finding_verification.focus_comparison",
    "comparison_finding_verification.ib_to_dsur",
    "comparison_finding_verification.dsur_to_ib",
)


@pytest.mark.parametrize("prompt_id", _FORMAL_PROMPT_IDS)
def test_manifest_loads_formal_prompt_definition(prompt_id: str) -> None:
    definition = load_formal_prompt_definition(prompt_id)  # type: ignore[arg-type]
    assert definition.prompt_id == prompt_id
    expected_version = {
        "comparison_finding_verification.scope_local": "0.2.2",
        "comparison_finding_verification.focus_comparison": "0.2.1",
        "comparison_finding_verification.ib_to_dsur": "0.2.1",
        "comparison_finding_verification.dsur_to_ib": "0.2.1",
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
def test_conclusion_requires_chinese_quotation_marks(prompt_id: str) -> None:
    definition = load_formal_prompt_definition(prompt_id)  # type: ignore[arg-type]
    generated_conclusion_requirements = [
        line
        for line in definition.system_text.splitlines()
        if line.startswith("- `conclusion`: Enter")
    ]
    assert len(generated_conclusion_requirements) == 2
    assert all(
        line.endswith(
            "When quotation marks are needed, use Chinese quotation marks `“…”`."
        )
        for line in generated_conclusion_requirements
    )
    assert (
        "When quotation marks are needed in `conclusion`"
        not in definition.system_text
    )


@pytest.mark.parametrize(
    ("comparison_mode_id", "prompt_id"),
    [
        ("scope_local", "comparison_finding_verification.scope_local"),
        ("focus_comparison", "comparison_finding_verification.focus_comparison"),
        ("ib_to_dsur", "comparison_finding_verification.ib_to_dsur"),
        ("dsur_to_ib", "comparison_finding_verification.dsur_to_ib"),
    ],
)
def test_comparison_mode_resolves_verification_prompt_id(
    comparison_mode_id: str,
    prompt_id: str,
) -> None:
    assert (
        resolve_formal_comparison_finding_verification_prompt_id(
            comparison_mode_id  # type: ignore[arg-type]
        )
        == prompt_id
    )
    assert resolve_formal_prompt_id(comparison_mode_id) == prompt_id  # type: ignore[arg-type]


def test_manifest_prompt_id_mismatch_fails_fast() -> None:
    with pytest.raises(ValueError, match="does not match requested formal prompt"):
        formal_prompt_module._validate_manifest(
            {"prompt_id": "focus_comparison", "version": "0.1.0"},
            requested_prompt_id="comparison_finding_verification.scope_local",
        )


def test_manifest_legacy_short_prompt_id_fails_fast(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "dsur_to_ib"
    prompt_dir.mkdir()
    (prompt_dir / PROMPT_MANIFEST_FILENAME).write_text(
        json.dumps({"prompt_id": "dsur_to_ib", "version": "0.1.0"}),
        encoding="utf-8",
    )
    (prompt_dir / PROMPT_DIR_SYSTEM_FILE).write_text("system", encoding="utf-8")
    (prompt_dir / PROMPT_DIR_USER_FILE).write_text("{{INPUT}}", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match requested formal prompt"):
        formal_prompt_module.load_formal_prompt_definition(
            "comparison_finding_verification.dsur_to_ib",
            prompt_dir=prompt_dir,
        )


def test_unknown_formal_prompt_id_fails_fast() -> None:
    with pytest.raises(ValueError, match="unknown formal prompt id"):
        resolve_formal_prompt_directory_name("comparison_finding_verification.unknown")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("prompt_id", "directory_name"),
    [
        ("comparison_finding_verification.scope_local", "scope_local"),
        ("comparison_finding_verification.focus_comparison", "focus_comparison"),
        ("comparison_finding_verification.ib_to_dsur", "ib_to_dsur"),
        ("comparison_finding_verification.dsur_to_ib", "dsur_to_ib"),
    ],
)
def test_formal_prompt_id_resolves_storage_directory(
    prompt_id: str,
    directory_name: str,
) -> None:
    assert resolve_formal_prompt_directory_name(prompt_id) == directory_name  # type: ignore[arg-type]
    assert formal_prompt_dir(prompt_id).name == directory_name  # type: ignore[arg-type]


def test_render_formal_prompt_messages_substitutes_verification_input() -> None:
    verification_input = "## Source Scope\nbody\n\n## Findings\nL001"
    messages = render_formal_prompt_messages(
        prompt_id="comparison_finding_verification.scope_local",
        verification_input_text=verification_input,
    )
    assert messages[0]["role"] == "system"
    assert INPUT_PLACEHOLDER not in messages[0]["content"]
    assert verification_input in messages[1]["content"]
