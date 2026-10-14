"""Aggregate Comparison materialization dev runner tests."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.source_adapter import (
    adapt_clinical_safety_aggregate_source_bundle,
)
from scripts.stage_runners.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    materialize_runner,
)


def test_runner_forwards_cross_cli_arguments_to_runtime(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    captured: dict[str, object] = {}

    def fake_runtime(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(messages=("run_id: cross_test", "artifact: result.json"))

    monkeypatch.setattr(
        "runtime.evidence_comparison.clinical_trial_doc.clinical_safety."
        "aggregate_evidence.materialization.run_aggregate_comparison_materialization",
        fake_runtime,
    )

    materialize_runner.main(
        [
            "--source-a",
            "a.json",
            "--source-b",
            "b.json",
            "--output-dir",
            str(tmp_path / "out"),
            "--run-id",
            "cross_test",
        ]
    )

    assert captured == {
        "project_root": materialize_runner.PROJECT_ROOT,
        "source_adapter": adapt_clinical_safety_aggregate_source_bundle,
        "source": None,
        "source_a": "a.json",
        "source_b": "b.json",
        "output_dir": str(tmp_path / "out"),
        "run_id": "cross_test",
    }
    assert capsys.readouterr().out.splitlines() == [
        "run_id: cross_test",
        "artifact: result.json",
    ]


def test_runner_is_the_explicit_clinical_dev_composition_boundary() -> None:
    tree = ast.parse(Path(materialize_runner.__file__).read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert (
        "runtime.evidence_comparison.clinical_trial_doc.clinical_safety."
        "aggregate_evidence.materialization"
    ) in imported_modules
    assert (
        "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
        "aggregate_evidence.source_adapter"
    ) in imported_modules
    assert not any(module.startswith("artifacts.") for module in imported_modules)
    assert not any(module.startswith("pipeline.") for module in imported_modules)
    assert not any(module.startswith("operations.") for module in imported_modules)


def test_runner_help_does_not_import_discovery_application_or_llm() -> None:
    runner_path = Path(materialize_runner.__file__).resolve()
    script = f"""
import importlib.abc
import runpy
import sys

blocked_roots = (
    "application",
    "dotenv",
    "llm",
)
blocked_modules = (
    "runtime.evidence_comparison.clinical_trial_doc.clinical_safety."
    "aggregate_evidence.comparison_finding_assessment_plan",
)

class RejectUnrelatedPhaseImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in blocked_modules or fullname.startswith(blocked_roots):
            raise RuntimeError(f"forbidden materialize import: {{fullname}}")
        return None

sys.meta_path.insert(0, RejectUnrelatedPhaseImports())
sys.argv = [r"{runner_path}", "--help"]
runpy.run_path(r"{runner_path}", run_name="__main__")
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Materialize one or two ordered aggregate evidence" in completed.stdout
