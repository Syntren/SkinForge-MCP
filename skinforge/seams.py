"""
Backward-compatible re-export of seams auditing and alignment from skinforge.audit.seams.
"""

from .audit.seams import SEAM_PAIRS, align_seams, check_seams

__all__ = [
    "SEAM_PAIRS",
    "check_seams",
    "align_seams",
]
