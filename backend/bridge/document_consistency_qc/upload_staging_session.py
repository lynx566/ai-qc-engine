"""Bridge-owned upload staging session manifest for Document Consistency QC create-flow."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.io import load_json, save_json
from runtime.run_layout import utc_now_iso

UPLOAD_STAGING_SESSION_FILENAME = "upload_staging_session.json"
UPLOAD_STAGING_SESSION_ARTIFACT_TYPE = "upload_staging_session"
UPLOAD_STAGING_SESSION_SCHEMA_VERSION = "0.2.0"

OUTCOME_PENDING = "pending"
OUTCOME_FLOW_CREATED = "flow_created"
OUTCOME_FAILED = "failed"

_OUTCOME_VALUES = frozenset({OUTCOME_PENDING, OUTCOME_FLOW_CREATED, OUTCOME_FAILED})

_ROOT_KEYS = frozenset(
    {
        "artifact_type",
        "schema_version",
        "upload_staging_session_id",
        "created_at",
        "updated_at",
        "task_run_id",
        "task_id",
        "outcome",
        "slots",
        "flow_run_id",
        "flow_run_summary_path",
        "failure_message",
    }
)
_SLOT_KEYS = frozenset({"slot_id", "original_file_name"})


@dataclass(frozen=True, slots=True)
class UploadStagingSlotRecord:
    slot_id: str
    original_file_name: str

    def to_record(self) -> dict[str, str]:
        return {
            "slot_id": self.slot_id,
            "original_file_name": self.original_file_name,
        }


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _validate_slot_record(slot: Any, *, label: str) -> dict[str, str]:
    if not isinstance(slot, dict):
        raise TypeError(f"{label} must be an object")
    extra = set(slot) - _SLOT_KEYS
    if extra:
        raise ValueError(f"{label} has unexpected keys: {sorted(extra)!r}")
    missing = _SLOT_KEYS - set(slot)
    if missing:
        raise ValueError(f"{label} is missing required keys: {sorted(missing)!r}")
    return {
        "slot_id": _require_str(slot["slot_id"], field=f"{label}.slot_id"),
        "original_file_name": _require_str(
            slot["original_file_name"],
            field=f"{label}.original_file_name",
        ),
    }


def validate_upload_staging_session_manifest(payload: Mapping[str, Any]) -> None:
    """Validate one upload staging session manifest envelope."""

    if not isinstance(payload, Mapping):
        raise TypeError("upload_staging_session manifest must be a mapping")

    extra_root = set(payload) - _ROOT_KEYS
    if extra_root:
        raise ValueError(
            "upload_staging_session manifest has unexpected root keys: "
            f"{sorted(extra_root)!r}"
        )
    missing_root = _ROOT_KEYS - set(payload)
    if missing_root:
        raise ValueError(
            "upload_staging_session manifest is missing required root keys: "
            f"{sorted(missing_root)!r}"
        )

    artifact_type = _require_str(payload["artifact_type"], field="artifact_type")
    if artifact_type != UPLOAD_STAGING_SESSION_ARTIFACT_TYPE:
        raise ValueError(
            f"artifact_type must be {UPLOAD_STAGING_SESSION_ARTIFACT_TYPE!r}, "
            f"got {artifact_type!r}"
        )
    schema_version = _require_str(payload["schema_version"], field="schema_version")
    if schema_version != UPLOAD_STAGING_SESSION_SCHEMA_VERSION:
        raise ValueError(
            "schema_version must be "
            f"{UPLOAD_STAGING_SESSION_SCHEMA_VERSION!r}, got {schema_version!r}"
        )

    _require_str(
        payload["upload_staging_session_id"],
        field="upload_staging_session_id",
    )
    _require_str(payload["created_at"], field="created_at")
    _require_str(payload["updated_at"], field="updated_at")
    _require_str(payload["task_run_id"], field="task_run_id")
    _require_str(payload["task_id"], field="task_id")

    outcome = _require_str(payload["outcome"], field="outcome")
    if outcome not in _OUTCOME_VALUES:
        raise ValueError(
            f"outcome must be one of {sorted(_OUTCOME_VALUES)!r}, got {outcome!r}"
        )

    slots = payload["slots"]
    if not isinstance(slots, list):
        raise TypeError("slots must be a list")
    normalized_slots = [
        _validate_slot_record(slot, label=f"slots[{index}]")
        for index, slot in enumerate(slots)
    ]
    if len({slot["slot_id"] for slot in normalized_slots}) != len(normalized_slots):
        raise ValueError("slots must not contain duplicate slot_id values")

    flow_run_id = payload["flow_run_id"]
    flow_run_summary_path = payload["flow_run_summary_path"]
    failure_message = payload["failure_message"]

    if flow_run_id is not None and not (
        isinstance(flow_run_id, str) and flow_run_id.strip()
    ):
        raise ValueError("flow_run_id must be a non-empty string or null")
    if flow_run_summary_path is not None and not (
        isinstance(flow_run_summary_path, str) and flow_run_summary_path.strip()
    ):
        raise ValueError("flow_run_summary_path must be a non-empty string or null")
    if failure_message is not None and not (
        isinstance(failure_message, str) and failure_message.strip()
    ):
        raise ValueError("failure_message must be a non-empty string or null")

    if outcome == OUTCOME_PENDING:
        if flow_run_id is not None:
            raise ValueError("pending outcome must not include flow_run_id")
        if flow_run_summary_path is not None:
            raise ValueError("pending outcome must not include flow_run_summary_path")
        if failure_message is not None:
            raise ValueError("pending outcome must not include failure_message")
    elif outcome == OUTCOME_FLOW_CREATED:
        if flow_run_id is None:
            raise ValueError("flow_created outcome requires flow_run_id")
        if flow_run_summary_path is None:
            raise ValueError("flow_created outcome requires flow_run_summary_path")
        if failure_message is not None:
            raise ValueError("flow_created outcome must not include failure_message")
    elif outcome == OUTCOME_FAILED:
        if failure_message is None:
            raise ValueError("failed outcome requires failure_message")
        if flow_run_id is not None and flow_run_summary_path is None:
            raise ValueError(
                "failed outcome with flow_run_id requires flow_run_summary_path"
            )


def build_upload_staging_session_manifest(
    *,
    upload_staging_session_id: str,
    task_run_id: str,
    task_id: str,
    created_at: str,
    updated_at: str,
    outcome: str,
    slots: Sequence[UploadStagingSlotRecord],
    flow_run_id: str | None = None,
    flow_run_summary_path: Path | str | None = None,
    failure_message: str | None = None,
) -> dict[str, Any]:
    """Build and validate one upload staging session manifest."""

    manifest: dict[str, Any] = {
        "artifact_type": UPLOAD_STAGING_SESSION_ARTIFACT_TYPE,
        "schema_version": UPLOAD_STAGING_SESSION_SCHEMA_VERSION,
        "upload_staging_session_id": _require_str(
            upload_staging_session_id,
            field="upload_staging_session_id",
        ),
        "created_at": _require_str(created_at, field="created_at"),
        "updated_at": _require_str(updated_at, field="updated_at"),
        "task_run_id": _require_str(task_run_id, field="task_run_id"),
        "task_id": _require_str(task_id, field="task_id"),
        "outcome": outcome,
        "slots": [slot.to_record() for slot in slots],
        "flow_run_id": flow_run_id,
        "flow_run_summary_path": (
            Path(flow_run_summary_path).as_posix()
            if flow_run_summary_path is not None
            else None
        ),
        "failure_message": failure_message,
    }
    validate_upload_staging_session_manifest(manifest)
    return manifest


def upload_staging_session_manifest_path(session_dir: Path) -> Path:
    return session_dir / UPLOAD_STAGING_SESSION_FILENAME


@dataclass
class UploadStagingSession:
    """Mutable bridge-side writer for one upload staging session manifest."""

    session_dir: Path
    upload_staging_session_id: str
    task_run_id: str
    task_id: str
    _created_at: str | None = None
    _slots: list[UploadStagingSlotRecord] | None = None

    @property
    def manifest_path(self) -> Path:
        return upload_staging_session_manifest_path(self.session_dir)

    def initialize(self) -> None:
        """Write the initial pending manifest as soon as the session directory exists."""

        stamp = utc_now_iso()
        self._created_at = stamp
        self._slots = []
        manifest = build_upload_staging_session_manifest(
            upload_staging_session_id=self.upload_staging_session_id,
            task_run_id=self.task_run_id,
            task_id=self.task_id,
            created_at=stamp,
            updated_at=stamp,
            outcome=OUTCOME_PENDING,
            slots=(),
        )
        self._persist(manifest)

    def record_materialized_slot(
        self,
        *,
        slot_id: str,
        original_file_name: str,
    ) -> None:
        """Append one successfully materialized slot to the session manifest."""

        state = self._load_state()
        if any(slot.slot_id == slot_id for slot in state.slots):
            raise ValueError(
                f"slot {slot_id!r} is already recorded in staging manifest"
            )
        state.slots.append(
            UploadStagingSlotRecord(
                slot_id=slot_id,
                original_file_name=original_file_name,
            )
        )
        self._persist(
            build_upload_staging_session_manifest(
                upload_staging_session_id=self.upload_staging_session_id,
                task_run_id=self.task_run_id,
                task_id=self.task_id,
                created_at=state.created_at,
                updated_at=utc_now_iso(),
                outcome=OUTCOME_PENDING,
                slots=state.slots,
            )
        )

    def record_flow_created(
        self,
        *,
        flow_run_id: str,
        flow_run_summary_path: Path | str,
    ) -> None:
        state = self._load_state()
        self._persist(
            build_upload_staging_session_manifest(
                upload_staging_session_id=self.upload_staging_session_id,
                task_run_id=self.task_run_id,
                task_id=self.task_id,
                created_at=state.created_at,
                updated_at=utc_now_iso(),
                outcome=OUTCOME_FLOW_CREATED,
                slots=state.slots,
                flow_run_id=flow_run_id,
                flow_run_summary_path=flow_run_summary_path,
            )
        )

    def record_failed(
        self,
        failure_message: str,
        *,
        flow_run_id: str | None = None,
        flow_run_summary_path: Path | str | None = None,
    ) -> None:
        state = self._load_state()
        self._persist(
            build_upload_staging_session_manifest(
                upload_staging_session_id=self.upload_staging_session_id,
                task_run_id=self.task_run_id,
                task_id=self.task_id,
                created_at=state.created_at,
                updated_at=utc_now_iso(),
                outcome=OUTCOME_FAILED,
                slots=state.slots,
                flow_run_id=flow_run_id,
                flow_run_summary_path=flow_run_summary_path,
                failure_message=failure_message,
            )
        )

    def read_manifest(self) -> dict[str, Any]:
        manifest = load_json(self.manifest_path)
        validate_upload_staging_session_manifest(manifest)
        if manifest["upload_staging_session_id"] != self.upload_staging_session_id:
            raise ValueError(
                "upload_staging_session_id does not match staging session directory"
            )
        return manifest

    def _load_state(self) -> _UploadStagingSessionState:
        if self._created_at is not None and self._slots is not None:
            return _UploadStagingSessionState(
                created_at=self._created_at,
                slots=list(self._slots),
            )
        manifest = self.read_manifest()
        slots = [
            UploadStagingSlotRecord(
                slot_id=record["slot_id"],
                original_file_name=record["original_file_name"],
            )
            for record in manifest["slots"]
        ]
        self._created_at = manifest["created_at"]
        self._slots = slots
        return _UploadStagingSessionState(
            created_at=manifest["created_at"],
            slots=slots,
        )

    def _persist(self, manifest: dict[str, Any]) -> None:
        validate_upload_staging_session_manifest(manifest)
        if manifest["upload_staging_session_id"] != self.upload_staging_session_id:
            raise ValueError(
                "upload_staging_session_id does not match staging session directory"
            )
        self.session_dir.mkdir(parents=True, exist_ok=True)
        save_json(self.manifest_path, manifest)
        self._created_at = manifest["created_at"]
        self._slots = [
            UploadStagingSlotRecord(
                slot_id=record["slot_id"],
                original_file_name=record["original_file_name"],
            )
            for record in manifest["slots"]
        ]


@dataclass(frozen=True, slots=True)
class _UploadStagingSessionState:
    created_at: str
    slots: list[UploadStagingSlotRecord]


__all__ = [
    "OUTCOME_FAILED",
    "OUTCOME_FLOW_CREATED",
    "OUTCOME_PENDING",
    "UPLOAD_STAGING_SESSION_ARTIFACT_TYPE",
    "UPLOAD_STAGING_SESSION_FILENAME",
    "UPLOAD_STAGING_SESSION_SCHEMA_VERSION",
    "UploadStagingSession",
    "UploadStagingSlotRecord",
    "build_upload_staging_session_manifest",
    "upload_staging_session_manifest_path",
    "validate_upload_staging_session_manifest",
]
