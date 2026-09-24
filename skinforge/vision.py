"""
SkinForge Vision - Computer Vision Feature Extraction & Concept Image Search.

Enables searching Minecraft skins by reference concept art, photos, or character illustrations
using spatial-color pyramid representations in LAB color space (OpenCV + NumPy).
"""

from typing import Union, Optional, List, Dict, Any, Tuple
import os
import io
import cv2
import numpy as np
from PIL import Image


def extract_visual_features(image_input: Union[str, Image.Image, np.ndarray]) -> np.ndarray:
    """
    Extract a normalized 178-dimensional Spatial-Color LAB feature vector from an image.
    Robust to scale, character pose, and transparent backgrounds.
    """
    if isinstance(image_input, (str, bytes, os.PathLike)) or hasattr(image_input, "read"):
        pil_im = Image.open(image_input).convert("RGBA")
    elif isinstance(image_input, Image.Image):
        pil_im = image_input.convert("RGBA")
    elif isinstance(image_input, np.ndarray):
        if image_input.shape[-1] == 4:
            pil_im = Image.fromarray(image_input, "RGBA")
        else:
            pil_im = Image.fromarray(image_input, "RGB").convert("RGBA")
    else:
        raise ValueError(f"Unsupported image input type: {type(image_input)}")

    # Resize to standard analysis size (128x128)
    pil_im = pil_im.resize((128, 128), Image.Resampling.BILINEAR)
    arr = np.array(pil_im)

    # Separate RGB and Alpha
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]

    # Convert to LAB color space (perceptually uniform)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)

    # Consider only non-transparent pixels if alpha mask is informative
    mask = alpha > 30
    if np.sum(mask) < 200:
        mask = np.ones((128, 128), dtype=bool)

    lab_valid = lab[mask]
    if len(lab_valid) == 0:
        return np.zeros(178, dtype=np.float32)

    features = []

    # 1. Global LAB histogram (8 bins L, 4 bins A, 4 bins B = 64 bins)
    hist, _ = np.histogramdd(
        lab_valid,
        bins=(8, 4, 4),
        range=[(0, 256), (0, 256), (0, 256)]
    )
    features.append(hist.flatten() / max(1, len(lab_valid)))

    # 2. Vertical 3-Zone Spatial Color Distribution (Head 0-42, Torso 42-85, Legs 85-128)
    zones = [
        (0, 42),    # Head
        (42, 85),   # Torso / Upper body
        (85, 128)   # Legs / Lower body
    ]

    for y0, y1 in zones:
        zone_mask = mask[y0:y1, :]
        zone_lab = lab[y0:y1, :][zone_mask]
        if len(zone_lab) > 10:
            zh, _ = np.histogramdd(
                zone_lab,
                bins=(6, 3, 3),  # 54 bins per zone * 2 zones = 108 bins
                range=[(0, 256), (0, 256), (0, 256)]
            )
            features.append(zh.flatten() / max(1, len(zone_lab)))
            # Mean and std dev for this zone
            mean_lab = np.mean(zone_lab, axis=0) / 255.0
            features.append(mean_lab)  # 3 features
        else:
            features.append(np.zeros(54, dtype=np.float32))
            features.append(np.zeros(3, dtype=np.float32))

    # Combine into single 1D feature vector
    feat_vec = np.concatenate(features).astype(np.float32)

    # L2 normalize
    norm = np.linalg.norm(feat_vec)
    if norm > 1e-7:
        feat_vec /= norm

    return feat_vec


def compute_visual_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Compute cosine similarity between two visual feature vectors (0.0 to 1.0)."""
    if len(vec1) != len(vec2):
        return 0.0
    sim = float(np.dot(vec1, vec2))
    return max(0.0, min(1.0, (sim + 1.0) / 2.0))
