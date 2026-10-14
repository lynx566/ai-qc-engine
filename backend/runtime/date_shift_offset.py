"""Runtime effective date-shift offset resolution (profile → default)."""

from __future__ import annotations

from privacy.profile import DEFAULT_DATE_SHIFT_OFFSET_DAYS, PrivacyProfile


def resolve_effective_date_shift_offset_days(
    *,
    profile: PrivacyProfile,
) -> int:
    """
    Resolve the offset used for a privacy transform run.

    Priority:
    1. ``profile.date_shift_offset_days``
    2. ``DEFAULT_DATE_SHIFT_OFFSET_DAYS``
    """
    profile_offset = profile.date_shift_offset_days
    if profile_offset is not None:
        return profile_offset

    return DEFAULT_DATE_SHIFT_OFFSET_DAYS
