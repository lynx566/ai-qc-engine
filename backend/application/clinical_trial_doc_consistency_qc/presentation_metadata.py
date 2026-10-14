"""DCQC Flow capability presentation metadata (Flow-owned, not Product Task)."""

from __future__ import annotations

from types import MappingProxyType

from application.document_consistency_qc.catalog import (
    DocumentConsistencyQcCapabilityPresentationMetadata,
)

_INTERNAL_DSUR_PRESENTATION = DocumentConsistencyQcCapabilityPresentationMetadata(
    display_name="研发期间安全性更新报告（DSUR）",
    description="单份研发期间安全性更新报告（DSUR）的质控任务。",
    slot_upload_labels={"source": "点击或拖拽上传DSUR"},
    slot_help_texts={
        "source": "请上传待核查的 DSUR Word 文档（.docx）。",
    },
)
_INTERNAL_IB_PRESENTATION = DocumentConsistencyQcCapabilityPresentationMetadata(
    display_name="研究者手册（IB）",
    description="单份研究者手册（IB）的质控任务。",
    slot_upload_labels={"source": "点击或拖拽上传IB"},
    slot_help_texts={
        "source": "请上传待核查的 IB Word 文档（.docx）。",
    },
)
_INTERNAL_CSR_PRESENTATION = DocumentConsistencyQcCapabilityPresentationMetadata(
    display_name="临床研究报告（CSR）",
    description="单份临床研究报告（CSR）的质控任务。",
    slot_upload_labels={"source": "点击或拖拽上传CSR"},
    slot_help_texts={
        "source": "请上传待核查的 CSR Word 文档（.docx）。",
    },
)
_DSUR_UPDATED_IB_PRESENTATION = DocumentConsistencyQcCapabilityPresentationMetadata(
    display_name="DSUR↔IB",
    description="面向 DSUR 与 IB 两份文件的文件间质控任务。",
    slot_upload_labels={
        "source_a": "点击或拖拽上传DSUR",
        "source_b": "点击或拖拽上传IB",
    },
    slot_help_texts={
        "source_a": "请上传 DSUR Word 文档（.docx）。",
        "source_b": "请上传更新版 IB Word 文档（.docx）。",
    },
)

_DCQC_CAPABILITY_PRESENTATION: dict[str, DocumentConsistencyQcCapabilityPresentationMetadata] = {
    "internal_dsur": _INTERNAL_DSUR_PRESENTATION,
    "internal_ib": _INTERNAL_IB_PRESENTATION,
    "internal_csr": _INTERNAL_CSR_PRESENTATION,
    "dsur_updated_ib": _DSUR_UPDATED_IB_PRESENTATION,
}

INSTALLED_DCQC_CAPABILITY_PRESENTATION: MappingProxyType[
    str, DocumentConsistencyQcCapabilityPresentationMetadata
] = MappingProxyType(_DCQC_CAPABILITY_PRESENTATION)


def presentation_for_dcqc_capability_id(
    capability_id: str,
) -> DocumentConsistencyQcCapabilityPresentationMetadata | None:
    """Return Flow-owned presentation for one installed DCQC capability id."""

    if not isinstance(capability_id, str) or not capability_id.strip():
        return None
    return INSTALLED_DCQC_CAPABILITY_PRESENTATION.get(capability_id.strip())


__all__ = [
    "INSTALLED_DCQC_CAPABILITY_PRESENTATION",
    "presentation_for_dcqc_capability_id",
]
