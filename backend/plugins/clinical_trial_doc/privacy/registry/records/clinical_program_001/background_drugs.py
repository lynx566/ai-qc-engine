from __future__ import annotations

from core.registry.alias import AliasEntityRecord

BACKGROUND_DRUG_CARBOPLATIN = AliasEntityRecord(
    canonical_id="background_drug_001",
    token="BackgroundDrug_001",
    aliases=(
        "卡铂",
        "carboplatin",
        "Carboplatin",
    ),
)

BACKGROUND_DRUG_PEMETREXED = AliasEntityRecord(
    canonical_id="background_drug_002",
    token="BackgroundDrug_002",
    aliases=(
        "培美曲塞",
        "pemetrexed",
        "Pemetrexed",
    ),
)
