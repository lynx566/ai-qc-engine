from __future__ import annotations

from core.registry.alias import AliasEntityRecord

DOSE_LEVEL_001 = AliasEntityRecord(
    canonical_id="dose_level_001",
    token="DoseLevel_001",
    aliases=(
        "0.3 mg/kg Q3W",
        "0.3mg/kg Q3W",
        "0.3 mg/kg",
        "0.3mg/kg",
    ),
)

DOSE_LEVEL_002 = AliasEntityRecord(
    canonical_id="dose_level_002",
    token="DoseLevel_002",
    aliases=(
        "1 mg/kg Q3W",
        "1mg/kg Q3W",
        "1 mg/kg",
        "1mg/kg",
    ),
)

DOSE_LEVEL_003 = AliasEntityRecord(
    canonical_id="dose_level_003",
    token="DoseLevel_003",
    aliases=(
        "3 mg/kg Q3W",
        "3mg/kg Q3W",
        "3 mg/kg",
        "3mg/kg",
    ),
)
