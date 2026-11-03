"""
SkinForge Vision - 299-Dimensional CIELAB Spatial-Color Pyramid Feature Extractor.

Computes a normalized 299-dimensional spatial-color feature vector in perceptual CIELAB
color space, strictly ignoring transparent pixels (alpha == 0), and supports compact
float16 BLOB serialization (598 bytes per skin) for portable SQLite RAG databases.
"""

from __future__ import annotations

import io
import os
from typing import Final, Union
import numpy as np
from PIL import Image

from ..color.spaces import rgb_to_cielab

FEATURE_DIM: Final[int] = 299  # 128 (8x4x4 global LAB) + 3 * (54 (6x3x3 zone LAB) + 3 (zone mean LAB))


def _load_rgba_for_vision(image_input: Union[str, bytes, os.PathLike, Image.Image, np.ndarray]) -> np.ndarray:
    if isinstance(image_input, np.ndarray):
        arr = np.asarray(image_input, dtype=np.uint8)
        if arr.ndim == 3 and arr.shape[-1] == 4:
            pil_im = Image.fromarray(arr, "RGBA")
        elif arr.ndim == 3 and arr.shape[-1] == 3:
            pil_im = Image.fromarray(arr, "RGB").convert("RGBA")
        else:
            raise ValueError(f"Unsupported ndarray shape for vision features: {arr.shape}")
    elif isinstance(image_input, Image.Image):
        pil_im = image_input.convert("RGBA")
    elif isinstance(image_input, (bytes, bytearray)):
        pil_im = Image.open(io.BytesIO(image_input)).convert("RGBA")
    elif isinstance(image_input, (str, os.PathLike)) or hasattr(image_input, "read"):
        pil_im = Image.open(image_input).convert("RGBA")
    else:
        raise ValueError(f"Unsupported image input type: {type(image_input)}")

    # Use NEAREST resampling to avoid bleeding transparent [0,0,0,0] black into adjacent opaque pixels
    if pil_im.size != (128, 128):
        pil_im = pil_im.resize((128, 128), Image.Resampling.NEAREST)
    return np.array(pil_im, dtype=np.uint8)


def extract_visual_features(image_input: Union[str, bytes, os.PathLike, Image.Image, np.ndarray]) -> np.ndarray:
    """
    Extract a L2-normalized 299-dimensional Spatial-Color CIELAB pyramid vector from an image.
    Strictly ignores transparent pixels (alpha == 0).
    """
    arr = _load_rgba_for_vision(image_input)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]

    # Strictly ignore alpha == 0 pixels
    mask = alpha > 0
    if not np.any(mask):
        return np.zeros(FEATURE_DIM, dtype=np.float32)

    # Convert RGB -> CIELAB (L* in [0, 100], a* in [-128, 127], b* in [-128, 127])
    lab = rgb_to_cielab(rgb)
    # Shift L, a, b to [0, 256) range for uniform histogram binning
    lab_scaled = np.empty_like(lab, dtype=np.float64)
    lab_scaled[..., 0] = np.clip(lab[..., 0] * (255.0 / 100.0), 0.0, 255.999)
    lab_scaled[..., 1] = np.clip(lab[..., 1] + 128.0, 0.0, 255.999)
    lab_scaled[..., 2] = np.clip(lab[..., 2] + 128.0, 0.0, 255.999)

    lab_valid = lab_scaled[mask]
    if len(lab_valid) == 0:
        return np.zeros(FEATURE_DIM, dtype=np.float32)

    features = []

    # 1. Global CIELAB histogram: 8 * 4 * 4 = 128 bins
    hist, _ = np.histogramdd(
        lab_valid,
        bins=(8, 4, 4),
        range=[(0.0, 256.0), (0.0, 256.0), (0.0, 256.0)],
    )
    global_hist = np.zeros(128, dtype=np.float64)
    np.divide(hist.flatten(), float(len(lab_valid)), out=global_hist, where=len(lab_valid) > 0)
    features.append(global_hist)

    # 2. Vertical 3-Zone Spatial Color Pyramid (Head 0..42, Torso 42..85, Legs 85..128)
    # Each zone: 6 * 3 * 3 = 54 histogram bins + 3 mean LAB values = 57 features * 3 = 171 features
    zones = (
        (0, 42),
        (42, 85),
        (85, 128),
    )

    for y0, y1 in zones:
        zone_mask = mask[y0:y1, :]
        zone_lab = lab_scaled[y0:y1, :][zone_mask]
        if len(zone_lab) > 0:
            zh, _ = np.histogramdd(
                zone_lab,
                bins=(6, 3, 3),
                range=[(0.0, 256.0), (0.0, 256.0), (0.0, 256.0)],
            )
            z_hist = np.zeros(54, dtype=np.float64)
            np.divide(zh.flatten(), float(len(zone_lab)), out=z_hist, where=len(zone_lab) > 0)
            features.append(z_hist)

            mean_lab = np.mean(zone_lab, axis=0) / 255.0
            features.append(mean_lab)
        else:
            features.append(np.zeros(54, dtype=np.float64))
            features.append(np.zeros(3, dtype=np.float64))

    feat_vec = np.concatenate(features).astype(np.float32)
    assert feat_vec.shape == (FEATURE_DIM,), f"Expected {FEATURE_DIM} features, got {feat_vec.shape}"

    norm = float(np.linalg.norm(feat_vec))
    if norm > 1e-7:
        feat_vec = feat_vec / norm

    return feat_vec


def pack_feature_blob(vec: np.ndarray) -> bytes:
    """Serialize a 299-dim feature vector into a compact float16 BLOB (598 bytes)."""
    arr = np.asarray(vec, dtype=np.float16).flatten()
    if len(arr) != FEATURE_DIM:
        padded = np.zeros(FEATURE_DIM, dtype=np.float16)
        padded[: min(len(arr), FEATURE_DIM)] = arr[:FEATURE_DIM]
        arr = padded
    return arr.tobytes()


def unpack_feature_blob(blob: bytes) -> np.ndarray:
    """Deserialize a float16 BLOB back into a L2-normalized float32 299-dim vector."""
    if not blob:
        return np.zeros(FEATURE_DIM, dtype=np.float32)
    vec = np.frombuffer(blob, dtype=np.float16).astype(np.float32)
    if len(vec) != FEATURE_DIM:
        return np.zeros(FEATURE_DIM, dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    if norm > 1e-7:
        vec = vec / norm
    return vec


def compute_visual_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Compute cosine similarity between two 299-dim feature vectors mapped to [0.0, 1.0]."""
    if len(vec1) != len(vec2) or len(vec1) == 0:
        return 0.0
    sim = float(np.dot(vec1.astype(np.float32), vec2.astype(np.float32)))
    return max(0.0, min(1.0, (sim + 1.0) / 2.0))
