"""
Visual Rendering, Blueprint Inspection, Seam Auditing, Aesthetic Engine & Multimodal Critic MCP Tools (v2.0.0).
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, List, Optional

from ..ascii_codec import part_to_ascii, rgba_to_hex
from ..audit import (
    SkinValidator,
    align_seams,
    auto_fix_skin,
    check_seams,
    compute_aesthetic_score,
)
from ..core import BASE_PARTS, OUTER_PARTS, atomic_save_png
from ..regions import REGION_PARTS
from ..renderer import (
    render_3d_single,
    render_3d_turnaround,
    render_bottom_up,
    render_composite_2d,
    render_part_zoomed,
    render_turntable_gif,
)
from .protocol import (
    MCPServer,
    handle_mcp_errors,
    image_to_content,
    types,
    validate_part_name,
)


def _build_critic_recipes(
    aesthetic: Dict[str, Any],
    seams: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert quantitative audit findings into exact, ready-to-call MCP tool recipes."""
    recipes: List[Dict[str, Any]] = []
    gr = aesthetic["golden_rules"]
    m = aesthetic["metrics"]

    if not gr["all_passed"]:
        reasons = []
        if not gr["rule1_zero_holes"]["passed"]:
            reasons.append(f"Rule 1 ({gr['rule1_zero_holes']['holes']} holes)")
        if not gr["rule2_relief_depth"]["passed"]:
            reasons.append(f"Rule 2 ({gr['rule2_relief_depth']['layer2_pct']}% L2)")
        if not gr["rule3_hat_front"]["passed"]:
            reasons.append(f"Rule 3 ({gr['rule3_hat_front']['violating_pixels']} bad hat_front px)")
        if not gr["rule4_hat_top"]["passed"]:
            reasons.append(f"Rule 4 ({gr['rule4_hat_top']['hat_top_pixels']} floating hat_top px)")
        recipes.append({
            "priority": "critical",
            "issue": "Golden Rules violation: " + ", ".join(reasons),
            "tool": "skin_auto_fix",
            "arguments": {},
        })

    if m["shading_depth"] < 0.65 or m["hue_shifting"] < 0.60:
        recipes.append({
            "priority": "high",
            "issue": f"Flat shading or weak hue-shifting (shading={int(m['shading_depth']*100)}%, hue_shift={int(m['hue_shifting']*100)}%)",
            "tool": "skin_auto_shade",
            "arguments": {"target": "base", "style": "directional", "strength": 0.35, "hue_shift_deg": 18.0},
        })

    if seams:
        recipes.append({
            "priority": "medium",
            "issue": f"{len(seams)} 3D seam tear(s) detected across adjacent cuboid edges",
            "tool": "skin_align_seams",
            "arguments": {"seam_name": "all", "mode": "blend"},
        })

    if m["spatial_coherence"] < 0.60:
        recipes.append({
            "priority": "medium",
            "issue": f"High pixel scatter / compression noise (coherence={int(m['spatial_coherence']*100)}%)",
            "tool": "skin_denoise_palette",
            "arguments": {"min_pixel_count": 3},
        })

    if aesthetic["layer2_ratio"] < 0.12:
        recipes.append({
            "priority": "medium",
            "issue": f"Sparse 3D relief ({aesthetic['layer2_ratio']*100:.1f}% Layer 2; optimal 12–45%)",
            "tool": "skin_apply_preset",
            "arguments": {"preset_name": "hair_bangs"},
        })

    return recipes


