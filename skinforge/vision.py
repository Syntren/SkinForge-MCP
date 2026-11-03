"""
Backward-compatible re-export of visual feature extraction from skinforge.rag.vision.
"""

from .rag.vision import (
    FEATURE_DIM,
    compute_visual_similarity,
    extract_visual_features,
    pack_feature_blob,
    unpack_feature_blob,
)

__all__ = [
    "FEATURE_DIM",
    "extract_visual_features",
    "pack_feature_blob",
    "unpack_feature_blob",
    "compute_visual_similarity",
]
