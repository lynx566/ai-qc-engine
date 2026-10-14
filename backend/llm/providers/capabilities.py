from __future__ import annotations

from dataclasses import dataclass

JSON_OBJECT_RESPONSE_FORMAT: dict[str, str] = {"type": "json_object"}


@dataclass(frozen=True)
class ProviderCapabilities:
    """Declared API features for a tag-stage LLM provider."""

    supports_json_object_response_format: bool
    notes: str = ""


DEEPSEEK_CAPABILITIES = ProviderCapabilities(
    supports_json_object_response_format=True,
    notes="deepseek-v4-flash supports OpenAI-compatible response_format json_object.",
)

BAILIAN_QWEN_CAPABILITIES = ProviderCapabilities(
    supports_json_object_response_format=False,
    notes=(
        "DashScope compatible-mode json_object support is model-dependent; "
        "qwen3.5-flash is not declared compatible — response_format omitted."
    ),
)

PROVIDER_CAPABILITIES = {
    "deepseek": DEEPSEEK_CAPABILITIES,
    "bailian_qwen": BAILIAN_QWEN_CAPABILITIES,
}
