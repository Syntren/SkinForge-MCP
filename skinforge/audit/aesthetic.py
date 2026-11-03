"""
Aesthetic Engine v2 & 4 Golden Rules Evaluator for SkinForge (v1.3.0).

Evaluates 6 quantitative dimensions of pixel-art craftsmanship:
  1. 3D Relief Depth (relief_3d)
  2. Palette Harmony & Entropy (palette_harmony)
  3. Shading Depth & Dynamic Range (shading_depth)
  4. Spatial Cluster Coherence (spatial_coherence)
  5. Vectorized Hue Shifting (hue_shifting)
  6. Seam Continuity (seam_continuity)
Plus full verification of the 4 Golden Rules of Minecraft Skin Depth.
Strictly ignores transparent pixels (alpha == 0) in all color calculations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from ..color.spaces import extract_opaque_rgb, rgb_to_hsv
from ..core.uv import (
    BASE_PARTS,
    OUTER_PARTS,
    get_uv_map,
    load_skin_array,
)


def detect_pillow_shading(face_arr: np.ndarray) -> bool:
    """
    Detect beginner 'pillow shading' on a cuboid face where all 4 outer perimeter edges
    are shaded noticeably darker than the inner core.
    Strictly ignores transparent pixels (alpha == 0) if a 4-channel RGBA array is provided.
    """
    arr = np.asarray(face_arr)
    H, W = arr.shape[:2]
    if H < 4 or W < 4:
        return False

    if arr.ndim == 3 and arr.shape[2] >= 4:
        if np.any(arr[:, :, 3] == 0):
            return False
        rgb = arr[:, :, :3]
    else:
        rgb = arr[:, :, :3]

    rgb_f = np.clip(rgb.astype(np.float64), 0.0, 255.0) / 255.0
    v = np.max(rgb_f, axis=-1)

    mask_perimeter = np.zeros((H, W), dtype=bool)
    mask_perimeter[0, :] = True
    mask_perimeter[-1, :] = True
    mask_perimeter[:, 0] = True
    mask_perimeter[:, -1] = True

    mask_center = ~mask_perimeter
    v_peri = float(np.mean(v[mask_perimeter]))
    v_cent = float(np.mean(v[mask_center]))

    top_darker = float(np.mean(v[0, :])) < v_cent - 0.15
    bot_darker = float(np.mean(v[-1, :])) < v_cent - 0.15
    left_darker = float(np.mean(v[:, 0])) < v_cent - 0.15
    right_darker = float(np.mean(v[:, -1])) < v_cent - 0.15

    return bool(top_darker and bot_darker and left_darker and right_darker and (v_cent - v_peri > 0.20))


def evaluate_golden_rules(arr: np.ndarray, model: str = "default") -> Dict[str, Any]:
    """
    Evaluate all 4 Golden Rules of Minecraft Skin Depth on a 64x64 RGBA array.
    Returns structured status for each rule and aggregate compliance flag.
    """
    uv_map = get_uv_map(model)

    # Rule 1: Zero Holes on Base Layer (36 parts must have alpha == 255)
    holes_by_part: Dict[str, int] = {}
    base_total = 0
    base_opaque = 0
    for name in BASE_PARTS:
        u0, v0, u1, v1 = uv_map[name]
        crop = arr[v0:v1, u0:u1]
        total_px = crop.shape[0] * crop.shape[1]
        opaque_px = int(np.sum(crop[:, :, 3] == 255))
        holes = total_px - opaque_px
        base_total += total_px
        base_opaque += opaque_px
        if holes > 0:
            holes_by_part[name] = holes
    total_holes = sum(holes_by_part.values())
    rule1_passed = total_holes == 0

    # Rule 2: Layer 2 is +0.35 3D Relief (not bloated > 65%)
    l2_pixels = 0
    l2_total = 0
    for name in OUTER_PARTS:
        u0, v0, u1, v1 = uv_map[name]
        crop = arr[v0:v1, u0:u1]
        l2_total += crop.shape[0] * crop.shape[1]
        l2_pixels += int(np.sum(crop[:, :, 3] > 0))
    l2_ratio = l2_pixels / max(1, l2_total)
    rule2_passed = l2_ratio <= 0.65

    # Rule 3: hat_front rows 4..7 MUST be 100% transparent
    u0, v0, u1, v1 = uv_map["hat_front"]
    hat_f = arr[v0:v1, u0:u1]
    hat_f_violating_rows: Dict[int, int] = {}
    for r in range(4, min(8, hat_f.shape[0])):
        cnt = int(np.sum(hat_f[r, :, 3] > 0))
        if cnt > 0:
            hat_f_violating_rows[r] = cnt
    hat_f_bad_pixels = sum(hat_f_violating_rows.values())
    rule3_passed = hat_f_bad_pixels == 0

    # Rule 4: hat_top must not have isolated floating crown planks (0 < pixels < 20)
    u0, v0, u1, v1 = uv_map["hat_top"]
    hat_t = arr[v0:v1, u0:u1]
    hat_t_pixels = int(np.sum(hat_t[:, :, 3] > 0))
    rule4_passed = not (0 < hat_t_pixels < 20)

    return {
        "all_passed": bool(rule1_passed and rule2_passed and rule3_passed and rule4_passed),
        "rule1_zero_holes": {
            "passed": rule1_passed,
            "holes": total_holes,
            "holes_by_part": holes_by_part,
            "base_opacity_pct": round((base_opaque / max(1, base_total)) * 100.0, 1),
            "label": "Rule 1: Zero Holes (Base 100% Solid)",
        },
        "rule2_relief_depth": {
            "passed": rule2_passed,
            "layer2_ratio": round(l2_ratio, 3),
            "layer2_pct": round(l2_ratio * 100.0, 1),
            "optimal": bool(0.12 <= l2_ratio <= 0.45),
            "label": "Rule 2: +0.35 3D Relief Layer",
        },
        "rule3_hat_front": {
            "passed": rule3_passed,
            "violating_pixels": hat_f_bad_pixels,
            "violating_rows": hat_f_violating_rows,
            "label": "Rule 3: hat_front Rows 4-7 Transparent",
        },
        "rule4_hat_top": {
            "passed": rule4_passed,
            "hat_top_pixels": hat_t_pixels,
            "label": "Rule 4: hat_top No Floating Planks",
        },
    }


def _extract_canvas_array(canvas_or_arr: Any, model: Optional[str] = None) -> Tuple[np.ndarray, str]:
    if hasattr(canvas_or_arr, "arr"):
        arr = np.asarray(canvas_or_arr.arr, dtype=np.uint8)
        if model is None:
            model = getattr(canvas_or_arr, "model", "default")
    elif hasattr(canvas_or_arr, "to_array"):
        arr = canvas_or_arr.to_array()
        if model is None:
            model = getattr(canvas_or_arr, "model", "default")
    elif hasattr(canvas_or_arr, "get_part"):
        model = getattr(canvas_or_arr, "model", "default") if model is None else model
        uv_map = get_uv_map(model)
        arr = np.zeros((64, 64, 4), dtype=np.uint8)
        for part_name, (u0, v0, u1, v1) in uv_map.items():
            arr[v0:v1, u0:u1] = canvas_or_arr.get_part(part_name)
    elif isinstance(canvas_or_arr, np.ndarray):
        arr, _ = load_skin_array(canvas_or_arr)
    else:
        arr, _ = load_skin_array(canvas_or_arr)

    return arr, (model or "default")


def compute_aesthetic_score(
    canvas_or_arr: Any,
    model: Optional[str] = None,
    deduct_defects: bool = True
) -> Dict[str, Any]:
    """
    Compute the 6-dimensional Aesthetic Engine v2 score (0.0 to 1.0) and Golden Rules telemetry.
    Strictly ignores transparent pixels (alpha == 0) in all color, shading, coherence, and hue metrics.
    """
    arr, resolved_model = _extract_canvas_array(canvas_or_arr, model=model)
    uv_map = get_uv_map(resolved_model)
    recommendations: List[str] = []
    deductions: List[str] = []

    golden = evaluate_golden_rules(arr, model=resolved_model)

    # 1. 3D Relief Depth (Layer 2 density)
    l2_ratio = float(golden["rule2_relief_depth"]["layer2_ratio"])
    if 0.12 <= l2_ratio <= 0.45:
        score_l2 = 1.0
    elif 0.05 <= l2_ratio < 0.12:
        score_l2 = 0.6 + (l2_ratio - 0.05) * 5.7
    elif 0.45 < l2_ratio <= 0.65:
        score_l2 = 1.0 - (l2_ratio - 0.45) * 2.5
    elif l2_ratio > 0.65:
        score_l2 = 0.35
        recommendations.append("Layer 2 is over-dense (>65% filled); thin out outer layers to avoid bulky armor look.")
    else:
        score_l2 = 0.2
        recommendations.append("Add 3D relief on Layer 2 (hair fringes, jacket cuffs, hood) for 15-40% depth.")

    # 2. Palette Harmony & Entropy (strictly ignoring alpha == 0)
    opaque_rgb = extract_opaque_rgb(arr, min_alpha=1)
    if len(opaque_rgb) > 0:
        unique_colors = int(len(np.unique(opaque_rgb, axis=0)))
    else:
        unique_colors = 0

    if 16 <= unique_colors <= 70:
        score_colors = 1.0
    elif 8 <= unique_colors < 16:
        score_colors = 0.4 + (unique_colors - 8) * 0.075
        recommendations.append("Expand color ramps with more shading steps (aim for 16-60 harmonious colors).")
    elif unique_colors < 8:
        score_colors = 0.15
        recommendations.append("Palette has fewer than 8 colors; replace flat bucket fills with multi-tone shading.")
    elif 70 < unique_colors <= 140:
        score_colors = 1.0 - (unique_colors - 70) * 0.005
    else:
        score_colors = 0.45
        recommendations.append("Palette has too many disjoint colors (>140); consolidate ramps to avoid noisy artifacts.")

    # 3 & 4. Shading Depth & Spatial Cluster Coherence (strictly ignoring alpha == 0)
    std_scores: List[float] = []
    coherence_scores: List[float] = []
    pillow_detected = False
    test_faces = ["head_front", "body_front", "right_arm_front"]

    for test_face in test_faces:
        u0, v0, u1, v1 = uv_map[test_face]
        face_rgba = arr[v0:v1, u0:u1]
        opaque_mask = face_rgba[:, :, 3] > 0
        if not np.any(opaque_mask):
            std_scores.append(0.0)
            coherence_scores.append(0.1)
            continue

        face_valid_rgb = face_rgba[opaque_mask][:, :3].astype(np.float64)
        std_val = float(np.mean(np.std(face_valid_rgb, axis=0)))
        std_scores.append(std_val)

        if face_rgba.shape[0] > 1 and face_rgba.shape[1] > 1:
            face_rgb_f = face_rgba[:, :, :3].astype(np.float64)
            h_pair_mask = opaque_mask[:, 1:] & opaque_mask[:, :-1]
            v_pair_mask = opaque_mask[1:, :] & opaque_mask[:-1, :]

            dh_vals = np.abs(face_rgb_f[:, 1:] - face_rgb_f[:, :-1])
            dv_vals = np.abs(face_rgb_f[1:, :] - face_rgb_f[:-1, :])

            dh = float(np.mean(dh_vals[h_pair_mask])) if np.any(h_pair_mask) else 0.0
            dv = float(np.mean(dv_vals[v_pair_mask])) if np.any(v_pair_mask) else 0.0
            d_local = (dh + dv) * 0.5

            ratio_arr = np.zeros(1, dtype=np.float64)
            np.divide(d_local, std_val, out=ratio_arr, where=std_val > 1e-5)
            ratio = float(ratio_arr[0])

            if std_val < 6.0:
                c_score = max(0.1, std_val / 6.0)
            elif ratio > 0.95 and std_val > 25.0:
                c_score = max(0.2, 1.0 - (ratio - 0.95) * 2.0)
            elif 0.20 <= ratio <= 0.75:
                c_score = 1.0
            else:
                c_score = 0.8
        else:
            c_score = 0.5
        coherence_scores.append(c_score)

        if not pillow_detected and detect_pillow_shading(face_rgba):
            pillow_detected = True

    mean_std = float(np.mean(std_scores)) if std_scores else 0.0
    if 12.0 <= mean_std <= 85.0:
        score_shading = 1.0
    elif mean_std < 12.0:
        score_shading = max(0.1, mean_std / 12.0)
    else:
        score_shading = max(0.6, 1.0 - (mean_std - 85.0) * 0.01)

    score_coherence = float(np.mean(coherence_scores)) if coherence_scores else 0.1

    if pillow_detected:
        recommendations.append("Avoid pillow shading: shade with directional light and form clusters rather than darkening all perimeter edges.")

    # 5. Vectorized Hue Shifting (strictly ignoring alpha == 0)
    hue_scores: List[float] = []
    for face in ["head_front", "body_front"]:
        u0, v0, u1, v1 = uv_map[face]
        crop_rgba = arr[v0:v1, u0:u1]
        valid_px = crop_rgba[crop_rgba[:, :, 3] > 0][:, :3]
        if len(valid_px) < 8:
            hue_scores.append(0.5)
            continue

        hsv = rgb_to_hsv(valid_px)
        h_norm = hsv[:, 0] / 360.0
        s = hsv[:, 1]
        v = hsv[:, 2]

        sat_mask = s > 0.12
        if int(np.sum(sat_mask)) >= 8:
            med_v = float(np.median(v[sat_mask]))
            sh_h = h_norm[sat_mask & (v < med_v)]
            hi_h = h_norm[sat_mask & (v >= med_v)]
            if len(sh_h) >= 3 and len(hi_h) >= 3:
                std_sh = float(np.std(sh_h)) * 360.0
                h_diff = float(np.abs(np.mean(hi_h) - np.mean(sh_h)))
                circ_deg = min(h_diff, 1.0 - h_diff) * 360.0
                if std_sh > 65.0:
                    hue_scores.append(0.4)
                elif 8.0 <= circ_deg <= 75.0:
                    hue_scores.append(1.0)
                elif circ_deg > 75.0:
                    hue_scores.append(0.85)
                elif 3.0 <= circ_deg < 8.0:
                    hue_scores.append(0.7)
                else:
                    hue_scores.append(0.5)
            else:
                hue_scores.append(0.6)
        else:
            hue_scores.append(0.5)

    score_hue = float(np.mean(hue_scores)) if hue_scores else 0.5
    if score_hue < 0.65:
        recommendations.append("Apply hue shifting: shift shadows toward cooler hues (blue/purple) and highlights toward warm hues (gold/cyan).")

    # 6. Seam Continuity (strictly ignoring alpha == 0)
    def seam_diff(p1: str, p2: str, e1: int, e2: int) -> float:
        u0_a, v0_a, u1_a, v1_a = uv_map[p1]
        u0_b, v0_b, u1_b, v1_b = uv_map[p2]
        c1 = arr[v0_a:v1_a, u0_a:u1_a]
        c2 = arr[v0_b:v1_b, u0_b:u1_b]
        edge1 = c1[:, e1]
        edge2 = c2[:, e2]
        valid = (edge1[:, 3] > 0) & (edge2[:, 3] > 0)
        if not np.any(valid):
            return 0.0
        return float(np.mean(np.abs(edge1[valid, :3].astype(np.float64) - edge2[valid, :3].astype(np.float64))))

    d_hr = seam_diff("head_front", "head_right", 0, -1)
    d_hl = seam_diff("head_front", "head_left", -1, 0)
    max_seam = max(d_hr, d_hl)
    if max_seam <= 20.0:
        score_seams = 1.0
    elif max_seam <= 45.0:
        score_seams = 0.85
    else:
        score_seams = max(0.2, 1.0 - (max_seam - 45.0) * 0.015)
        recommendations.append(f"Seam color jump detected (delta = {max_seam:.1f}); use skin_align_seams() to blend.")

    base_score = float(
        0.25 * score_l2
        + 0.20 * score_colors
        + 0.20 * score_shading
        + 0.15 * score_coherence
        + 0.10 * score_hue
        + 0.10 * score_seams
    )

    penalty_points = 0.0
    if deduct_defects:
        base_pixels_total = sum((uv_map[bp][2] - uv_map[bp][0]) * (uv_map[bp][3] - uv_map[bp][1]) for bp in BASE_PARTS)
        holes = int(golden["rule1_zero_holes"]["holes"])
        base_opaque_total = base_pixels_total - holes
        if base_opaque_total > 0.5 * base_pixels_total and holes > 0:
            p = min(0.20, 0.05 + holes * 0.01)
            penalty_points += p
            deductions.append(f"-{p:.2f}: {holes} base layer non-opaque holes (Rule 1)")

        f_rows = len(golden["rule3_hat_front"]["violating_rows"])
        if f_rows > 0:
            p = f_rows * 0.04
            penalty_points += p
            deductions.append(f"-{p:.2f}: {f_rows} floating lower rows on hat_front rows 4-7 (Rule 3)")

        if not golden["rule4_hat_top"]["passed"]:
            hat_t_count = int(golden["rule4_hat_top"]["hat_top_pixels"])
            p = 0.06
            penalty_points += p
            deductions.append(f"-{p:.2f}: Isolated floating plank ({hat_t_count} px) on hat_top (Rule 4)")

        if pillow_detected:
            p = 0.05
            penalty_points += p
            deductions.append(f"-{p:.2f}: Pillow shading detected on face/body")

    final_score = max(0.0, min(1.0, base_score - penalty_points))
    final_score = round(final_score, 3)

    return {
        "score": final_score,
        "base_score": round(base_score, 3),
        "tier": "top_tier" if final_score >= 0.78 else "high" if final_score >= 0.62 else "medium" if final_score >= 0.42 else "low",
        "layer2_ratio": round(l2_ratio, 3),
        "unique_colors": unique_colors,
        "shading_variance": round(mean_std, 1),
        "metrics": {
            "relief_3d": round(score_l2, 3),
            "palette_harmony": round(score_colors, 3),
            "shading_depth": round(score_shading, 3),
            "spatial_coherence": round(score_coherence, 3),
            "hue_shifting": round(score_hue, 3),
            "seam_continuity": round(score_seams, 3),
        },
        "golden_rules": golden,
        "deductions": deductions,
        "recommendations": recommendations,
    }
