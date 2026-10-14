"""Content-boundary validation for Aggregate Evidence assessment_input artifacts."""

from __future__ import annotations

from typing import Any

_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "normalized_text",
        "span_map",
        "source_ref",
        "document_meta",
        "privacy_transforms",
        "mapping_store",
        "matched_rule",
        "evidence",
        "coverage",
    }
)


def assert_assessment_input_safe(payload: dict[str, Any]) -> None:
    """Raise ``ValueError`` if *payload* contains forbidden debug or raw fields."""

    def _walk(value: Any, *, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in _FORBIDDEN_OUTPUT_KEYS:
                    raise ValueError(f"forbidden key {key!r} at {path}")
                if key == "fields":
                    raise ValueError(f"forbidden key 'fields' at {path}")
                if path.endswith(".temporal_context") or path == "llm_input_bundle.temporal_context":
                    if key == "days":
                        raise ValueError(
                            f"forbidden key 'days' in llm_input temporal_context at {path}"
                        )
                _walk(item, path=f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                _walk(item, path=f"{path}[{index}]")

    _walk(payload, path="llm_input_bundle")
    temporal_context = payload.get("temporal_context")
    if isinstance(temporal_context, dict):
        date_transform = temporal_context.get("date_transform")
        if isinstance(date_transform, dict) and "days" in date_transform:
            raise ValueError(
                "forbidden key 'days' in llm_input temporal_context.date_transform"
            )
