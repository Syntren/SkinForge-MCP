"""
3D Seam & Edge Continuity Subsystem for SkinForge.
Audits and automatically heals 3D wrap-around seams across adjacent cube faces in Minecraft skins.
Eliminates noticeable texture tears and misalignments along cube folds in 3D space.
"""

from typing import List, Dict, Any, Tuple
import numpy as np
from .ascii_codec import rgba_to_hex


# Standard Minecraft 3D edge connectivity matrix
# format: (part_a, slice_a, part_b, slice_b, flip_b, description)
SEAM_PAIRS = [
    # Head vertical ring (front -> left -> back -> right -> front)
    ("head_front", ("slice", slice(None), 7), "head_left", ("slice", slice(None), 0), False, "Head Front-Right <-> Left-Face"),
    ("head_left",  ("slice", slice(None), 7), "head_back", ("slice", slice(None), 0), False, "Head Left-Face <-> Back-Face"),
    ("head_back",  ("slice", slice(None), 7), "head_right", ("slice", slice(None), 0), False, "Head Back-Face <-> Right-Face"),
    ("head_right", ("slice", slice(None), 7), "head_front", ("slice", slice(None), 0), False, "Head Right-Face <-> Front-Face"),

    # Head top crown connections
    ("head_top",   ("slice", 7, slice(None)), "head_front", ("slice", 0, slice(None)), False, "Head Top-Crown <-> Front-Forehead"),
    ("head_top",   ("slice", 0, slice(None)), "head_back",  ("slice", 0, slice(None)), True,  "Head Top-Crown <-> Back-Nape"),
    ("head_top",   ("slice", slice(None), 0), "head_right", ("slice", 0, slice(None)), False, "Head Top-Crown <-> Right-Side"),
    ("head_top",   ("slice", slice(None), 7), "head_left",  ("slice", 0, slice(None)), True,  "Head Top-Crown <-> Left-Side"),

    # Torso vertical ring
    ("body_front", ("slice", slice(None), 7), "body_left",  ("slice", slice(None), 0), False, "Torso Front-Right <-> Left-Flank"),
    ("body_left",  ("slice", slice(None), 3), "body_back",  ("slice", slice(None), 0), False, "Torso Left-Flank <-> Back-Fabric"),
    ("body_back",  ("slice", slice(None), 7), "body_right", ("slice", slice(None), 0), False, "Torso Back-Fabric <-> Right-Flank"),
    ("body_right", ("slice", slice(None), 3), "body_front", ("slice", slice(None), 0), False, "Torso Right-Flank <-> Front-Chest"),
    ("body_top",   ("slice", 3, slice(None)), "body_front", ("slice", 0, slice(None)), False, "Torso Shoulder-Top <-> Chest-Upper"),

    # Jacket outer layer ring
    ("jacket_front", ("slice", slice(None), 7), "jacket_left",  ("slice", slice(None), 0), False, "Jacket Front-Right <-> Left-Flank"),
    ("jacket_left",  ("slice", slice(None), 3), "jacket_back",  ("slice", slice(None), 0), False, "Jacket Left-Flank <-> Back-Emblem"),
    ("jacket_back",  ("slice", slice(None), 7), "jacket_right", ("slice", slice(None), 0), False, "Jacket Back-Emblem <-> Right-Flank"),
    ("jacket_right", ("slice", slice(None), 3), "jacket_front", ("slice", slice(None), 0), False, "Jacket Right-Flank <-> Front-Chest"),
]


def _extract_edge(part_arr: np.ndarray, spec: Tuple) -> np.ndarray:
    """Extract a 1D slice of pixels from a 2D part array."""
    _, s0, s1 = spec
    return part_arr[s0, s1]


def _set_edge(part_arr: np.ndarray, spec: Tuple, values: np.ndarray):
    """Assign values to a 1D slice of pixels on a 2D part array."""
    _, s0, s1 = spec
    part_arr[s0, s1] = values


def check_seams(canvas, tolerance: int = 35) -> List[Dict[str, Any]]:
    """
    Scan adjacent cube faces and identify 3D texture mismatches along folded edges.
    Args:
        canvas: SkinCanvas instance.
        tolerance: Euclidean RGB distance threshold for flag mismatch.
    Returns:
        List of detected seam discrepancies with coordinates, colors, and descriptions.
    """
    discrepancies = []

    for part_a, spec_a, part_b, spec_b, flip_b, desc in SEAM_PAIRS:
        if part_a not in canvas.parts or part_b not in canvas.parts:
            continue

        edge_a = _extract_edge(canvas.parts[part_a], spec_a)
        edge_b = _extract_edge(canvas.parts[part_b], spec_b)
        if flip_b:
            edge_b = edge_b[::-1]

        # Ignore transparent-to-transparent edges on Layer 2
        min_len = min(len(edge_a), len(edge_b))
        mismatched_indices = []

        for i in range(min_len):
            px_a = edge_a[i]
            px_b = edge_b[i]

            # Both transparent is fine
            if px_a[3] == 0 and px_b[3] == 0:
                continue

            dist = np.sqrt(np.sum((px_a[:3].astype(float) - px_b[:3].astype(float))**2))
            if dist > tolerance:
                mismatched_indices.append({
                    "index": i,
                    "color_a": rgba_to_hex(px_a.tolist()),
                    "color_b": rgba_to_hex(px_b.tolist()),
                    "color_distance": round(float(dist), 1)
                })

        if mismatched_indices:
            discrepancies.append({
                "seam_name": desc,
                "part_a": part_a,
                "part_b": part_b,
                "mismatch_count": len(mismatched_indices),
                "mismatches": mismatched_indices
            })

    return discrepancies


def align_seams(canvas, seam_name: str = "all", mode: str = "blend") -> int:
    """
    Automatically harmonize and smooth colors along adjacent 3D cube edges.
    Args:
        canvas: SkinCanvas instance.
        seam_name: Specific seam description substring or 'all'.
        mode: 'blend' (average color of A and B) or 'copy_a_to_b'.
    Returns:
        Total number of pixels smoothed.
    """
    total_aligned = 0

    for part_a, spec_a, part_b, spec_b, flip_b, desc in SEAM_PAIRS:
        if seam_name != "all" and seam_name.lower() not in desc.lower():
            continue
        if part_a not in canvas.parts or part_b not in canvas.parts:
            continue

        p_a = canvas.parts[part_a]
        p_b = canvas.parts[part_b]
        edge_a = _extract_edge(p_a, spec_a)
        edge_b = _extract_edge(p_b, spec_b)

        min_len = min(len(edge_a), len(edge_b))
        for i in range(min_len):
            idx_b = (min_len - 1 - i) if flip_b else i
            px_a = edge_a[i].astype(float)
            px_b = edge_b[idx_b].astype(float)

            if px_a[3] == 0 and px_b[3] == 0:
                continue

            if mode == "copy_a_to_b":
                edge_b[idx_b] = edge_a[i]
                total_aligned += 1
            else:
                # Average blend
                avg = np.round((px_a + px_b) / 2.0).astype(np.uint8)
                edge_a[i] = avg
                edge_b[idx_b] = avg
                total_aligned += 1

        _set_edge(p_a, spec_a, edge_a)
        if flip_b:
            edge_b = edge_b[::-1]
        _set_edge(p_b, spec_b, edge_b)

    return total_aligned
