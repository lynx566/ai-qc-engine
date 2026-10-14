from __future__ import annotations

from privacy.detectors.base import SensitiveEntityDetector
from privacy.detectors.composite import CompositeDetector
from privacy.detectors.local_model_detector import LocalModelDetector
from privacy.detectors.mock_detector import MockDetector
from privacy.detectors.regex_detector import RegexDetector, RegexRule

__all__ = [
    "CompositeDetector",
    "LocalModelDetector",
    "MockDetector",
    "RegexDetector",
    "RegexRule",
    "SensitiveEntityDetector",
    "UIEDetector",
]


def __getattr__(name: str):
    if name == "UIEDetector":
        from privacy.detectors.uie_detector import UIEDetector

        return UIEDetector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
