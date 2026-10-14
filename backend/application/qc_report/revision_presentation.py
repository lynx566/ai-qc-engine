"""Codepoint edit reconstruction over validated canonical report annotations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from application.qc_report.presentation_model import (
    AnnotationMetadata,
    CommentPresentation,
    RevisionPresentation,
    SentenceReviewPresentation,
)

REVISION_CONFLICT_NOTICE = (
    "修订范围存在冲突，未生成合并后的修订句；请逐条核对修订片段。"
)


def project_sentence_reviews(
    original_sentence_text: str, annotations: Sequence[Mapping[str, Any]]
) -> SentenceReviewPresentation:
    """Keep annotation order; reconstruct once against original offsets.

    The entry validator has already checked canonical identity and slices.
    Overlapping (including identical/contained) edits are valid report facts,
    but no combined text can safely be inferred. Highlights are not body items.
    """
    revisions, comments = [], []
    for annotation in annotations:
        kind = annotation["kind"]
        if kind == "highlight":
            continue
        metadata = AnnotationMetadata(
            annotation["annotation_ref"],
            annotation["annotation_id"],
            annotation["created_at"],
            annotation["updated_at"],
            tuple(annotation["related_finding_refs"]),
        )
        if kind == "edit":
            selected_range = annotation["range"]
            revisions.append(
                RevisionPresentation(
                    annotation["selected_original_text"],
                    annotation["replacement_text"],
                    selected_range["start_offset"],
                    selected_range["end_offset"],
                    metadata,
                )
            )
        else:
            comments.append(
                CommentPresentation(
                    annotation["selected_original_text"],
                    annotation["content"],
                    metadata,
                )
            )
    ordered = sorted(revisions, key=lambda revision: revision.start_offset)
    conflict = any(
        earlier.end_offset > later.start_offset
        for earlier, later in zip(ordered, ordered[1:])
    )
    revised = None
    if revisions and not conflict:
        revised = original_sentence_text
        for revision in reversed(ordered):
            revised = (
                revised[: revision.start_offset]
                + revision.replacement_text
                + revised[revision.end_offset :]
            )
    return SentenceReviewPresentation(
        tuple(revisions),
        tuple(comments),
        revised,
        conflict,
        REVISION_CONFLICT_NOTICE if conflict else None,
    )
