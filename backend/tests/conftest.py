"""Shared pytest configuration for backend tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tests.external_llm_guard import (
    install_external_llm_execution_guard,
    install_external_llm_factory_guard,
    is_allow_external_provider_factory_opted_in,
    is_live_llm_opted_in,
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live_llm: opt in to real external LLM factory construction and execution",
    )
    config.addinivalue_line(
        "markers",
        (
            "allow_external_provider_factory: opt in to real provider factory "
            "construction without network execution"
        ),
    )


@pytest.fixture(autouse=True)
def _external_llm_fail_closed_guard(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if is_live_llm_opted_in(request):
        return
    if not is_allow_external_provider_factory_opted_in(request):
        install_external_llm_factory_guard(monkeypatch)
    install_external_llm_execution_guard(monkeypatch)


@pytest.fixture(scope="session")
def paused_canonical_flow_baseline(tmp_path_factory: pytest.TempPathFactory):
    from tests.candidate_scope_isolation import build_paused_canonical_flow_baseline

    cache_root = tmp_path_factory.mktemp("candidate_scope_paused_baseline")
    return build_paused_canonical_flow_baseline(cache_root)


@pytest.fixture
def representative_qc_task_run(tmp_path: Path) -> tuple[Path, str]:
    from tests.qc_report_representative_fixture import (
        install_representative_qc_task_run,
    )

    return tmp_path, install_representative_qc_task_run(tmp_path)


@pytest.fixture
def paused_flow(
    tmp_path: Path,
    paused_canonical_flow_baseline,
) -> tuple:
    from tests.candidate_scope_isolation import clone_paused_canonical_flow_workspace

    return clone_paused_canonical_flow_workspace(
        tmp_path,
        paused_canonical_flow_baseline,
    )
