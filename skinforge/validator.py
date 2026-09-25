"""
Validator and quality audit subsystem for SkinForge.
Detects holes in Layer 1, floating cardboard planes on Layer 2, and edge seam alignment issues.
Supports audit from file path, SkinCanvas instance, or PIL Image.
"""

import numpy as np
from PIL import Image
from .canvas import MINECRAFT_UV_MAP, SkinCanvas


class SkinValidator:
    def __init__(self, skin_source):
        self.source_desc = "in-memory canvas"
        if isinstance(skin_source, str):
            self.source_desc = skin_source
            self.im = Image.open(skin_source).convert("RGBA")
            self.arr = np.array(self.im)
        elif isinstance(skin_source, SkinCanvas):
            self.arr = np.zeros((64, 64, 4), dtype=np.uint8)
            for name, (u0, v0, u1, v1) in MINECRAFT_UV_MAP.items():
                self.arr[v0:v1, u0:u1] = skin_source.parts[name]
            self.im = Image.fromarray(self.arr)
        elif isinstance(skin_source, Image.Image):
            self.im = skin_source.convert("RGBA")
            self.arr = np.array(self.im)
        elif isinstance(skin_source, np.ndarray):
            self.arr = skin_source.copy()
            self.im = Image.fromarray(self.arr)
        else:
            raise TypeError(f"Unsupported skin source type: {type(skin_source)}")

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

        report = []
        report.append(f"=== SkinForge Quality Audit for '{self.source_desc}' ===")
        report.append(f"Dimensions: {self.im.size[0]}x{self.im.size[1]} | Mode: {self.im.mode}")

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

        suggestions = []
        if self.layer1_holes:
            total_holes = sum(self.layer1_holes.values())
            suggestions.append(f"Call 'skin_auto_fix()' to fill {total_holes} non-opaque pixels on Layer 1 (Rule 1).")
        if self.layer2_violations:
            suggestions.append("Call 'skin_auto_fix()' to strip illegal floating cardboard planes on hat_front and hat_top (Rules 3 & 4).")
        if self.seam_issues:
            suggestions.append("Align colors across head front/right/left seams to eliminate visible border lines.")

        return {
            "valid": len(self.issues) == 0,
            "dimensions": [self.im.size[0], self.im.size[1]],
            "issues": list(self.issues),
            "warnings": list(self.warnings),
            "layer1_holes": dict(self.layer1_holes),
            "layer2_violations": list(self.layer2_violations),
            "seam_issues": list(self.seam_issues),
            "suggestions": suggestions,
            "report": "\n".join(report),
        }

    def _check_dimensions(self):
        if self.im.size != (64, 64):
            self.issues.append(f"Image dimensions must be 64x64, found {self.im.size}")

    def _check_base_layer_holes(self):
        base_parts = [k for k in MINECRAFT_UV_MAP.keys() if not any(x in k for x in ['hat', 'jacket', 'sleeve', 'pants'])]
        for name in base_parts:
            u0, v0, u1, v1 = MINECRAFT_UV_MAP[name]
            crop = self.arr[v0:v1, u0:u1]
            holes = int(np.sum(crop[:, :, 3] < 255))
            if holes > 0:
                self.warnings.append(f"Base part '{name}' has {holes} non-opaque pixels (Rule 1).")
                self.layer1_holes[name] = holes

    def _check_outer_layer_floating_planes(self):
        # 1. Check hat_front lower rows (below brow line, rows 5..7)
        u0, v0, u1, v1 = MINECRAFT_UV_MAP["hat_front"]
        hat_f = self.arr[v0:v1, u0:u1]
        for r in range(5, 8):
            row_alpha = hat_f[r, :, 3] > 0
            if np.any(row_alpha):
                msg = f"hat_front row {r} has {int(np.sum(row_alpha))}/8 non-transparent pixels (Rule 3: floating cardboard in profile)."
                self.warnings.append(msg)
                self.layer2_violations.append(msg)

        # 2. Check hat_top for isolated floating lines
        u0, v0, u1, v1 = MINECRAFT_UV_MAP["hat_top"]
        hat_t = self.arr[v0:v1, u0:u1]
        t_alpha = hat_t[:, :, 3] > 0
        pixel_count = int(np.sum(t_alpha))
        if 0 < pixel_count < 20:
            msg = f"hat_top has only {pixel_count} pixels (Rule 4: floating detached plank over crown)."
            self.warnings.append(msg)
            self.layer2_violations.append(msg)

        # 3. Check pants front for giant white blocks
        u0, v0, u1, v1 = MINECRAFT_UV_MAP["left_pants_front"]
        p_crop = self.arr[v0:v1, u0:u1]
        bright_white_count = int(np.sum((p_crop[:, :, 0] > 240) & (p_crop[:, :, 1] > 240) & (p_crop[:, :, 2] > 240) & (p_crop[:, :, 3] > 0)))
        if bright_white_count > 6:
            self.warnings.append(f"left_pants_front has {bright_white_count} solid white pixels on Layer 2.")

    def _check_seams(self):
        # Check continuity between head_front and head_right/head_left
        u0_f, v0_f, u1_f, v1_f = MINECRAFT_UV_MAP["head_front"]
        u0_r, v0_r, u1_r, v1_r = MINECRAFT_UV_MAP["head_right"]

        edge_r = self.arr[v0_r:v1_r, u1_r - 1, :3]
        edge_f = self.arr[v0_f:v1_f, u0_f, :3]
        diff = float(np.mean(np.abs(edge_r.astype(int) - edge_f.astype(int))))
        if diff > 50:
            msg = f"Head front/right seam has noticeable color jump (delta = {diff:.1f})."
            self.warnings.append(msg)
            self.seam_issues.append(msg)


