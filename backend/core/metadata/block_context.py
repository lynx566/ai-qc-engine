from __future__ import annotations

from .schemas import DocumentContextBlock, MetadataContextConfig


def require_analysis_bundle(bundle: dict) -> None:
    stage = bundle.get("stage")
    if stage != "prepare_analysis":
        raise ValueError(
            "doc_meta requires analysis_bundle (stage=prepare_analysis); "
            f"got stage={stage!r}"
        )


def analysis_block_text(block: dict) -> str:
    """
    Analysis textual content for doc_meta context.

    Prefers ``analysis_text``, then canonical ``normalized_text``. ``text`` is
    retained only as a legacy artifact fallback. Never uses structural heading
    metadata (``meta.heading_text_stripped``, etc.).
    """
    text = (
        block.get("analysis_text")
        or block.get("normalized_text")
        or block.get("text")
        or ""
    )
    return str(text).strip()


def masked_block_text(block: dict) -> str:
    """Deprecated alias for :func:`analysis_block_text`."""
    return analysis_block_text(block)


def build_document_context_blocks(
    bundle: dict,
    context: MetadataContextConfig,
    block_count: int | None = None,
    block_source_key: str = "content_blocks",
) -> list[DocumentContextBlock]:
    if context.strategy != "first_n_content_blocks":
        raise ValueError(f"Unsupported metadata context strategy: {context.strategy}")

    require_analysis_bundle(bundle)

    n = block_count if block_count is not None else context.default_block_count
    raw_blocks = bundle.get(block_source_key, [])[:n]

    context_blocks: list[DocumentContextBlock] = []

    for block in raw_blocks:
        if not isinstance(block, dict):
            continue

        text = masked_block_text(block)
        if not text:
            continue

        context_blocks.append(
            DocumentContextBlock(
                block_id=str(block.get("block_id", "")),
                kind=str(block.get("kind", "")),
                text=text,
                order=block.get("order"),
            )
        )

    return context_blocks
