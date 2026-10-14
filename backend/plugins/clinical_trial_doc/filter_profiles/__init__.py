"""Filter-stage recall profiles for clinical document source selection.

In this package, filter profiles define recall-oriented source selection rules
for the filter stage. They are not semantic evidence types. Evidence routing into
aggregate/table/case/risk branches happens later in tag_prepare.
"""

from __future__ import annotations

from .csr import (
    CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    CSR_OVERVIEW_FILTER_PROFILE_ZH,
)
from .dsur import (
    DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    DSUR_OVERVIEW_FILTER_PROFILE_ZH,
)
from .ib import (
    IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH,
    IB_OVERVIEW_FILTER_PROFILE_ZH,
)

__all__ = [
    "CSR_CLINICAL_SAFETY_FILTER_PROFILE_ZH",
    "CSR_OVERVIEW_FILTER_PROFILE_ZH",
    "DSUR_CLINICAL_SAFETY_FILTER_PROFILE_ZH",
    "DSUR_OVERVIEW_FILTER_PROFILE_ZH",
    "IB_CLINICAL_SAFETY_FILTER_PROFILE_ZH",
    "IB_OVERVIEW_FILTER_PROFILE_ZH",
]
