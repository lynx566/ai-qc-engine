from __future__ import annotations

from core.registry.alias import AliasEntityRecord

TARGET_PD_L1 = AliasEntityRecord(
    canonical_id="target_001",
    token="Target_001",
    aliases=(
        "programmed death-ligand 1",
        "programmed death ligand 1",
        "PD-L1",
        "PDL1",
        "PD L1",
        "CD274",
    ),
)

TARGET_CLASS_PD_1_PD_L1 = AliasEntityRecord(
    canonical_id="target_class_001",
    token="TargetClass_001",
    aliases=(
        "PD-1 / PD-L1",
        "PD-1 与 PD-L1",
        "PD-1/PD-L1",
        "PD-1及PD-L1",
        "PD-1和PD-L1",
        "PD-1或PD-L1",
        "PD-1、PD-L1",
        "PD-1与PD-L1",
    ),
)