def register_audit_tools(server: MCPServer, session: Any, project_root: str) -> Dict[str, Any]:
    """Register visual rendering, blueprint inspection, critic, seam, validation, and auto-fix tools."""

    @server.tool()
    @handle_mcp_errors(multimodal=True)
    def skin_render_3d(
        preset: str = "turnaround",
        yaw_deg: float = -30.0,
        pitch_deg: float = 15.0,
        layer_mode: str = "both",
        save_path: Optional[str] = None,
    ) -> List[types.ContentBlock]:
        """Render a 3D Z-buffered rasterized model of the skin and return it directly as an image."""
        layer_mode = layer_mode.lower()
        if layer_mode not in ("both", "base", "outer"):
            layer_mode = "both"

        with session.lock:
            if preset == "turnaround":
                img = render_3d_turnaround(session.canvas, out_path=None, layer_mode=layer_mode)
                desc = f"3D Turnaround (4 angles) [layers: {layer_mode}]"
            elif preset == "bottom_up":
                img = render_bottom_up(session.canvas, out_path=None, layer_mode=layer_mode)
                desc = f"3D Bottom-Up View (chin, neck, hood underside) [layers: {layer_mode}]"
            elif preset == "front":
                img = render_3d_single(session.canvas, yaw_deg=0, pitch_deg=10, layer_mode=layer_mode)
                desc = f"3D Front View [layers: {layer_mode}]"
            elif preset == "back":
                img = render_3d_single(session.canvas, yaw_deg=180, pitch_deg=10, layer_mode=layer_mode)
                desc = f"3D Back View [layers: {layer_mode}]"
            elif preset == "left_profile":
                img = render_3d_single(session.canvas, yaw_deg=75, pitch_deg=8, layer_mode=layer_mode)
                desc = f"3D Left Profile View (check for floating cardboard) [layers: {layer_mode}]"
            elif preset == "right_profile":
                img = render_3d_single(session.canvas, yaw_deg=-75, pitch_deg=8, layer_mode=layer_mode)
                desc = f"3D Right Profile View [layers: {layer_mode}]"
            else:
                img = render_3d_single(session.canvas, yaw_deg=yaw_deg, pitch_deg=pitch_deg, layer_mode=layer_mode)
                desc = f"3D Custom Angle (yaw={yaw_deg}°, pitch={pitch_deg}°) [layers: {layer_mode}]"

        saved_msg = ""
        if save_path:
            out = atomic_save_png(img, save_path)
            saved_msg = f"\nSaved image to: '{out}'"

        return [
            types.TextContent(type="text", text=f"Rendered {desc}.{saved_msg}\nInspect the visual output below:"),
            image_to_content(img),
        ]

    @server.tool()
    @handle_mcp_errors(multimodal=True)
    def skin_render_2d(
        layer_mode: str = "both",
        scale: int = 16,
        save_path: Optional[str] = None,
    ) -> List[types.ContentBlock]:
        """Render front and back 2D composite view with Layer 2 overlaid and return as an image."""
        with session.lock:
            img = render_composite_2d(session.canvas, out_path=None, scale=scale)
        saved_msg = ""
        if save_path:
            out = atomic_save_png(img, save_path)
            saved_msg = f"\nSaved composite to: '{out}'"

        return [
            types.TextContent(type="text", text=f"Rendered 2D Composite (Front and Back with Layer 2 overlay).{saved_msg}"),
            image_to_content(img),
        ]

    @server.tool()
    @handle_mcp_errors(multimodal=True)
    def skin_render_part(
        part_name: str,
        scale: int = 16,
        show_grid: bool = True,
        save_path: Optional[str] = None,
    ) -> List[types.ContentBlock]:
        """Render an individual UV part face enlarged with a pixel grid for micro-inspection."""
        err = validate_part_name(part_name)
        if err:
            return [types.TextContent(type="text", text=err)]

        with session.lock:
            img = render_part_zoomed(session.canvas, part_name, scale=scale, show_grid=show_grid, out_path=None)
            h, w, _ = session.canvas.parts[part_name].shape

        saved_msg = ""
        if save_path:
            out = atomic_save_png(img, save_path)
            saved_msg = f"\nSaved to: '{out}'"

        return [
            types.TextContent(type="text", text=f"Zoomed view of part '{part_name}' ({w}x{h} px, scale={scale}x).{saved_msg}"),
            image_to_content(img),
        ]

    @server.tool()
    @handle_mcp_errors(multimodal=True)
    def skin_render_turntable_gif(
        frames: int = 16,
        fps: int = 12,
        layer_mode: str = "both",
        out_path: Optional[str] = None,
    ) -> List[Any]:
        """Generate an animated 360-degree turntable rotation GIF of the player model."""
        if not out_path and session.file_path:
            out = os.path.join(os.path.dirname(session.file_path), "turntable_360.gif")
        else:
            out = out_path or os.path.join(project_root, "previews", "turntable_360.gif")
        out = os.path.abspath(os.path.expanduser(out))
        os.makedirs(os.path.dirname(out), exist_ok=True)

        with session.lock:
            render_turntable_gif(session.canvas, out, frames=frames, fps=fps, layer_mode=layer_mode)
        with open(out, "rb") as f:
            b64_str = base64.b64encode(f.read()).decode("utf-8")
        try:
            gif_content = types.ImageContent(type="image", data=b64_str, mime_type="image/gif", mimeType="image/gif")
        except TypeError:
            try:
                gif_content = types.ImageContent(type="image", data=b64_str, mimeType="image/gif")
            except TypeError:
                gif_content = types.ImageContent(type="image", data=b64_str, mime_type="image/gif")
        return [
            types.TextContent(type="text", text=f"Successfully generated {frames}-frame turntable GIF at: '{out}' ({os.path.getsize(out)} bytes)."),
            gif_content,
        ]

    @server.tool()
    @handle_mcp_errors(json_output=True)
    def skin_inspect_blueprint(
        include_ascii_region: Optional[str] = None,
        top_colors: int = 8,
    ) -> str:
        """
        AI Context-Optimized Full-Skin Blueprint Inspector (v2.0.0).
        Returns a single compact JSON snapshot of the active skin: model, Golden Rules status,
        6-metric Aesthetic Score, top dominant colors, active Layer 2 parts, seam summary,
        and optional ASCII grids for a specific semantic region ('head', 'hat', 'torso', 'jacket', 'arms', 'legs').
        Replaces 6-8 separate inspection tool calls with 1 token-efficient call.
        """
        with session.lock:
            aesthetic = compute_aesthetic_score(session.canvas, deduct_defects=True)
            seams = check_seams(session.canvas, tolerance=35)
            colors = session.canvas.list_colors(top_n=top_colors, ignore_transparent=True)
            active_outer = [
                p for p in OUTER_PARTS
                if int((session.canvas.parts[p][:, :, 3] > 0).sum()) > 0
            ]
            ascii_dump: Dict[str, Any] = {}
            if include_ascii_region:
                reg = include_ascii_region.lower().strip()
                target_parts = REGION_PARTS.get(reg)
                if target_parts is None:
                    if reg in session.canvas.parts:
                        target_parts = [reg]
                    else:
                        return json.dumps({
                            "status": "error",
                            "error": f"Unknown region '{include_ascii_region}'. Valid: {sorted(REGION_PARTS.keys())}",
                        }, indent=2)
                for p in target_parts:
                    grid, pal = part_to_ascii(session.canvas.parts[p], tolerance=8)
                    ascii_dump[p] = {
                        "grid": grid,
                        "palette": {ch: rgba_to_hex(rgba) for ch, rgba in pal.items()},
                    }

            payload: Dict[str, Any] = {
                "status": "success",
                "model": session.canvas.model,
                "score": aesthetic["score"],
                "tier": aesthetic["tier"],
                "metrics": aesthetic["metrics"],
                "golden_rules_passed": aesthetic["golden_rules"]["all_passed"],
                "golden_rules": {
                    "rule1_holes": aesthetic["golden_rules"]["rule1_zero_holes"]["holes"],
                    "rule2_layer2_pct": aesthetic["golden_rules"]["rule2_relief_depth"]["layer2_pct"],
                    "rule3_hat_front_bad_px": aesthetic["golden_rules"]["rule3_hat_front"]["violating_pixels"],
                    "rule4_hat_top_px": aesthetic["golden_rules"]["rule4_hat_top"]["hat_top_pixels"],
                },
                "seam_issues_count": len(seams),
                "active_outer_parts": active_outer,
                "top_colors": [
                    {"hex": c["hex"], "percentage": c["percentage"], "count": c["count"]}
                    for c in colors
                ],
                "fix_recipes": _build_critic_recipes(aesthetic, seams),
            }
            if ascii_dump:
                payload["ascii_parts"] = ascii_dump

        return json.dumps(payload, indent=2)

    @server.tool()
    @handle_mcp_errors(multimodal=True)
    def skin_critic(layer_mode: str = "both") -> List[types.ContentBlock]:
        """
        Multimodal Visual + Quantitative Self-Critique Loop (v2.0.0).
        In ONE call, renders a 3D turnaround image AND produces an actionable craftsmanship report
        with exact MCP tool-call recipes to push the skin to top_tier (>= 0.85) with 0 defects.
        """
        with session.lock:
            img = render_3d_turnaround(session.canvas, out_path=None, layer_mode=layer_mode)
            aesthetic = compute_aesthetic_score(session.canvas, deduct_defects=True)
            seams = check_seams(session.canvas, tolerance=35)
            model_label = session.canvas.model.upper()

        recipes = _build_critic_recipes(aesthetic, seams)
        m = aesthetic["metrics"]
        gr = aesthetic["golden_rules"]

        lines = [
            f"=== SkinForge v2.0 Multimodal Critic ({model_label}) ===",
            f"Score: {aesthetic['score']:.2f} / 1.0 [{aesthetic['tier'].upper()}] | Golden Rules: {'ALL PASS' if gr['all_passed'] else 'NEEDS FIX'}",
            f"Metrics: Relief {int(m['relief_3d']*100)}% | Palette {int(m['palette_harmony']*100)}% | "
            f"Shading {int(m['shading_depth']*100)}% | Coherence {int(m['spatial_coherence']*100)}% | "
            f"HueShift {int(m['hue_shifting']*100)}% | Seams {int(m['seam_continuity']*100)}%",
        ]
        if recipes:
            lines.append("\nRecommended Action Recipes (call directly or bundle in skin_batch_actions):")
            for i, rec in enumerate(recipes, 1):
                lines.append(
                    f"  {i}. [{rec['priority'].upper()}] {rec['issue']}\n"
                    f"     -> {rec['tool']}({json.dumps(rec['arguments'])})"
                )
        else:
            lines.append("\n[EXCELLENT] Skin passes all 4 Golden Rules and meets high craftsmanship standards!")

        return [
            types.TextContent(type="text", text="\n".join(lines)),
            image_to_content(img),
        ]

    @server.tool()
    @handle_mcp_errors()
    def skin_check_seams(tolerance: int = 35) -> str:
        """Audit 3D cube edge wrap-around continuity across adjacent faces."""
        with session.lock:
            discrepancies = check_seams(session.canvas, tolerance=tolerance)
        if not discrepancies:
            return f"Pass: All 3D seams are continuous and well-aligned (tolerance={tolerance}). Zero texture tears detected."

        total_mismatches = sum(d["mismatch_count"] for d in discrepancies)
        lines = [
            f"=== 3D Seam Continuity Audit ({len(discrepancies)} seam(s) flagged, {total_mismatches} mismatched pixel(s)) ==="
        ]
        for d in discrepancies:
            lines.append(f"\n* Seam: {d['seam_name']} ({d['part_a']} <-> {d['part_b']}) - {d['mismatch_count']} mismatched px:")
            for m in d["mismatches"][:5]:
                lines.append(f"    - Index {m['index']}: {m['color_a']} vs {m['color_b']} (dist: {m['color_distance']})")
            if len(d["mismatches"]) > 5:
                lines.append(f"    ... and {len(d['mismatches']) - 5} more.")
        lines.append("\nTip: Call 'skin_align_seams()' to automatically heal and blend these seams.")
        return "\n".join(lines)

    @server.tool()
    @handle_mcp_errors()
    def skin_align_seams(seam_name: str = "all", mode: str = "blend") -> str:
        """Automatically heal and harmonize color continuity along adjacent 3D cube edges."""
        with session.lock:
            session.push_undo(action=f"align_seams:{seam_name}")
            aligned = align_seams(session.canvas, seam_name=seam_name, mode=mode)
            session.mark_dirty()
        return f"Successfully aligned {aligned} edge pixel(s) across seam(s) matching '{seam_name}' using mode='{mode}'. Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_aesthetic_audit(detailed: bool = True) -> str:
        """Perform a comprehensive 6-metric pixel art craftsmanship and Golden Rules audit."""
        with session.lock:
            res = compute_aesthetic_score(session.canvas, deduct_defects=True)
            model_label = session.canvas.model.upper()

        m = res["metrics"]
        gr = res["golden_rules"]

        out = [
            "=== SkinForge Aesthetic Craftsmanship Audit ===",
            f"Model: {model_label} | Overall Score: {res['score']:.2f} / 1.0 [{res['tier'].upper()}] (Base: {res['base_score']:.2f})",
            "",
            "Craftsmanship Radar Metrics:",
            f"  - 3D Relief Depth:       {int(m['relief_3d']*100)}% ({res['layer2_ratio']*100:.1f}% Layer 2 coverage)",
            f"  - Palette Harmony:       {int(m['palette_harmony']*100)}% ({res['unique_colors']} unique colors)",
            f"  - Shading Depth:         {int(m['shading_depth']*100)}% (variance: {res['shading_variance']})",
            f"  - Spatial Coherence:     {int(m['spatial_coherence']*100)}% (anti-noise cluster density)",
            f"  - Hue-Shift Dynamics:    {int(m['hue_shifting']*100)}% (color temperature ramps)",
            f"  - Seam Continuity:       {int(m['seam_continuity']*100)}% (edge alignment)",
            "",
            "4 Golden Rules Status:",
            f"  - Rule 1 (Zero Holes):     {'PASS' if gr['rule1_zero_holes']['passed'] else 'FAIL'} ({gr['rule1_zero_holes']['holes']} holes)",
            f"  - Rule 2 (+0.35 Relief):   {'PASS' if gr['rule2_relief_depth']['passed'] else 'FAIL'} ({gr['rule2_relief_depth']['layer2_pct']}% L2)",
            f"  - Rule 3 (hat_front 4-7):  {'PASS' if gr['rule3_hat_front']['passed'] else 'FAIL'} ({gr['rule3_hat_front']['violating_pixels']} bad px)",
            f"  - Rule 4 (hat_top Planks): {'PASS' if gr['rule4_hat_top']['passed'] else 'FAIL'} ({gr['rule4_hat_top']['hat_top_pixels']} px)",
        ]

        if res["deductions"]:
            out.append("\nDefect Deductions:")
            for d in res["deductions"]:
                out.append(f"  - {d}")

        if res["recommendations"]:
            out.append("\nActionable Recommendations:")
            for r in res["recommendations"]:
                out.append(f"  -> {r}")
        else:
            out.append("\n[PERFECT] No aesthetic flaws detected. Skin meets top-tier craftsmanship standards!")

        return "\n".join(out)

    @server.tool()
    @handle_mcp_errors()
    def skin_validate() -> str:
        """Run full quality and layer discipline audit on the active working canvas."""
        with session.lock:
            validator = SkinValidator(session.canvas)
            res = validator.validate_structured()

        out = [res["report"]]
        if res["suggestions"]:
            out.append("\n[RECOMMENDED ACTIONS]:")
            for s in res["suggestions"]:
                out.append(f"  -> {s}")

        return "\n".join(out)

    @server.tool()
    @handle_mcp_errors()
    def skin_auto_fix(default_skin_color: Optional[str] = None) -> str:
        """
        Autonomous self-healing tool for the 4 Golden Rules:
          1. Rule 1: Plugs all non-opaque holes on Layer 1 using neighbor colors or default_skin_color.
          2. Rule 2: Ensures Layer 2 is in the optimal +0.35 3D relief range (12–45%).
          3. Rule 3: Wipes out illegal floating pixels on hat_front rows 4–7.
          4. Rule 4: Clears isolated floating planks (<20 px) on hat_top.
        """
        with session.lock:
            session.push_undo(action="skin_auto_fix")
            fix_res = auto_fix_skin(session.canvas, default_skin_color=default_skin_color, ensure_relief=True)
            session.mark_dirty()

        healed = fix_res["healed_layer1_holes"]
        sanitized = fix_res["sanitized_layer2_pixels"]
        return (
            f"=== Autonomous Self-Healing Report ===\n"
            f"- Healed Layer 1 holes: {healed} pixels made 100% solid (Rule 1 compliant).\n"
            f"- Sanitized Layer 2: {sanitized} pixels adjusted for +0.35 relief & floating profile/crown rules (Rules 2, 3 & 4 compliant).\n"
            f"Active canvas is now compliant with all 4 Golden Rules of Minecraft Skin Depth! Live viewer updated."
        )

    return {
        "skin_render_3d": skin_render_3d,
        "skin_render_2d": skin_render_2d,
        "skin_render_part": skin_render_part,
        "skin_render_turntable_gif": skin_render_turntable_gif,
        "skin_inspect_blueprint": skin_inspect_blueprint,
        "skin_critic": skin_critic,
        "skin_check_seams": skin_check_seams,
        "skin_align_seams": skin_align_seams,
        "skin_aesthetic_audit": skin_aesthetic_audit,
        "skin_validate": skin_validate,
        "skin_auto_fix": skin_auto_fix,
    }
