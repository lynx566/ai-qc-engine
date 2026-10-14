"""Import boundary guard for llm/debug_artifacts.py."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.operations import (
    _persist_llm_debug,
)

LLM_DEBUG_ARTIFACTS_PATH = BACKEND_ROOT / "llm" / "debug_artifacts.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "runtime.evidence_source_preparation",
    "plugins.",
)

PROMPT_NAME = "clinical_safety_aggregate_heading_scope_assessment_zh"
PROMPT_VERSION = "0.1.0"


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _is_forbidden_import(module_name: str) -> bool:
    return any(
        module_name == prefix or module_name.startswith(prefix)
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def test_llm_debug_artifacts_does_not_import_heavy_runtime_or_plugins() -> None:
    violations: list[str] = []
    for imported in _imported_module_names(_parse(LLM_DEBUG_ARTIFACTS_PATH)):
        if _is_forbidden_import(imported):
            violations.append(imported)
    assert not violations, (
        "llm/debug_artifacts.py must not import heavy runtime stages or plugins; "
        "violations:\n" + "\n".join(violations)
    )


def test_persist_llm_debug_creates_files(tmp_path: Path) -> None:
    artifacts = {
        "llm_messages": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "prompt_name": PROMPT_NAME,
            "prompt_version": PROMPT_VERSION,
            "messages": [{"role": "user", "content": "hello"}],
        },
        "prompt_txt": "[user]\nhello\n",
        "raw_text": '{"tagged_items":[]}',
        "parse_error": "",
        "run_metadata": {"prompt": {"name": PROMPT_NAME, "version": PROMPT_VERSION}},
    }
    debug_dir = _persist_llm_debug(tmp_path, artifacts)
    assert debug_dir == tmp_path / "debug"
    assert (debug_dir / "llm_messages.json").is_file()
    assert (debug_dir / "prompt.txt").read_text(encoding="utf-8") == "[user]\nhello\n"
    assert (debug_dir / "raw_text.txt").read_text(
        encoding="utf-8"
    ) == '{"tagged_items":[]}'
    assert (debug_dir / "parse_error.txt").read_text(encoding="utf-8") == ""
    assert (debug_dir / "run_metadata.json").is_file()
