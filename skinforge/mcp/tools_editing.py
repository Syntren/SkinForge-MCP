"""
Pixel, ASCII, Region, Shading, Primitive, Color & Atomic Batch Editing MCP Tools (v2.0.0).
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

from ..ascii_codec import normalize_color, part_to_ascii, rgba_to_hex
from ..audit import align_seams, auto_fix_skin
from ..color import (
    ANIME_SKIN,
    CASUAL_STREETWEAR,
    COZY_PASTEL,
    CYBER_NINJA,
    FANTASY_KNIGHT,
    TECHWEAR_CYBERPUNK,
)
from ..converter import convert_skin_model
from ..core import MINECRAFT_UV_MAP, SkinCanvas
from ..outfits import apply_outfit
from ..rag import get_rag
from ..regions import draw_primitive, paint_region
from ..renderer import render_3d_turnaround
from ..shading import auto_shade_skin
from ..typography import draw_symbol, draw_text
from .protocol import (
    MCPServer,
    handle_mcp_errors,
    image_to_content,
    types,
    validate_part_name,
)
from .schemas import BatchActionSchema, PixelCoordSchema
from .tools_design import execute_preset_on_canvas


def _resolve_named_palette(palette_name: str) -> Optional[Dict[str, Any]]:
    p_name = palette_name.upper().strip()
    if p_name in ("TECHWEAR", "CYBERPUNK", "TECHWEAR_CYBERPUNK"):
        return TECHWEAR_CYBERPUNK
    if p_name in ("ANIME", "ANIME_SKIN"):
        return ANIME_SKIN
    if p_name in ("CASUAL", "CASUAL_STREETWEAR", "STREETWEAR"):
        return CASUAL_STREETWEAR
    if p_name in ("FANTASY", "FANTASY_KNIGHT", "KNIGHT"):
        return FANTASY_KNIGHT
    if p_name in ("NINJA", "CYBER_NINJA"):
        return CYBER_NINJA
    if p_name in ("PASTEL", "COZY", "COZY_PASTEL"):
        return COZY_PASTEL
    return None


def register_editing_tools(
    server: MCPServer,
    session: Any,
    skin_save_fn: Callable[..., str],
) -> Dict[str, Any]:
    """Register all pixel, ASCII, region, shading, primitive, color, and batch editing tools."""

    @server.tool()
    @handle_mcp_errors()
    def skin_get_part_ascii(part_name: str, tolerance: int = 6) -> str:
        """Reverse-engineer an existing part's pixels into a clean ASCII grid string and palette dictionary."""
        err = validate_part_name(part_name)
        if err:
            return err

        with session.lock:
            part_arr = session.canvas.parts[part_name]
            h, w, _ = part_arr.shape
            grid, palette = part_to_ascii(part_arr, tolerance=tolerance)

        pal_lines = [f"  '{ch}': {rgba}  # {rgba_to_hex(rgba)}" for ch, rgba in sorted(palette.items())]
        pal_str = "\n".join(pal_lines)
        return (
            f"=== Part: {part_name} ({w}x{h} px) ===\n"
            f"Palette:\n{pal_str}\n\n"
            f"ASCII Grid:\n{grid}\n\n"
            f"To edit this part: Modify the characters in the grid above and call 'skin_set_part_ascii'."
        )

    @server.tool()
    @handle_mcp_errors(json_output=True)
    def skin_denoise_palette(
        min_pixel_count: int = 3,
        part_name: Optional[str] = None,
    ) -> str:
        """Clean up compression noise and isolated color artifacts."""
        with session.lock:
            session.push_undo(action=f"denoise_palette:{part_name or 'all'}")
            modified = session.canvas.denoise_palette(min_pixel_count=min_pixel_count, part_name=part_name)
            session.mark_dirty()
            colors = session.canvas.list_colors(top_n=100, ignore_transparent=True)
        return json.dumps({
            "status": "success",
            "modified_pixels": modified,
            "current_unique_colors": len(colors),
            "message": f"Denoised palette: healed {modified} artifact pixels. Unique colors now: {len(colors)}.",
        })

    @server.tool()
    @handle_mcp_errors(json_output=True)
    def skin_import_part(
        source: str,
        part_name: str,
        target_part_name: Optional[str] = None,
    ) -> str:
        """Import an individual anatomical part from an external skin file or RAG skin_id."""
        err = validate_part_name(part_name)
        if err:
            return json.dumps({"error": err})
        dst_name = target_part_name or part_name
        err_dst = validate_part_name(dst_name)
        if err_dst:
            return json.dumps({"error": err_dst})

        src_canvas = SkinCanvas()
        if os.path.exists(source):
            src_canvas.load_png(source)
        else:
            rag = get_rag()
            if not rag.is_available:
                return json.dumps(rag.get_unavailable_response(query=source))
            s_data = rag.get_skin(source, as_canvas=True, as_ascii=False)
            if not s_data or "canvas" not in s_data:
                return json.dumps({"error": f"Source '{source}' is neither a valid file path nor an existing skin_id"})
            src_canvas = s_data["canvas"]

        with session.lock:
            session.push_undo(action=f"import_part:{part_name}->{dst_name}")
            session.canvas.set_part(dst_name, src_canvas.get_part(part_name))
            session.mark_dirty()

        return json.dumps({
            "status": "success",
            "message": f"Successfully imported '{part_name}' from '{source}' into '{dst_name}'. Live viewer updated.",
        })

    @server.tool()
    @handle_mcp_errors()
    def skin_build(
        palette: Dict[str, str],
        parts: Dict[str, str],
        model_type: str = "default",
        auto_fix: bool = True,
        auto_shade: bool = False,
        shade_style: str = "directional",
        align_seams_mode: Optional[str] = None,
        save_path: Optional[str] = None,
    ) -> str:
        """
        Generate and assemble a complete 64x64 dual-layer Minecraft skin in a single atomic call.
        Optionally applies procedural hue-shifted auto-shading, seam blending, and Golden Rules auto-fix.
        """
        with session.lock:
            session.push_undo(action="skin_build")
            session.canvas.model = "slim" if model_type and model_type.lower() == "slim" else "default"
            session.canvas.apply_ascii_skin(palette, parts)

            fix_summary: List[str] = []
            if auto_shade:
                shade_res = auto_shade_skin(session.canvas, target="all", style=shade_style)
                fix_summary.append(f"Auto-shaded {shade_res['shaded_pixels']} px ({shade_style})")
            if align_seams_mode:
                aligned = align_seams(session.canvas, seam_name="all", mode=align_seams_mode)
                if aligned:
                    fix_summary.append(f"Aligned {aligned} seam px")
            if auto_fix:
                healed = session.canvas.heal_layer1_holes()
                if healed:
                    fix_summary.append(f"Healed {healed} holes on Layer 1")
                sanitized = session.canvas.sanitize_outer_layer()
                if sanitized:
                    fix_summary.append(f"Sanitized {sanitized} floating pixels on Layer 2")

            session.mark_dirty()

        msg = f"Skin successfully built ({len(parts)} parts rendered, model: {model_type})."
        if fix_summary:
            msg += " Auto-fix: " + ", ".join(fix_summary) + "."
        if save_path:
            save_res = skin_save_fn(file_path=save_path, update_previews=True)
            msg += f" {save_res}"
        return msg

    @server.tool()
    @handle_mcp_errors()
    def skin_set_part_ascii(
        part_name: str,
        ascii_grid: str,
        palette: Optional[Dict[str, Any]] = None,
        palette_name: Optional[str] = None,
    ) -> str:
        """Draw a part using a multiline ASCII grid."""
        err = validate_part_name(part_name)
        if err:
            return err

        chosen_palette: Dict[str, Any] = palette or {}
        if isinstance(chosen_palette, str):
            try:
                chosen_palette = json.loads(chosen_palette)
            except Exception:
                chosen_palette = {}

        if palette_name:
            resolved = _resolve_named_palette(palette_name)
            if resolved is None:
                return f"Error: Unknown palette_name '{palette_name}'."
            chosen_palette = {**resolved, **chosen_palette}

        if not chosen_palette:
            chosen_palette = TECHWEAR_CYBERPUNK

        with session.lock:
            session.push_undo(action=f"set_ascii:{part_name}")
            session.canvas.set_ascii(part_name, ascii_grid, chosen_palette)
            session.mark_dirty()
            h, w, _ = session.canvas.parts[part_name].shape
        return f"Successfully updated '{part_name}' ({w}x{h} px) using ASCII grid. Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_fill_part(part_name: str, color: str) -> str:
        """Fill an entire UV face with a solid color."""
        err = validate_part_name(part_name)
        if err:
            return err
        with session.lock:
            session.push_undo(action=f"fill_part:{part_name}")
            session.canvas.fill_part(part_name, color)
            session.mark_dirty()
        return f"Filled '{part_name}' with {color}. Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_draw_rect(
        part_name: str,
        x: int,
        y: int,
        width: int,
        height: int,
        color: str,
    ) -> str:
        """Draw a filled rectangle on a part."""
        err = validate_part_name(part_name)
        if err:
            return err
        with session.lock:
            session.push_undo(action=f"draw_rect:{part_name}")
            session.canvas.draw_rect(part_name, x, y, width, height, color)
            session.mark_dirty()
        return f"Drawn rect at ({x}, {y}) of size {width}x{height} on '{part_name}' with color {color}. Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_set_pixel(part_name: str, x: int, y: int, color: str) -> str:
        """Set an individual pixel on a UV part."""
        err = validate_part_name(part_name)
        if err:
            return err
        px = PixelCoordSchema(x=x, y=y, color=color)
        with session.lock:
            session.push_undo(action=f"set_pixel:{part_name}({px.x},{px.y})")
            session.canvas.set_pixel(part_name, px.x, px.y, px.color)
            session.mark_dirty()
        return f"Set pixel ({px.x}, {px.y}) on '{part_name}' to {color}. Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_get_pixel(part_name: str, x: int, y: int) -> str:
        """Get the color of an individual pixel on a UV part."""
        err = validate_part_name(part_name)
        if err:
            return err
        with session.lock:
            rgba = session.canvas.get_pixel(part_name, x, y)
        hex_c = rgba_to_hex(rgba)
        return f"Pixel at ({x}, {y}) on '{part_name}': {rgba} ({hex_c})"

    @server.tool()
    @handle_mcp_errors()
    def skin_apply_gradient(
        part_name: str,
        start_color: str,
        end_color: str,
        direction: str = "vertical",
    ) -> str:
        """Apply a smooth linear color gradient across a part."""
        err = validate_part_name(part_name)
        if err:
            return err
        with session.lock:
            session.push_undo(action=f"gradient:{part_name}")
            session.canvas.apply_gradient(part_name, start_color, end_color, direction=direction)
            session.mark_dirty()
        return f"Applied {direction} gradient ({start_color} -> {end_color}) on '{part_name}'. Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_auto_shade(
        target: str = "all",
        style: str = "directional",
        strength: float = 0.35,
        hue_shift_deg: float = 18.0,
        dither: bool = False,
    ) -> str:
        """
        Procedural Pixel-Art Hue-Shifted Auto-Shading Engine (v2.0.0).
        Applies directional lighting, ambient occlusion, cylindrical limb shading, fabric folds,
        hair sheen strands, or metallic specular shading with cooler shadows and warmer highlights
        while preserving transparency and avoiding pillow shading.
        Args:
            target: Any UV part name or semantic group ('all', 'base', 'outer', 'head', 'hat', 'torso', 'jacket', 'arms', 'sleeves', 'legs', 'pants', 'limbs').
            style: 'directional', 'ambient_occlusion', 'cylindrical', 'fabric_folds', 'hair_strands', or 'metallic'.
            strength: Shading intensity (0.05 to 0.85, default 0.35).
            hue_shift_deg: Artistic temperature hue-shift in degrees (0 to 45, default 18).
            dither: Apply ordered 2x2 Bayer pixel-art dithering (default False).
        """
        with session.lock:
            session.push_undo(action=f"auto_shade:{target}:{style}")
            res = auto_shade_skin(
                session.canvas,
                target=target,
                style=style,
                strength=strength,
                hue_shift_deg=hue_shift_deg,
                dither=dither,
            )
            session.mark_dirty()
        return (
            f"Auto-shaded '{res['target']}' using style='{res['style']}' "
            f"(strength={res['strength']}, hue_shift={res['hue_shift_deg']}°, dither={res['dither']}): "
            f"{res['shaded_pixels']} opaque pixels across {res['shaded_parts_count']} part(s). Live viewer updated."
        )

    @server.tool()
    @handle_mcp_errors()
    def skin_paint_region(
        region: str,
        color: str,
        secondary_color: Optional[str] = None,
        pattern: str = "solid",
        row_start: Optional[int] = None,
        row_end: Optional[int] = None,
        include_caps: bool = True,
    ) -> str:
        """
        Semantic Multi-Face 3D Region Painter (v2.0.0).
        Paints all faces of an anatomical cuboid in a single call with wrap-around patterns.
        Args:
            region: 'head', 'hat', 'hair_cap', 'hat_cap', 'torso', 'jacket', 'arms', 'sleeves', 'legs', 'pants', 'right_arm', 'left_arm', 'right_leg', 'left_leg', 'shoes', 'hands'.
            color: Primary hex or RGBA color.
            secondary_color: Optional secondary color for gradients, stripes, checker, cuff, belt, collar.
            pattern: 'solid', 'vertical_gradient', 'horizontal_stripes', 'vertical_stripes', 'checker', 'cuff', 'belt', 'collar'.
            row_start/row_end: Optional vertical row slice (0-indexed) to wrap a horizontal band 360° around the region.
        """
        with session.lock:
            session.push_undo(action=f"paint_region:{region}:{pattern}")
            res = paint_region(
                session.canvas,
                region=region,
                color=color,
                secondary_color=secondary_color,
                pattern=pattern,
                row_start=row_start,
                row_end=row_end,
                include_caps=include_caps,
            )
            session.mark_dirty()
        return (
            f"Painted region '{res['region']}' with pattern='{res['pattern']}' "
            f"({res['pixels_painted']} pixels across {res['modified_parts_count']} faces: "
            f"{', '.join(res['modified_parts'])}). Live viewer updated."
        )

    @server.tool()
    @handle_mcp_errors()
    def skin_draw_primitive(
        part_name: str,
        primitive: str,
        x0: int = 0,
        y0: int = 0,
        x1: Optional[int] = None,
        y1: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        color: str = "#ffffff",
        secondary_color: Optional[str] = None,
        tolerance: int = 12,
        direction: str = "left_to_right",
    ) -> str:
        """
        Draw 2D pixel primitives on a UV face (v2.0.0):
          - 'line': Crisp Bresenham line from (x0, y0) to (x1, y1).
          - 'outline': 1px border frame at (x0, y0) with (width, height).
          - 'flood_fill': 4-connected bucket fill starting at (x0, y0) within RGB tolerance.
          - 'dither_rect': 2-color checkerboard dithered rectangle at (x0, y0, width, height).
          - 'mirror_x': Mirror one half of a face symmetrically ('left_to_right' or 'right_to_left').
        """
        err = validate_part_name(part_name)
        if err:
            return err
        with session.lock:
            session.push_undo(action=f"primitive:{primitive}:{part_name}")
            res = draw_primitive(
                session.canvas,
                part_name=part_name,
                primitive=primitive,
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                width=width,
                height=height,
                color=color,
                secondary_color=secondary_color,
                tolerance=tolerance,
                direction=direction,
            )
            session.mark_dirty()
        return f"Executed primitive '{res['primitive']}' on '{part_name}' ({res['pixels_changed']} pixels changed). Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_replace_color(
        old_color: str,
        new_color: str,
        part_name: Optional[str] = None,
        tolerance: int = 15,
        layer: str = "both",
    ) -> str:
        """Fuzzy replace occurrences of old_color with new_color within an RGB tolerance threshold."""
        if part_name:
            err = validate_part_name(part_name)
            if err:
                return err
        with session.lock:
            session.push_undo(action=f"replace_color:{old_color}->{new_color}")
            count, affected = session.canvas.replace_color(
                old_color=old_color,
                new_color=new_color,
                part_name=part_name,
                tolerance=tolerance,
                layer=layer,
            )
            session.mark_dirty()
        return (
            f"Successfully replaced color {old_color} -> {new_color} (tolerance={tolerance}):\n"
            f"- Total pixels replaced: {count}\n"
            f"- Affected parts ({len(affected)}): {', '.join(affected) if affected else 'none'}\n"
            f"Live viewer updated."
        )

    @server.tool()
    @handle_mcp_errors()
    def skin_adjust_hsv(
        part_name: Optional[str] = None,
        hue_shift: float = 0.0,
        sat_mult: float = 1.0,
        val_mult: float = 1.0,
        target_color: Optional[str] = None,
        tolerance: int = 30,
        layer: str = "both",
    ) -> str:
        """Vectorized Hue, Saturation, and Brightness adjustment across part(s) or entire skin."""
        if part_name:
            err = validate_part_name(part_name)
            if err:
                return err
        with session.lock:
            session.push_undo(action=f"adjust_hsv:{part_name or layer}")
            adjusted, affected = session.canvas.adjust_hsv(
                part_name=part_name,
                hue_shift=hue_shift,
                sat_mult=sat_mult,
                val_mult=val_mult,
                target_color=target_color,
                tolerance=tolerance,
                layer=layer,
            )
            session.mark_dirty()
        target_desc = part_name or f"entire skin (layer={layer})"
        filter_desc = f" matching target {target_color} (tol={tolerance})" if target_color else ""
        return (
            f"Adjusted HSV on {target_desc}{filter_desc}:\n"
            f"- Hue shift: {hue_shift}° | Saturation: x{sat_mult} | Value/Brightness: x{val_mult}\n"
            f"- Total pixels adjusted: {adjusted} across {len(affected)} part(s).\n"
            f"Live viewer updated."
        )

    @server.tool()
    @handle_mcp_errors()
    def skin_shift_hue(
        hue_shift: float,
        part_name: Optional[str] = None,
        target_color: Optional[str] = None,
        tolerance: int = 30,
        layer: str = "both",
    ) -> str:
        """Convenience tool to rotate color hue without altering saturation or brightness."""
        return skin_adjust_hsv(
            part_name=part_name,
            hue_shift=hue_shift,
            sat_mult=1.0,
            val_mult=1.0,
            target_color=target_color,
            tolerance=tolerance,
            layer=layer,
        )

    @server.tool()
    @handle_mcp_errors()
    def skin_set_pixels(
        part_name: str,
        pixels: List[Dict[str, Any]],
    ) -> str:
        """Efficiently set multiple individual pixels on a part in a single call."""
        err = validate_part_name(part_name)
        if err:
            return err
        with session.lock:
            session.push_undo(action=f"set_pixels:{part_name}")
            count = session.canvas.set_pixels(part_name, pixels)
            session.mark_dirty()
        return f"Successfully updated {count} pixel(s) on part '{part_name}'. Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_list_colors(
        part_name: Optional[str] = None,
        top_n: int = 16,
    ) -> str:
        """Inspect unique colors and frequency counts on a specific face or the entire skin canvas."""
        if part_name:
            err = validate_part_name(part_name)
            if err:
                return err
        with session.lock:
            colors = session.canvas.list_colors(part_name=part_name, top_n=top_n)
        target_name = part_name or "entire canvas"
        lines = [f"=== Top Colors on {target_name} ==="]
        for c in colors:
            alpha_note = " (transparent)" if c["alpha"] == 0 else ""
            lines.append(f"  {c['hex']} - RGB: {c['rgb']} | count: {c['count']} px ({c['percentage']}%) {alpha_note}")
        return "\n".join(lines)

    @server.tool()
    @handle_mcp_errors()
    def skin_diff(
        other_file_path: str,
        part_name: Optional[str] = None,
    ) -> str:
        """Compare the current in-memory skin canvas against another skin PNG file."""
        path = os.path.abspath(os.path.expanduser(other_file_path))
        if not os.path.exists(path):
            return f"Error: File not found at '{path}'."
        with session.lock:
            report = session.canvas.diff(path, part_name=part_name)
        status = report["status"].upper()
        lines = [
            f"=== Skin Diff Report: Active Session vs '{os.path.basename(path)}' ===",
            f"Status: {status}",
            f"Total Differing Pixels: {report['total_diff_pixels']}",
            f"Differing Parts: {report['differing_parts_count']} | Identical Parts: {report['identical_parts_count']}",
        ]
        if report["differing_parts"]:
            lines.append("\nDiffering Parts Details:")
            for p in report["differing_parts"]:
                coords = ", ".join(f"({c['x']},{c['y']})" for c in p["sample_coords"][:6])
                lines.append(f"  - {p['part_name']}: {p['diff_pixels']} px differ (coords: {coords})")
        return "\n".join(lines)

    @server.tool()
    @handle_mcp_errors()
    def skin_batch_actions(
        actions: List[Dict[str, Any]],
        return_preview: bool = False,
    ) -> Any:
        """
        Execute multiple skin authoring actions in a single atomic MCP call (1 undo state).
        Supports: set_pixel, set_pixels, set_ascii, replace_color, draw_rect, fill_part,
        paint_region, auto_shade, draw_primitive, adjust_hsv, apply_preset, apply_outfit,
        draw_text, draw_symbol, mirror_limb, add_noise, apply_gradient, align_seams,
        auto_fix, clear_outer_layer.
        Set return_preview=True to also return an inline 3D turnaround image in the same round-trip.
        """
        with session.lock:
            session.push_undo(action=f"batch_actions({len(actions)})")
            summary: List[str] = []
            success_count = 0
            for idx, raw_act in enumerate(actions):
                try:
                    act = BatchActionSchema(**raw_act)
                    a_type = act.action
                    if a_type == "set_pixel":
                        session.canvas.set_pixel(str(act.part_name), int(act.x or 0), int(act.y or 0), normalize_color(act.color))
                        summary.append(f"[{idx+1}] set_pixel on '{act.part_name}' at ({act.x}, {act.y})")
                    elif a_type == "set_pixels":
                        c = session.canvas.set_pixels(str(act.part_name), act.pixels or [])
                        summary.append(f"[{idx+1}] set_pixels on '{act.part_name}': {c} px")
                    elif a_type == "set_ascii":
                        session.canvas.set_ascii(str(act.part_name), str(act.ascii_grid or ""), act.palette or TECHWEAR_CYBERPUNK)
                        summary.append(f"[{idx+1}] set_ascii on '{act.part_name}'")
                    elif a_type == "replace_color":
                        c, aff = session.canvas.replace_color(
                            act.old_color, act.new_color,
                            part_name=act.part_name,
                            tolerance=act.tolerance,
                            layer=act.layer,
                        )
                        summary.append(f"[{idx+1}] replace_color: {c} px across {len(aff)} parts")
                    elif a_type == "draw_rect":
                        session.canvas.draw_rect(
                            str(act.part_name), int(act.x or 0), int(act.y or 0),
                            int(act.width or 1), int(act.height or 1),
                            normalize_color(act.color),
                        )
                        summary.append(f"[{idx+1}] draw_rect on '{act.part_name}'")
                    elif a_type == "fill_part":
                        session.canvas.fill_part(str(act.part_name), normalize_color(act.color))
                        summary.append(f"[{idx+1}] fill_part on '{act.part_name}'")
                    elif a_type == "paint_region":
                        r = paint_region(
                            session.canvas,
                            region=str(act.region or act.target or "torso"),
                            color=act.color,
                            secondary_color=act.secondary_color,
                            pattern=act.pattern,
                            row_start=act.row_start,
                            row_end=act.row_end,
                            include_caps=act.include_caps,
                        )
                        summary.append(f"[{idx+1}] paint_region '{r['region']}' ({r['pixels_painted']} px)")
                    elif a_type == "auto_shade":
                        r = auto_shade_skin(
                            session.canvas,
                            target=str(act.target or act.part_name or "all"),
                            style=str(act.style or "directional"),
                            strength=act.strength,
                            hue_shift_deg=act.hue_shift_deg,
                            dither=act.dither,
                        )
                        summary.append(f"[{idx+1}] auto_shade '{r['target']}' ({r['style']}, {r['shaded_pixels']} px)")
                    elif a_type == "draw_primitive":
                        r = draw_primitive(
                            session.canvas,
                            part_name=str(act.part_name),
                            primitive=str(act.primitive or "line"),
                            x0=int(act.x0 if act.x0 is not None else (act.x or 0)),
                            y0=int(act.y0 if act.y0 is not None else (act.y or 0)),
                            x1=act.x1,
                            y1=act.y1,
                            width=act.width,
                            height=act.height,
                            color=act.color or "#ffffff",
                            secondary_color=act.secondary_color,
                            tolerance=act.tolerance,
                            direction=act.direction if act.direction in ("left_to_right", "right_to_left") else "left_to_right",
                        )
                        summary.append(f"[{idx+1}] draw_primitive '{r['primitive']}' on '{act.part_name}' ({r['pixels_changed']} px)")
                    elif a_type == "adjust_hsv":
                        c, aff = session.canvas.adjust_hsv(
                            part_name=act.part_name,
                            hue_shift=act.hue_shift,
                            sat_mult=act.sat_mult,
                            val_mult=act.val_mult,
                            target_color=act.target_color,
                            tolerance=act.tolerance,
                            layer=act.layer,
                        )
                        summary.append(f"[{idx+1}] adjust_hsv: {c} px across {len(aff)} parts")
                    elif a_type == "apply_preset":
                        execute_preset_on_canvas(session.canvas, str(act.preset_name), act.params)
                        summary.append(f"[{idx+1}] apply_preset '{act.preset_name}'")
                    elif a_type == "apply_outfit":
                        r = apply_outfit(
                            session.canvas,
                            style=str(act.style or "techwear_hoodie"),
                            primary_color=str(act.primary_color or act.color or "#141018"),
                            secondary_color=str(act.secondary_color or "#1c1822"),
                            accent_color=str(act.accent_color or "#af36f8"),
                            trim_color=str(act.trim_color or "#faf8fc"),
                        )
                        summary.append(f"[{idx+1}] apply_outfit '{r['style']}' ({r['parts_modified_count']} parts)")
                    elif a_type == "draw_text":
                        c = draw_text(
                            session.canvas,
                            part_name=str(act.part_name),
                            text=str(act.text or ""),
                            x=int(act.x or 1),
                            y=int(act.y or 1),
                            color=str(act.color or "#ffffff"),
                            spacing=act.spacing,
                        )
                        summary.append(f"[{idx+1}] draw_text '{act.text}' on '{act.part_name}' ({c} px)")
                    elif a_type == "draw_symbol":
                        c = draw_symbol(
                            session.canvas,
                            part_name=str(act.part_name),
                            symbol_name=str(act.symbol_name or "star"),
                            x=int(act.x or 1),
                            y=int(act.y or 1),
                            color=str(act.color or "#ffffff"),
                        )
                        summary.append(f"[{idx+1}] draw_symbol '{act.symbol_name}' on '{act.part_name}' ({c} px)")
                    elif a_type == "mirror_limb":
                        session.canvas.mirror_limb(
                            src_limb=act.src_limb,
                            dst_limb=act.dst_limb,
                            mirror_layer2=act.mirror_layer2,
                        )
                        summary.append(f"[{idx+1}] mirror_limb {act.src_limb} -> {act.dst_limb}")
                    elif a_type == "add_noise":
                        session.canvas.add_noise(str(act.part_name), amount=act.amount)
                        summary.append(f"[{idx+1}] add_noise on '{act.part_name}'")
                    elif a_type == "apply_gradient":
                        session.canvas.apply_gradient(
                            str(act.part_name), act.start_color, act.end_color,
                            direction=act.direction,
                        )
                        summary.append(f"[{idx+1}] apply_gradient on '{act.part_name}'")
                    elif a_type == "align_seams":
                        aligned = align_seams(session.canvas, seam_name=act.seam_name, mode=act.mode)
                        summary.append(f"[{idx+1}] align_seams '{act.seam_name}' ({aligned} px)")
                    elif a_type == "auto_fix":
                        fix_res = auto_fix_skin(session.canvas, default_skin_color=act.default_skin_color, ensure_relief=True)
                        summary.append(
                            f"[{idx+1}] auto_fix (healed {fix_res['healed_layer1_holes']} L1, "
                            f"sanitized {fix_res['sanitized_layer2_pixels']} L2)"
                        )
                    elif a_type == "clear_outer_layer":
                        cleared = session.canvas.clear_layer(layer="outer", parts=act.parts)
                        summary.append(f"[{idx+1}] clear_outer_layer ({cleared} parts)")
                    else:
                        summary.append(f"[{idx+1}] WARNING: Unknown action '{a_type}'")
                        continue
                    success_count += 1
                except Exception as exc:
                    summary.append(f"[{idx+1}] ERROR in action '{raw_act.get('action')}': {str(exc)}")

            session.mark_dirty()
            preview_img = render_3d_turnaround(session.canvas, out_path=None, layer_mode="both") if return_preview else None

        text_out = f"Batch Execution Complete ({success_count}/{len(actions)} succeeded). Live viewer updated:\n" + "\n".join(summary)
        if preview_img is not None:
            return [types.TextContent(type="text", text=text_out), image_to_content(preview_img)]
        return text_out

    @server.tool()
    @handle_mcp_errors()
    def skin_convert_model(target_model: str = "slim") -> str:
        """Convert canvas between 'default' (Steve 4px arms) and 'slim' (Alex 3px arms)."""
        with session.lock:
            session.push_undo(action=f"convert_model:{target_model}")
            res = convert_skin_model(session.canvas, target_model=target_model)
            session.model = session.canvas.model
            session.mark_dirty()
        return f"{res['message']} (status: {res['status']}). Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_mirror_limb(
        src_limb: str = "right_arm",
        dst_limb: str = "left_arm",
        mirror_layer2: bool = True,
    ) -> str:
        """Mirror an entire limb (arm or leg) to the other side."""
        with session.lock:
            session.push_undo(action=f"mirror_limb:{src_limb}->{dst_limb}")
            session.canvas.mirror_limb(src_limb=src_limb, dst_limb=dst_limb, mirror_layer2=mirror_layer2)
            session.mark_dirty()
        return f"Mirrored {src_limb} -> {dst_limb} (with Layer 2: {mirror_layer2}). Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_add_noise(part_name: str, amount: int = 6) -> str:
        """Inject subtle procedural microtexture/noise into a part, preserving transparent pixels."""
        err = validate_part_name(part_name)
        if err:
            return err
        with session.lock:
            session.push_undo(action=f"add_noise:{part_name}")
            session.canvas.add_noise(part_name, amount=amount)
            session.mark_dirty()
        return f"Injected microtexture (amount={amount}) on '{part_name}'. Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_clear_outer_layer(parts: Optional[List[str]] = None) -> str:
        """Clear all Layer 2 (Outer Overlay) parts or specific parts to transparent [0, 0, 0, 0]."""
        with session.lock:
            session.push_undo(action="clear_outer_layer")
            cleared = session.canvas.clear_layer(layer="outer", parts=parts)
            session.mark_dirty()
        return f"Cleared {cleared} outer parts to 100% transparency. Live viewer updated."

    return {
        "skin_get_part_ascii": skin_get_part_ascii,
        "skin_denoise_palette": skin_denoise_palette,
        "skin_import_part": skin_import_part,
        "skin_build": skin_build,
        "skin_set_part_ascii": skin_set_part_ascii,
        "skin_fill_part": skin_fill_part,
        "skin_draw_rect": skin_draw_rect,
        "skin_set_pixel": skin_set_pixel,
        "skin_get_pixel": skin_get_pixel,
        "skin_apply_gradient": skin_apply_gradient,
        "skin_auto_shade": skin_auto_shade,
        "skin_paint_region": skin_paint_region,
        "skin_draw_primitive": skin_draw_primitive,
        "skin_replace_color": skin_replace_color,
        "skin_adjust_hsv": skin_adjust_hsv,
        "skin_shift_hue": skin_shift_hue,
        "skin_set_pixels": skin_set_pixels,
        "skin_list_colors": skin_list_colors,
        "skin_diff": skin_diff,
        "skin_batch_actions": skin_batch_actions,
        "skin_convert_model": skin_convert_model,
        "skin_mirror_limb": skin_mirror_limb,
        "skin_add_noise": skin_add_noise,
        "skin_clear_outer_layer": skin_clear_outer_layer,
    }
