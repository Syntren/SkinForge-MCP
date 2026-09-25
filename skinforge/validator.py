"""
Validator and quality audit subsystem for SkinForge.
Detects holes in Layer 1, floating cardboard planes on Layer 2, edge seam alignment issues,
and evaluates multi-dimensional craftsmanship aesthetics (0.0 to 1.0) using:
  1. Layer 2 3D relief density & distribution
  2. Palette harmony, color ramp depth, and entropy
  3. Shading dynamic range & contrast
  4. Spatial cluster coherence (anti-noise / anti-confetti)
  5. Artistic hue shifting (temperature ramps across luminance)
  6. Seam continuity across cuboid transitions
  7. Pillow shading detection & anatomical defect deductions
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from PIL import Image
from .canvas import MINECRAFT_UV_MAP, SkinCanvas, get_uv_map


def detect_pillow_shading(face_rgb: np.ndarray) -> bool:
    """
    Detects classic beginner 'pillow shading' on a cuboid face where every outer perimeter
    pixel is shaded darker than the center, creating an artificial rounded cushion effect
    instead of directional lighting or form clusters.
    """
    H, W = face_rgb.shape[:2]
    if H < 4 or W < 4:
        return False
    v = np.max(face_rgb.astype(float) / 255.0, axis=-1)

    mask_perimeter = np.zeros((H, W), dtype=bool)
    mask_perimeter[0, :] = True
    mask_perimeter[-1, :] = True
    mask_perimeter[:, 0] = True
    mask_perimeter[:, -1] = True

    mask_center = ~mask_perimeter
    v_peri = np.mean(v[mask_perimeter])
    v_cent = np.mean(v[mask_center])

    top_darker = np.mean(v[0, :]) < v_cent - 0.15
    bot_darker = np.mean(v[-1, :]) < v_cent - 0.15
    left_darker = np.mean(v[:, 0]) < v_cent - 0.15
    right_darker = np.mean(v[:, -1]) < v_cent - 0.15

    return bool(top_darker and bot_darker and left_darker and right_darker and (v_cent - v_peri > 0.20))


class SkinValidator:
    def __init__(self, skin_source, model=None):
        self.source_desc = "in-memory canvas"
        self.model = model
        if isinstance(skin_source, str):
            self.source_desc = skin_source
            self.im = Image.open(skin_source).convert("RGBA")
            self.arr = np.array(self.im)
            if self.model is None and self.arr.shape[0] >= 64 and self.arr.shape[1] >= 56:
                r_unused = np.max(self.arr[20:32, 54:56, 3])
                l_unused = np.max(self.arr[52:64, 46:48, 3])
                if r_unused == 0 and l_unused == 0:
                    self.model = "slim"
        elif isinstance(skin_source, SkinCanvas):
            self.model = skin_source.model
            self.arr = skin_source.to_array()
            self.im = Image.fromarray(self.arr)
        elif isinstance(skin_source, Image.Image):
            self.im = skin_source.convert("RGBA")
            self.arr = np.array(self.im)
            if self.model is None and self.arr.shape[0] >= 64 and self.arr.shape[1] >= 56:
                r_unused = np.max(self.arr[20:32, 54:56, 3])
                l_unused = np.max(self.arr[52:64, 46:48, 3])
                if r_unused == 0 and l_unused == 0:
                    self.model = "slim"
        elif isinstance(skin_source, np.ndarray):
            self.arr = skin_source.copy()
            self.im = Image.fromarray(self.arr)
        else:
            raise TypeError(f"Unsupported skin source type: {type(skin_source)}")

        if not self.model:
            self.model = "default"

        self.issues = []
        self.warnings = []
        self.layer1_holes = {}
        self.layer2_violations = []
        self.seam_issues = []

    def validate(self):
        """Run all validation checks and return (is_valid, report_str)."""
        res = self.validate_structured()
        return res["valid"], res["report"]

    def validate_structured(self):
        """
        Run all validation checks and return structured diagnostic dictionary.
        """
        self.issues.clear()
        self.warnings.clear()
        self.layer1_holes.clear()
        self.layer2_violations.clear()
        self.seam_issues.clear()

        self._check_dimensions()
        self._check_base_layer_holes()
        self._check_outer_layer_floating_planes()
        self._check_seams()

        # Compute deep craftsmanship aesthetics
        aesthetic = compute_aesthetic_score(self.arr, model=self.model, deduct_defects=True)

        report = []
        report.append(f"=== SkinForge Quality Audit for '{self.source_desc}' ===")
        report.append(f"Dimensions: {self.im.size[0]}x{self.im.size[1]} | Mode: {self.im.mode} | Model: {self.model}")

        if not self.issues:
            report.append("\n[PASS] No critical errors found.")
        else:
            report.append(f"\n[FAIL] Found {len(self.issues)} critical issues:")
            for issue in self.issues:
                report.append(f"  - ERROR: {issue}")

        if self.warnings:
            report.append(f"\n[WARNINGS] ({len(self.warnings)} items):")
            for w in self.warnings:
                report.append(f"  - {w}")
        else:
            report.append("\n[PASS] Zero visual warnings.")

        # Craftsmanship Scoreboard
        report.append("\n=== Craftsmanship & Aesthetic Analysis ===")
        report.append(f"Overall Aesthetic Score: {aesthetic['score']:.2f} / 1.0 [{aesthetic['tier'].upper()}]")
        report.append("Radar Sub-Metrics:")
        m = aesthetic["metrics"]
        report.append(f"  - 3D Relief Depth:       {int(m['relief_3d']*100)}% ({aesthetic['layer2_ratio']*100:.1f}% Layer 2)")
        report.append(f"  - Palette Harmony:       {int(m['palette_harmony']*100)}% ({aesthetic['unique_colors']} unique colors)")
        report.append(f"  - Shading Depth:         {int(m['shading_depth']*100)}% (variance: {aesthetic['shading_variance']})")
        report.append(f"  - Spatial Coherence:     {int(m['spatial_coherence']*100)}% (anti-noise cluster density)")
        report.append(f"  - Hue-Shift Dynamics:    {int(m['hue_shifting']*100)}% (temperature modulation)")
        report.append(f"  - Seam Continuity:       {int(m['seam_continuity']*100)}% (edge alignment)")

        if aesthetic["deductions"]:
            report.append("\nAesthetic Deductions:")
            for d in aesthetic["deductions"]:
                report.append(f"  - {d}")

        suggestions = []
        if self.layer1_holes:
            total_holes = sum(self.layer1_holes.values())
            suggestions.append(f"Call 'skin_auto_fix()' to fill {total_holes} non-opaque pixels on Layer 1 (Rule 1).")
        if self.layer2_violations:
            suggestions.append("Call 'skin_auto_fix()' to strip illegal floating cardboard planes on hat_front and hat_top (Rules 3 & 4).")
        if self.seam_issues:
            suggestions.append("Align colors across head front/right/left seams to eliminate visible border lines.")

        for rec in aesthetic["recommendations"]:
            if rec not in suggestions:
                suggestions.append(rec)

        if suggestions:
            report.append("\nCraftsmanship Recommendations:")
            for s in suggestions:
                report.append(f"  -> {s}")

        return {
            "valid": len(self.issues) == 0,
            "dimensions": [self.im.size[0], self.im.size[1]],
            "issues": list(self.issues),
            "warnings": list(self.warnings),
            "layer1_holes": dict(self.layer1_holes),
            "layer2_violations": list(self.layer2_violations),
            "seam_issues": list(self.seam_issues),
            "suggestions": suggestions,
            "aesthetic_score": aesthetic["score"],
            "aesthetic_tier": aesthetic["tier"],
            "craftsmanship_metrics": aesthetic["metrics"],
            "deductions": aesthetic["deductions"],
            "recommendations": aesthetic["recommendations"],
            "report": "\n".join(report),
        }

    def _check_dimensions(self):
        if self.im.size != (64, 64):
            self.issues.append(f"Image dimensions must be 64x64, found {self.im.size}")

    def _check_base_layer_holes(self):
        uv_map = get_uv_map(self.model)
        base_parts = [k for k in uv_map.keys() if not any(x in k for x in ['hat', 'jacket', 'sleeve', 'pants'])]
        for name in base_parts:
            u0, v0, u1, v1 = uv_map[name]
            crop = self.arr[v0:v1, u0:u1]
            holes = int(np.sum(crop[:, :, 3] < 255))
            if holes > 0:
                self.warnings.append(f"Base part '{name}' has {holes} non-opaque pixels (Rule 1).")
                self.layer1_holes[name] = holes

    def _check_outer_layer_floating_planes(self):
        uv_map = get_uv_map(self.model)
        # 1. Check hat_front lower rows (below brow line, rows 5..7)
        u0, v0, u1, v1 = uv_map["hat_front"]
        hat_f = self.arr[v0:v1, u0:u1]
        for r in range(5, 8):
            row_alpha = hat_f[r, :, 3] > 0
            if np.any(row_alpha):
                msg = f"hat_front row {r} has {int(np.sum(row_alpha))}/8 non-transparent pixels (Rule 3: floating cardboard in profile)."
                self.warnings.append(msg)
                self.layer2_violations.append(msg)

        # 2. Check hat_top for isolated floating lines
        u0, v0, u1, v1 = uv_map["hat_top"]
        hat_t = self.arr[v0:v1, u0:u1]
        t_alpha = hat_t[:, :, 3] > 0
        pixel_count = int(np.sum(t_alpha))
        if 0 < pixel_count < 20:
            msg = f"hat_top has only {pixel_count} pixels (Rule 4: floating detached plank over crown)."
            self.warnings.append(msg)
            self.layer2_violations.append(msg)

        # 3. Check pants front for giant white blocks
        u0, v0, u1, v1 = uv_map["left_pants_front"]
        p_crop = self.arr[v0:v1, u0:u1]
        bright_white_count = int(np.sum((p_crop[:, :, 0] > 240) & (p_crop[:, :, 1] > 240) & (p_crop[:, :, 2] > 240) & (p_crop[:, :, 3] > 0)))
        if bright_white_count > 6:
            self.warnings.append(f"left_pants_front has {bright_white_count} solid white pixels on Layer 2.")

    def _check_seams(self):
        uv_map = get_uv_map(self.model)
        u0_f, v0_f, u1_f, v1_f = uv_map["head_front"]
        u0_r, v0_r, u1_r, v1_r = uv_map["head_right"]

        edge_r = self.arr[v0_r:v1_r, u1_r - 1, :3]
        edge_f = self.arr[v0_f:v1_f, u0_f, :3]
        diff = float(np.mean(np.abs(edge_r.astype(int) - edge_f.astype(int))))
        if diff > 50:
            msg = f"Head front/right seam has noticeable color jump (delta = {diff:.1f})."
            self.warnings.append(msg)
            self.seam_issues.append(msg)


def compute_aesthetic_score(canvas_or_arr, model: Optional[str] = None, deduct_defects: bool = True) -> Dict[str, Any]:
    """
    Compute a state-of-the-art algorithmic quality & aesthetic craftsmanship score (0.0 to 1.0)
    for a Minecraft skin using pixel art theory and community standards.

    Evaluates:
      1. Layer 2 Relief Metric (optimal 12-45% 3D accents).
      2. Color Palette Harmony & Entropy (16-70 harmonious colors, avoids muddy flat fills or bloat).
      3. Shading Variance & Depth (detects dynamic light range on main faces).
      4. Spatial Cluster Coherence (autocorrelation ratio; separates true pixel clusters from TV noise).
      5. Vectorized Hue Shifting (rewards artistic warm highlights & cool shadow temperature ramps).
      6. Seam Continuity (continuity across 3D cuboid transitions).
      7. Defect Deductions (penalizes Rule 1 holes, Rule 3 floating cardboard, and Rule 4 planks).
    """
    if hasattr(canvas_or_arr, "arr"):
        arr = canvas_or_arr.arr
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
    else:
        arr = np.array(canvas_or_arr, dtype=np.uint8)

    if not model:
        model = "default"

    uv_map = get_uv_map(model)
    recommendations: List[str] = []
    deductions: List[str] = []

    # 1. Layer 2 Relief Metric
    l2_pixels = 0
    total_l2_pixels = 0
    for name, (u0, v0, u1, v1) in uv_map.items():
        if name.startswith("hat_") or name.startswith("jacket_") or "sleeve" in name or "pants" in name:
            part = arr[v0:v1, u0:u1]
            total_l2_pixels += part.shape[0] * part.shape[1]
            l2_pixels += int(np.sum(part[:, :, 3] > 0))

    l2_ratio = l2_pixels / max(1, total_l2_pixels)
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

    # 2. Color Palette Richness
    opaque_mask = arr[:, :, 3] > 128
    opaque_colors = arr[opaque_mask][:, :3]
    if len(opaque_colors) > 0:
        unique_colors = len(np.unique(opaque_colors, axis=0))
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

    # 3. Shading Variance & Spatial Coherence (Anti-Noise / Anti-Confetti)
    std_scores = []
    coherence_scores = []
    pillow_detected = False
    test_faces = ["head_front", "body_front", "right_arm_front"]

    for test_face in test_faces:
        u0, v0, u1, v1 = uv_map[test_face]
        face_rgb = arr[v0:v1, u0:u1, :3]
        std_val = float(np.mean(np.std(face_rgb.astype(float), axis=(0, 1))))
        std_scores.append(std_val)

        if face_rgb.shape[0] > 1 and face_rgb.shape[1] > 1:
            dh = np.mean(np.abs(face_rgb[:, 1:].astype(float) - face_rgb[:, :-1].astype(float)))
            dv = np.mean(np.abs(face_rgb[1:, :].astype(float) - face_rgb[:-1, :].astype(float)))
            d_local = float((dh + dv) / 2.0)
            ratio = d_local / (std_val + 1e-5)

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

        if not pillow_detected and detect_pillow_shading(face_rgb):
            pillow_detected = True

    mean_std = float(np.mean(std_scores))
    if 12.0 <= mean_std <= 85.0:
        score_shading = 1.0
    elif mean_std < 12.0:
        score_shading = max(0.1, mean_std / 12.0)
    else:
        score_shading = max(0.6, 1.0 - (mean_std - 85.0) * 0.01)

    score_coherence = float(np.mean(coherence_scores))

    if pillow_detected:
        recommendations.append("Avoid pillow shading: shade with directional light and form clusters rather than darkening all perimeter edges.")

    # 4. Fast Vectorized Hue Shifting
    hue_scores = []
    for face in ["head_front", "body_front"]:
        u0, v0, u1, v1 = uv_map[face]
        crop = arr[v0:v1, u0:u1, :3]
        f_rgb = crop.astype(float) / 255.0
        r, g, b = f_rgb[..., 0], f_rgb[..., 1], f_rgb[..., 2]
        maxc = np.maximum(np.maximum(r, g), b)
        minc = np.minimum(np.minimum(r, g), b)
        v = maxc
        deltac = maxc - minc
        safe_delta = np.where(deltac == 0, 1.0, deltac)
        s = np.where(maxc != 0, deltac / np.where(maxc == 0, 1.0, maxc), 0.0)
        rc = np.where(deltac != 0, (maxc - r) / safe_delta, 0.0)
        gc = np.where(deltac != 0, (maxc - g) / safe_delta, 0.0)
        bc = np.where(deltac != 0, (maxc - b) / safe_delta, 0.0)
        h = np.zeros_like(r)
        mask_r = (r == maxc) & (deltac != 0)
        mask_g = (g == maxc) & (deltac != 0)
        mask_b = (b == maxc) & (deltac != 0)
        h = np.where(mask_r, bc - gc, h)
        h = np.where(mask_g, 2.0 + rc - bc, h)
        h = np.where(mask_b, 4.0 + gc - rc, h)
        h = (h / 6.0) % 1.0

        sat_mask = s > 0.12
        if np.sum(sat_mask) >= 8:
            med_v = float(np.median(v[sat_mask]))
            sh_h = h[sat_mask & (v < med_v)]
            hi_h = h[sat_mask & (v >= med_v)]
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

    # 5. Seam Continuity
    def seam_diff(p1, p2, e1, e2):
        u0_a, v0_a, u1_a, v1_a = uv_map[p1]
        u0_b, v0_b, u1_b, v1_b = uv_map[p2]
        c1 = arr[v0_a:v1_a, u0_a:u1_a, :3].astype(float)
        c2 = arr[v0_b:v1_b, u0_b:u1_b, :3].astype(float)
        return float(np.mean(np.abs(c1[:, e1] - c2[:, e2])))

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

    # Weighted Base Score
    base_score = float(
        0.25 * score_l2 +
        0.20 * score_colors +
        0.20 * score_shading +
        0.15 * score_coherence +
        0.10 * score_hue +
        0.10 * score_seams
    )

    penalty_points = 0.0
    if deduct_defects:
        base_parts = [k for k in uv_map.keys() if not any(x in k for x in ['hat', 'jacket', 'sleeve', 'pants'])]
        base_pixels_total = sum((uv_map[bp][2] - uv_map[bp][0]) * (uv_map[bp][3] - uv_map[bp][1]) for bp in base_parts)
        base_opaque_total = sum(int(np.sum(arr[uv_map[bp][1]:uv_map[bp][3], uv_map[bp][0]:uv_map[bp][2], 3] == 255)) for bp in base_parts)
        if base_opaque_total > 0.5 * base_pixels_total:
            holes = base_pixels_total - base_opaque_total
            if holes > 0:
                p = min(0.20, 0.05 + holes * 0.01)
                penalty_points += p
                deductions.append(f"-{p:.2f}: {holes} base layer non-opaque holes (Rule 1)")

        u0, v0, u1, v1 = uv_map["hat_front"]
        hat_f = arr[v0:v1, u0:u1]
        f_rows = sum(1 for r in range(5, 8) if np.any(hat_f[r, :, 3] > 0))
        if f_rows > 0:
            p = f_rows * 0.04
            penalty_points += p
            deductions.append(f"-{p:.2f}: {f_rows} floating lower rows on hat_front (Rule 3)")

        u0, v0, u1, v1 = uv_map["hat_top"]
        hat_t_count = int(np.sum(arr[v0:v1, u0:u1, 3] > 0))
        if 0 < hat_t_count < 20:
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
        "deductions": deductions,
        "recommendations": recommendations,
    }
