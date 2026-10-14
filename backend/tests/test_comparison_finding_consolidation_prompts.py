"""Tests for promoted Comparison Finding Consolidation prompts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.prompts import (
    INPUT_PLACEHOLDER,
    PROMPT_DIR_SYSTEM_FILE,
    PROMPT_DIR_USER_FILE,
    formal_prompt_dir,
    load_formal_prompt_definition,
    render_formal_prompt_messages,
    resolve_formal_prompt_directory_name,
    resolve_formal_prompt_id,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation import prompts as prompts_module
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.alias_qc import (
    compute_comparison_finding_consolidation_alias_qc,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.execution import (
    execute_comparison_finding_consolidation,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.input_materialization import (
    materialize_comparison_finding_consolidation_input,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.response_validation import (
    validate_comparison_finding_consolidation_response_structure,
)

PROMPT_ID = "comparison_finding_consolidation.focus_comparison"


def test_focus_comparison_resolves_formal_consolidation_prompt() -> None:
    assert resolve_formal_prompt_id("focus_comparison") == PROMPT_ID
    assert resolve_formal_prompt_directory_name(PROMPT_ID) == "focus_comparison"
    assert formal_prompt_dir(PROMPT_ID).name == "focus_comparison"


def test_focus_comparison_formal_prompt_loads_manifest_and_on_disk_templates() -> None:
    prompt_dir = formal_prompt_dir(PROMPT_ID)
    manifest = json.loads(
        (prompt_dir / "manifest.json").read_text(encoding="utf-8")
    )
    definition = load_formal_prompt_definition(PROMPT_ID)

    assert manifest == {"prompt_id": PROMPT_ID, "version": "0.1.0"}
    assert definition.prompt_id == PROMPT_ID
    assert definition.version == manifest["version"]
    assert definition.system_text == (
        prompt_dir / PROMPT_DIR_SYSTEM_FILE
    ).read_text(encoding="utf-8")
    assert definition.user_text == (
        prompt_dir / PROMPT_DIR_USER_FILE
    ).read_text(encoding="utf-8").rstrip("\r\n")
    assert INPUT_PLACEHOLDER in definition.user_text


def test_render_formal_prompt_messages_substitutes_input_once() -> None:
    consolidation_input = "## Source Content\nsource\n\n## Conclusions\nC001"

    messages = render_formal_prompt_messages(
        prompt_id=PROMPT_ID,
        consolidation_input_text=consolidation_input,
    )

    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": consolidation_input}
    assert all(INPUT_PLACEHOLDER not in message["content"] for message in messages)


def test_unknown_comparison_mode_fails_prompt_resolution() -> None:
    with pytest.raises(ValueError, match="unknown comparison_mode_id"):
        resolve_formal_prompt_id("unknown")


def test_unknown_formal_prompt_id_fails_directory_resolution() -> None:
    with pytest.raises(ValueError, match="unknown formal prompt id"):
        resolve_formal_prompt_directory_name(
            "comparison_finding_consolidation.unknown"
        )


def test_future_mode_extension_changes_binding_without_copying_generic_core(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generic_core = (
        materialize_comparison_finding_consolidation_input,
        validate_comparison_finding_consolidation_response_structure,
        compute_comparison_finding_consolidation_alias_qc,
        execute_comparison_finding_consolidation,
    )
    monkeypatch.setitem(
        prompts_module._COMPARISON_MODE_TO_PROMPT_ID,
        "ib_to_dsur",
        PROMPT_ID,
    )

    assert resolve_formal_prompt_id("ib_to_dsur") == PROMPT_ID
    assert generic_core == (
        materialize_comparison_finding_consolidation_input,
        validate_comparison_finding_consolidation_response_structure,
        compute_comparison_finding_consolidation_alias_qc,
        execute_comparison_finding_consolidation,
    )
