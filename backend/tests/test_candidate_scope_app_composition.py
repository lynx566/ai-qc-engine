"""Explicit Candidate Scope app configuration and stage-tool import isolation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_app_import_without_runner_requires_explicit_config() -> None:
    code = """
import importlib.abc
import sys
from pathlib import Path

class BlockRunner(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'scripts.stage_runners' or fullname.startswith('scripts.stage_runners.'):
            raise AssertionError('Bridge imported runner tooling: ' + fullname)

sys.meta_path.insert(0, BlockRunner())
from bridge.candidate_scope import app as app_module
from bridge.candidate_scope.bridge_runtime import BridgeRuntimeConfig

assert not hasattr(app_module, 'app'), 'Import must not create a default app'
try:
    app_module.create_app()
except TypeError:
    pass
else:
    raise AssertionError('App factory must require explicit bridge_config')

root = Path.cwd()
config = BridgeRuntimeConfig(workspace_root=root, runs_root=root / 'runs', git_root=root.parent)
app = app_module.create_app(bridge_config=config)
assert {'/api/candidate-scope/state', '/api/candidate-scope/document', '/api/candidate-scope/next'} <= {route.path for route in app.routes}
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
