"""Scoped INFO logging for the Product HTTP server QC pipeline."""

from __future__ import annotations

import logging
import sys
from typing import Final

# Parent loggers only: child modules use logging.getLogger(__name__).
_PIPELINE_LOGGER_NAMES: Final[tuple[str, ...]] = (
    "llm",
    "plugins.clinical_trial_doc.evidence_comparison",
)

_PIPELINE_HANDLER_ATTR = "_clinical_trial_doc_qc_pipeline_handler"
_CONFIGURED = False


def _pipeline_log_formatter() -> logging.Formatter:
    return logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def configure_product_server_pipeline_logging() -> None:
    """Enable INFO for project QC / LLM loggers without raising the root logger.

    Safe to call more than once (e.g. import + main). Does not configure third-party
    loggers (httpx, openai, urllib3). Does not change uvicorn's own loggers.
    """

    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_pipeline_log_formatter())
    setattr(handler, _PIPELINE_HANDLER_ATTR, True)

    for logger_name in _PIPELINE_LOGGER_NAMES:
        pipeline_logger = logging.getLogger(logger_name)
        pipeline_logger.setLevel(logging.INFO)
        pipeline_logger.propagate = False
        if not _has_pipeline_handler(pipeline_logger):
            pipeline_logger.addHandler(handler)

    _CONFIGURED = True


def _has_pipeline_handler(logger: logging.Logger) -> bool:
    return any(
        getattr(handler, _PIPELINE_HANDLER_ATTR, False) for handler in logger.handlers
    )


def reset_product_server_pipeline_logging_for_tests() -> None:
    """Restore default hierarchy (tests only)."""

    global _CONFIGURED
    for logger_name in _PIPELINE_LOGGER_NAMES:
        pipeline_logger = logging.getLogger(logger_name)
        pipeline_logger.handlers = [
            handler
            for handler in pipeline_logger.handlers
            if not getattr(handler, _PIPELINE_HANDLER_ATTR, False)
        ]
        pipeline_logger.setLevel(logging.NOTSET)
        pipeline_logger.propagate = True
    _CONFIGURED = False


__all__ = [
    "configure_product_server_pipeline_logging",
    "reset_product_server_pipeline_logging_for_tests",
]
