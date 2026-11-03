"""
SkinValidator & Autonomous Golden Rules Self-Healer for SkinForge (v1.3.0).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

from ..core.canvas import SkinCanvas
from ..core.uv import (
    BASE_PARTS,
    OUTER_PARTS,
    detect_skin_model_from_array,
    get_uv_map,
    load_skin_array,
)
from .aesthetic import compute_aesthetic_score, evaluate_golden_rules


class SkinValidator:
    """Comprehensive geometry, Golden Rules, and craftsmanship validator for Minecraft skins."""

    def __init__(self, skin_source: Any, model: Optional[str] = None):
        self.source_desc = "in-memory canvas"
        self.model = model
        self.was_legacy_64x32 = False

        if isinstance(skin_source, str):
            self.source_desc = skin_source
            self.arr, self.was_legacy_64x32 = load_skin_array(skin_source)
            self.im = Image.fromarray(self.arr, "RGBA")
            if self.model is None:
                self.model = detect_skin_model_from_array(self.arr)
        elif isinstance(skin_source, SkinCanvas):
            self.model = skin_source.model if self.model is None else self.model
            self.arr = skin_source.to_array()
            self.im = Image.fromarray(self.arr, "RGBA")
            self.was_legacy_64x32 = getattr(skin_source, "was_converted_from_legacy", False)
        elif isinstance(skin_source, Image.Image):
            self.arr, self.was_legacy_64x32 = load_skin_array(skin_source)
            self.im = Image.fromarray(self.arr, "RGBA")
            if self.model is None:
                self.model = detect_skin_model_from_array(self.arr)
        elif isinstance(skin_source, np.ndarray):
            self.arr, self.was_legacy_64x32 = load_skin_array(skin_source)
            self.im = Image.fromarray(self.arr, "RGBA")
            if self.model is None:
                self.model = detect_skin_model_from_array(self.arr)
        else:
            raise TypeError(f"Unsupported skin source type: {type(skin_source)}")

        if not self.model:
            self.model = "default"

        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.layer1_holes: Dict[str, int] = {}
        self.layer2_violations: List[str] = []
        self.seam_issues: List[str] = []

    def validate(self) -> Tuple[bool, str]:
        """Run all validation checks and return (is_valid, report_str)."""
        res = self.validate_structured()
        return res["valid"], res["report"]

    def validate_structured(self) -> Dict[str, Any]:
        """Run all validation checks and return structured diagnostic dictionary."""
        self.issues.clear()
        self.warnings.clear()
        self.layer1_holes.clear()
        self.layer2_violations.clear()
        self.seam_issues.clear()

        self._check_dimensions()
        self._check_base_layer_holes()
        self._check_outer_layer_floating_planes()
        self._check_seams()

        aesthetic = compute_aesthetic_score(self.arr, model=self.model, deduct_defects=True)

        report: List[str] = []
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

        suggestions: List[str] = []
        if self.layer1_holes:
            total_holes = sum(self.layer1_holes.values())
            suggestions.append(f"Call 'skin_auto_fix()' to fill {total_holes} non-opaque pixels on Layer 1 (Rule 1).")
        if self.layer2_violations:
            suggestions.append("Call 'skin_auto_fix()' to strip illegal floating cardboard planes on hat_front (rows 4-7) and hat_top (Rules 2, 3 & 4).")
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
            "golden_rules": aesthetic["golden_rules"],
            "deductions": aesthetic["deductions"],
            "recommendations": aesthetic["recommendations"],
            "report": "\n".join(report),
        }

    def _check_dimensions(self) -> None:
        if self.im.size != (64, 64):
            self.issues.append(f"Image dimensions must be 64x64, found {self.im.size}")

    def _check_base_layer_holes(self) -> None:
        uv_map = get_uv_map(self.model)
        for name in BASE_PARTS:
            u0, v0, u1, v1 = uv_map[name]
            crop = self.arr[v0:v1, u0:u1]
            holes = int(np.sum(crop[:, :, 3] < 255))
            if holes > 0:
                self.warnings.append(f"Base part '{name}' has {holes} non-opaque pixels (Rule 1).")
                self.layer1_holes[name] = holes

    def _check_outer_layer_floating_planes(self) -> None:
        uv_map = get_uv_map(self.model)

        # Rule 3: hat_front lower rows 4..7 MUST be transparent
        u0, v0, u1, v1 = uv_map["hat_front"]
        hat_f = self.arr[v0:v1, u0:u1]
        for r in range(4, 8):
            row_alpha = hat_f[r, :, 3] > 0
            if np.any(row_alpha):
                msg = f"hat_front row {r} has {int(np.sum(row_alpha))}/8 non-transparent pixels (Rule 3: floating cardboard in profile)."
                self.warnings.append(msg)
                self.layer2_violations.append(msg)

        # Rule 4: hat_top isolated floating crown planks (< 20 pixels)
        u0, v0, u1, v1 = uv_map["hat_top"]
        hat_t = self.arr[v0:v1, u0:u1]
        t_alpha = hat_t[:, :, 3] > 0
        pixel_count = int(np.sum(t_alpha))
        if 0 < pixel_count < 20:
            msg = f"hat_top has only {pixel_count} pixels (Rule 4: floating detached plank over crown)."
            self.warnings.append(msg)
            self.layer2_violations.append(msg)

        # Rule 2: Bloated marshmallow Layer 2 check (> 65% filled)
        l2_pixels = sum(
            int(np.sum(self.arr[uv_map[p][1]:uv_map[p][3], uv_map[p][0]:uv_map[p][2], 3] > 0))
            for p in OUTER_PARTS
        )
        l2_total = sum((uv_map[p][2] - uv_map[p][0]) * (uv_map[p][3] - uv_map[p][1]) for p in OUTER_PARTS)
        l2_ratio = l2_pixels / max(1, l2_total)
        if l2_ratio > 0.65:
            msg = f"Layer 2 relief density is {l2_ratio*100:.1f}% (>65% max, Rule 2 bloated armor look)."
            self.warnings.append(msg)
            self.layer2_violations.append(msg)

        # Check pants front for giant white blocks
        u0, v0, u1, v1 = uv_map["left_pants_front"]
        p_crop = self.arr[v0:v1, u0:u1]
        bright_white_count = int(
            np.sum(
                (p_crop[:, :, 0] > 240)
                & (p_crop[:, :, 1] > 240)
                & (p_crop[:, :, 2] > 240)
                & (p_crop[:, :, 3] > 0)
            )
        )
        if bright_white_count > 6:
            self.warnings.append(f"left_pants_front has {bright_white_count} solid white pixels on Layer 2.")

    def _check_seams(self) -> None:
        uv_map = get_uv_map(self.model)
        u0_f, v0_f, u1_f, v1_f = uv_map["head_front"]
        u0_r, v0_r, u1_r, v1_r = uv_map["head_right"]

        edge_r = self.arr[v0_r:v1_r, u1_r - 1, :3]
        edge_f = self.arr[v0_f:v1_f, u0_f, :3]
        diff = float(np.mean(np.abs(edge_r.astype(np.int32) - edge_f.astype(np.int32))))
        if diff > 50:
            msg = f"Head front/right seam has noticeable color jump (delta = {diff:.1f})."
            self.warnings.append(msg)
            self.seam_issues.append(msg)


def auto_fix_skin(
    canvas: SkinCanvas,
    default_skin_color: Optional[str] = None,
    ensure_relief: bool = True
) -> Dict[str, Any]:
    """
    Deterministically heal all 4 Golden Rules on a SkinCanvas:
      - Rule 1: Plugs all non-opaque holes on all 36 Base Layer parts.
      - Rule 2: Ensures Layer 2 is in the optimal +0.35 3D relief range (thins bloated >65% layers,
                or adds subtle relief accents if Layer 2 was empty/under-dense).
      - Rule 3: Clears hat_front rows 4..7 to 100% transparent.
      - Rule 4: Clears isolated floating crown planks (<20 px) on hat_top.
    """
    healed_holes = canvas.heal_layer1_holes(default_color=default_skin_color)
    sanitized_l2 = canvas.sanitize_outer_layer(ensure_relief=ensure_relief)
    golden = evaluate_golden_rules(canvas.to_array(), model=canvas.model)
    return {
        "healed_layer1_holes": healed_holes,
        "sanitized_layer2_pixels": sanitized_l2,
        "golden_rules": golden,
    }