def compute_aesthetic_score(canvas_or_arr) -> Dict[str, Any]:
    """
    Compute an algorithmic quality and aesthetic craftsmanship score (0.0 to 1.0)
    for a Minecraft skin.
    
    Evaluates:
      1. Layer 2 relief density (optimal 15-40% 3D accents).
      2. Color palette entropy & shading ramp depth (16-55 harmonious colors).
      3. Surface texture variance (rejects flat unshaded flood fills).
    """
    if hasattr(canvas_or_arr, "arr"):
        arr = canvas_or_arr.arr
    elif hasattr(canvas_or_arr, "get_part"):
        # Synthesize 64x64 array from parts
        arr = np.zeros((64, 64, 4), dtype=np.uint8)
        for part_name, (u0, v0, u1, v1) in MINECRAFT_UV_MAP.items():
            arr[v0:v1, u0:u1] = canvas_or_arr.get_part(part_name)
    else:
        arr = np.array(canvas_or_arr, dtype=np.uint8)

    # 1. Layer 2 Relief Metric
    l2_pixels = 0
    total_l2_pixels = 0
    for name, (u0, v0, u1, v1) in MINECRAFT_UV_MAP.items():
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
    else:
        score_l2 = 0.2  # 0 active L2 pixels (flat skin)

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
    elif unique_colors < 8:
        score_colors = 0.15
    elif 70 < unique_colors <= 140:
        score_colors = 1.0 - (unique_colors - 70) * 0.005
    else:
        score_colors = 0.5  # extreme random noise / photo artifacts

    # 3. Shading Variance (Standard deviation across main faces)
    std_scores = []
    for test_face in ["head_front", "body_front", "right_arm_front"]:
        u0, v0, u1, v1 = MINECRAFT_UV_MAP[test_face]
        face_rgb = arr[v0:v1, u0:u1, :3]
        std_scores.append(float(np.mean(np.std(face_rgb, axis=(0, 1)))))

    mean_std = float(np.mean(std_scores))
    if 12.0 <= mean_std <= 85.0:
        score_shading = 1.0
    elif mean_std < 12.0:
        score_shading = max(0.1, mean_std / 12.0)
    else:
        score_shading = max(0.6, 1.0 - (mean_std - 85.0) * 0.01)

    # Weighted overall score
    overall = float(0.40 * score_l2 + 0.35 * score_colors + 0.25 * score_shading)
    overall = round(max(0.0, min(1.0, overall)), 3)

    return {
        "score": overall,
        "layer2_ratio": round(l2_ratio, 3),
        "unique_colors": unique_colors,
        "shading_variance": round(mean_std, 1),
        "tier": "top_tier" if overall >= 0.75 else "high" if overall >= 0.60 else "medium" if overall >= 0.40 else "low"
    }
