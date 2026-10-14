from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

PrivacyTransformSlot = Literal["after_extract", "after_filter"]
PrivacyDetectorName = Literal["registry", "regex", "uie"]

PRIVACY_TRANSFORM_SLOTS: tuple[PrivacyTransformSlot, ...] = (
    "after_extract",
    "after_filter",  # reserved; not enabled in production
)
SUPPORTED_DETECTORS: frozenset[str] = frozenset({"registry", "regex", "uie"})
DEPRECATED_DETECTORS: frozenset[str] = frozenset({"dictionary"})


def validate_detector_name(name: str) -> PrivacyDetectorName:
    if name in DEPRECATED_DETECTORS:
        raise ValueError(f"detector {name!r} is no longer supported")
    if name not in SUPPORTED_DETECTORS:
        raise ValueError(
            f"unknown detector {name!r}; supported: {sorted(SUPPORTED_DETECTORS)}"
        )
    return name  # type: ignore[return-value]


def validate_detector_list(detectors: list[str]) -> list[PrivacyDetectorName]:
    return [validate_detector_name(str(d)) for d in detectors]


def parse_detector_csv(value: str | None) -> list[PrivacyDetectorName]:
    """Parse comma-separated CLI detector list. Empty or omitted → ``[]``."""
    if value is None or value.strip() == "":
        return []
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return validate_detector_list(parts)


PRIVACY_DETECTORS_CLI_CONFLICT_MSG = (
    "Use either --privacy-detectors or --privacy-after-extract-detectors, not both."
)


def resolve_after_extract_cli(
    *,
    privacy_detectors: str | None,
    privacy_after_extract_detectors: str | None,
) -> str | None:
    """Map daily ``--privacy-detectors`` shortcut to after_extract CLI value."""
    if privacy_detectors is not None and privacy_after_extract_detectors is not None:
        raise ValueError(PRIVACY_DETECTORS_CLI_CONFLICT_MSG)
    if privacy_detectors is not None:
        return privacy_detectors
    return privacy_after_extract_detectors


def _empty_transforms() -> dict[PrivacyTransformSlot, "TransformConfig"]:
    return {slot: TransformConfig(detectors=[]) for slot in PRIVACY_TRANSFORM_SLOTS}


@dataclass(slots=True)
class TransformConfig:
    detectors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        validate_detector_list(self.detectors)


@dataclass(slots=True)
class PrivacyConfig:
    """
    Pipeline privacy transform configuration.

    **Execution source of truth:** ``transforms[slot].detectors`` only.
    Slot names mark insertion points; they do not restrict detector choice.
    Empty list → identity ``analysis_text`` for that slot.
    """

    transforms: dict[PrivacyTransformSlot, TransformConfig] = field(
        default_factory=_empty_transforms
    )

    def __post_init__(self) -> None:
        for slot in PRIVACY_TRANSFORM_SLOTS:
            if slot not in self.transforms:
                self.transforms[slot] = TransformConfig(detectors=[])

    @classmethod
    def default(cls) -> PrivacyConfig:
        """No detectors on any transform slot."""
        return cls(transforms=_empty_transforms())

    @classmethod
    def from_cli(
        cls,
        *,
        after_extract: str | None = None,
        after_filter: str | None = None,
    ) -> PrivacyConfig:
        return cls(
            transforms={
                "after_extract": TransformConfig(
                    detectors=parse_detector_csv(after_extract)
                ),
                "after_filter": TransformConfig(
                    detectors=parse_detector_csv(after_filter)
                ),
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PrivacyConfig:
        transforms_raw = data.get("transforms") or {}
        transforms = _empty_transforms()
        for slot in PRIVACY_TRANSFORM_SLOTS:
            slot_data = transforms_raw.get(slot)
            if isinstance(slot_data, dict) and "detectors" in slot_data:
                transforms[slot] = TransformConfig(
                    detectors=[str(d) for d in slot_data["detectors"]]
                )
        return cls(transforms=transforms)

    def transform_detectors(self, slot: PrivacyTransformSlot) -> list[str]:
        return list(self.transforms[slot].detectors)

    def with_transform_detectors(
        self,
        slot: PrivacyTransformSlot,
        detectors: list[str],
    ) -> PrivacyConfig:
        updated = dict(self.transforms)
        updated[slot] = TransformConfig(detectors=list(detectors))
        return PrivacyConfig(transforms=updated)

    def privacy_enabled(self) -> bool:
        return any(self.transform_detectors(slot) for slot in PRIVACY_TRANSFORM_SLOTS)

    def bundle_privacy_metadata(
        self,
        *,
        executed_slot: PrivacyTransformSlot,
        detectors_used: list[str],
        slot_applied: bool,
    ) -> dict[str, Any]:
        """Top-level analysis_bundle privacy fields."""
        return {
            "privacy_enabled": self.privacy_enabled(),
            "privacy_transforms": self._transform_metadata(
                executed_slot=executed_slot,
                detectors_used=detectors_used,
                slot_applied=slot_applied,
                include_used_in_slot=True,
            ),
        }

    def run_summary_privacy_transforms(
        self,
        *,
        executed_slot: PrivacyTransformSlot,
        detectors_used: list[str],
        slot_applied: bool,
    ) -> dict[str, Any]:
        return self._transform_metadata(
            executed_slot=executed_slot,
            detectors_used=detectors_used,
            slot_applied=slot_applied,
            include_used_in_slot=False,
            summary_keys=True,
        )

    def _transform_metadata(
        self,
        *,
        executed_slot: PrivacyTransformSlot,
        detectors_used: list[str],
        slot_applied: bool,
        include_used_in_slot: bool,
        summary_keys: bool = False,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for slot in PRIVACY_TRANSFORM_SLOTS:
            configured = self.transform_detectors(slot)
            if slot == executed_slot:
                used = list(detectors_used)
                applied = slot_applied
            else:
                used = []
                applied = False

            if summary_keys:
                entry: dict[str, Any] = {
                    "detectors_configured": configured,
                    "detectors_used": used,
                    "applied": applied,
                }
            else:
                entry = {
                    "detectors": configured,
                    "applied": applied,
                }
                if include_used_in_slot and slot == executed_slot:
                    entry["detectors_used"] = used
            out[slot] = entry
        return out
