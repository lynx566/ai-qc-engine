"""Installed application filesystem boundaries for Document Consistency QC."""

from __future__ import annotations

from pathlib import Path

_INSTALLED_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_installed_project_root() -> Path:
    """Return the canonical artifact root for the installed application."""

    return _INSTALLED_PROJECT_ROOT


__all__ = [
    "resolve_installed_project_root",
]
