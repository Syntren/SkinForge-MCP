"""
Backward-compatible re-export of validator and aesthetic scoring from skinforge.audit.
"""

from .audit.aesthetic import (
    compute_aesthetic_score,
    detect_pillow_shading,
    evaluate_golden_rules,
)
from .audit.validator import SkinValidator, auto_fix_skin

__all__ = [
    "SkinValidator",
    "auto_fix_skin",
    "compute_aesthetic_score",
    "detect_pillow_shading",
    "evaluate_golden_rules",
]
