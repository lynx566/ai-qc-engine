"""Import-boundary regressions for optional API-provider dependencies."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.providers.blocked_openai import EXTERNAL_LLM_EXECUTION_DISABLED_MESSAGE
from tests.external_llm_guard import isolated_subprocess_env

RUNNER_ROOT = BACKEND_ROOT / "scripts" / "stage_runners"


def _run_isolated(
    script: str,
    *args: str,
    disable_external_llm: bool = True,
) -> subprocess.CompletedProcess[str]:
    isolated_script = textwrap.dedent(script).replace(
        "__BLOCK_OPENAI__",
        textwrap.dedent(_BLOCK_OPENAI).strip(),
    )
    return subprocess.run(
        [sys.executable, "-c", isolated_script, *args],
        cwd=BACKEND_ROOT,
        env=isolated_subprocess_env(
            backend_root=BACKEND_ROOT,
            disable_external_llm=disable_external_llm,
        ),
        capture_output=True,
        text=True,
        check=False,
    )


_BLOCK_OPENAI = """
import importlib.abc

class BlockOpenAI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "openai" or fullname.startswith("openai."):
            raise ModuleNotFoundError("openai deliberately blocked by isolation test")
        return None

sys.meta_path.insert(0, BlockOpenAI())
"""


@pytest.mark.parametrize(
    "module_name",
    [
        "llm.providers.base",
        "llm.providers.factory",
    ],
)
def test_neutral_provider_imports_do_not_load_concrete_providers(
    module_name: str,
) -> None:
    result = _run_isolated(
        """
        import sys
        __BLOCK_OPENAI__
        __import__(sys.argv[1])
        forbidden = [
            name
            for name in (
                "llm.providers.bailian",
                "llm.providers.deepseek",
                "openai",
            )
            if name in sys.modules
        ]
        if forbidden:
            raise AssertionError(f"unexpected imports: {forbidden}")
        """,
        module_name,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("profile", "api_key_name", "selected_module", "other_module"),
    [
        (
            "qwen3_7_max",
            "DASHSCOPE_API_KEY",
            "llm.providers.bailian",
            "llm.providers.deepseek",
        ),
        (
            "deepseek_v4_flash",
            "DEEPSEEK_API_KEY",
            "llm.providers.deepseek",
            "llm.providers.bailian",
        ),
    ],
)
def test_factory_loads_only_selected_concrete_provider(
    profile: str,
    api_key_name: str,
    selected_module: str,
    other_module: str,
) -> None:
    result = _run_isolated(
        """
        import os
        import sys

        from llm.providers.factory import build_api_provider

        concrete = {
            "llm.providers.bailian",
            "llm.providers.deepseek",
        }
        assert concrete.isdisjoint(sys.modules)
        os.environ[sys.argv[2]] = "test-key"
        if sys.argv[1].startswith("qwen"):
            os.environ["BAILIAN_BASE_URL"] = "https://example.invalid/compatible-mode/v1"
        build_api_provider(llm_profile=sys.argv[1])
        assert sys.argv[3] in sys.modules
        assert sys.argv[4] not in sys.modules
        """,
        profile,
        api_key_name,
        selected_module,
        other_module,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("profile", "api_key_name"),
    [
        ("qwen3_7_max", "DASHSCOPE_API_KEY"),
        ("deepseek_v4_flash", "DEEPSEEK_API_KEY"),
    ],
)
def test_subprocess_provider_generate_is_blocked_with_api_key(
    profile: str,
    api_key_name: str,
) -> None:
    result = _run_isolated(
        f"""
        import os
        import sys

        from llm.providers.factory import build_api_provider

        os.environ[sys.argv[2]] = "test-key"
        if sys.argv[1].startswith("qwen"):
            os.environ["BAILIAN_BASE_URL"] = "https://example.invalid/compatible-mode/v1"
        provider = build_api_provider(llm_profile=sys.argv[1])
        try:
            provider.generate([{{"role": "user", "content": "hi"}}])
        except RuntimeError as exc:
            if "{EXTERNAL_LLM_EXECUTION_DISABLED_MESSAGE}" not in str(exc):
                raise
        else:
            raise AssertionError("provider.generate unexpectedly succeeded")
        """,
        profile,
        api_key_name,
    )

    assert result.returncode == 0, result.stderr


def test_missing_openai_fails_only_when_selected_provider_is_built() -> None:
    result = _run_isolated(
        """
        import os
        import sys
        __BLOCK_OPENAI__
        import llm.providers.base
        from llm.providers.factory import build_api_provider

        os.environ["DEEPSEEK_API_KEY"] = "test-key"
        try:
            build_api_provider(llm_profile="deepseek_v4_flash")
        except ModuleNotFoundError as exc:
            if exc.name != "openai" and "openai deliberately blocked" not in str(exc):
                raise
        else:
            raise AssertionError("provider construction unexpectedly succeeded")
        """,
        disable_external_llm=False,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "runner",
    [
        RUNNER_ROOT / "extract_runner.py",
        RUNNER_ROOT / "prepare_analysis_runner.py",
    ],
)
def test_non_llm_runner_help_does_not_import_openai(runner: Path) -> None:
    result = _run_isolated(
        """
        import runpy
        import sys
        __BLOCK_OPENAI__
        runner = sys.argv[1]
        sys.argv = [runner, "--help"]
        try:
            runpy.run_path(runner, run_name="__main__")
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise
        """,
        str(runner),
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
