"""Scoped pipeline logging for the clinical-trial document QC HTTP server."""

from __future__ import annotations

import logging

from bridge.clinical_trial_doc_qc.pipeline_logging import (
    configure_product_server_pipeline_logging,
    reset_product_server_pipeline_logging_for_tests,
)

BAILIAN_LOGGER = "llm.providers.bailian"
INVOCATION_LOGGER = "llm.invocation"
COMPARISON_EXECUTION_LOGGER = (
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution"
)
LLM_PARENT_LOGGER = "llm"
COMPARISON_PARENT_LOGGER = "plugins.clinical_trial_doc.evidence_comparison"


def setup_function() -> None:
    reset_product_server_pipeline_logging_for_tests()


def teardown_function() -> None:
    reset_product_server_pipeline_logging_for_tests()


def test_configure_enables_info_for_pipeline_loggers() -> None:
    configure_product_server_pipeline_logging()

    assert logging.getLogger(BAILIAN_LOGGER).isEnabledFor(logging.INFO)
    assert logging.getLogger(INVOCATION_LOGGER).isEnabledFor(logging.INFO)
    assert logging.getLogger(COMPARISON_EXECUTION_LOGGER).isEnabledFor(logging.INFO)


def test_configure_does_not_raise_third_party_loggers() -> None:
    configure_product_server_pipeline_logging()

    for name in ("httpx", "httpcore", "openai", "urllib3"):
        assert logging.getLogger(name).getEffectiveLevel() == logging.WARNING


def test_configure_is_idempotent_single_handler_per_parent() -> None:
    configure_product_server_pipeline_logging()
    configure_product_server_pipeline_logging()

    llm_logger = logging.getLogger(LLM_PARENT_LOGGER)
    comparison_logger = logging.getLogger(COMPARISON_PARENT_LOGGER)
    assert len(llm_logger.handlers) == 1
    assert len(comparison_logger.handlers) == 1
    assert llm_logger.handlers[0] is comparison_logger.handlers[0]


def test_pipeline_info_reaches_configured_handler() -> None:
    configure_product_server_pipeline_logging()
    bailian = logging.getLogger(BAILIAN_LOGGER)
    bailian.info("bailian generate started model=%s", "qwen-test")

    handler = logging.getLogger(LLM_PARENT_LOGGER).handlers[0]
    assert isinstance(handler, logging.Handler)
    assert handler.formatter is not None


def test_warnings_still_enabled_on_pipeline_loggers() -> None:
    configure_product_server_pipeline_logging()
    invocation = logging.getLogger(INVOCATION_LOGGER)
    assert invocation.isEnabledFor(logging.WARNING)
