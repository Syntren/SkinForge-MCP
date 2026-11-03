"""
SkinForge RAG & Visual Search Package (v1.3.0).
"""

from .engine import DEFAULT_DB_DIR, DEFAULT_PREVIEW_DIR, SkinRAG, get_rag, set_rag_db_path
from .packer import init_rag_schema, pack_rag_database
from .vision import (
    FEATURE_DIM,
    compute_visual_similarity,
    extract_visual_features,
    pack_feature_blob,
    unpack_feature_blob,
)

__all__ = [
    "DEFAULT_DB_DIR",
    "DEFAULT_PREVIEW_DIR",
    "SkinRAG",
    "get_rag",
    "set_rag_db_path",
    "init_rag_schema",
    "pack_rag_database",
    "FEATURE_DIM",
    "extract_visual_features",
    "pack_feature_blob",
    "unpack_feature_blob",
    "compute_visual_similarity",
]
