"""Deterministic Findings section rendering for Verification user input."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def render_verification_findings_section(
    findings: Sequence[Mapping[str, Any]],
) -> str:
    """Render the Findings body for one Assessment job envelope."""

    rendered_blocks: list[str] = []
    for finding in findings:
        finding_id = finding["finding_id"]
        conclusion = finding["conclusion"]
        label = finding["label"]
        aliases = ", ".join(finding["source_sentence_aliases"])
        rendered_blocks.append(
            "\n".join(
                (
                    finding_id,
                    f"- `conclusion`: {conclusion}",
                    f"- `label`: {label}",
                    f"- `source_sentence_aliases`: {aliases}",
                )
            )
        )
    return "\n".join(rendered_blocks)


__all__ = ["render_verification_findings_section"]
