"""
High-Level Design, Presets, Outfits, Typography, Reference Sampling & Smart Palette MCP Tools (v2.0.0).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ..color import (
    PALETTE_REGISTRY,
    generate_color_ramp,
    generate_harmonious_palette,
)
from ..core import SkinCanvas
from ..outfits import OUTFIT_STYLES, apply_outfit
from ..presets import PRESET_REGISTRY
from ..sampler import sample_image
from ..typography import draw_symbol, draw_text
from .protocol import MCPServer, handle_mcp_errors


def execute_preset_on_canvas(
    canvas: SkinCanvas,
    preset_name: str,
    params: Optional[Dict[str, Any]] = None,
) -> None:
    """Dispatch any registered preset from PRESET_REGISTRY onto a SkinCanvas."""
    key = preset_name.strip().lower()
    if key not in PRESET_REGISTRY:
        raise ValueError(
            f"Unknown preset '{preset_name}'. Supported presets ({len(PRESET_REGISTRY)}): "
            f"{', '.join(sorted(PRESET_REGISTRY.keys()))}."
        )
    fn = PRESET_REGISTRY[key]
    p = dict(params or {})
    fn(canvas, **p)


def register_design_tools(server: MCPServer, session: Any) -> Dict[str, Any]:
    """Register typography, outfit, preset, reference sampling, and smart palette tools."""

    @server.tool()
    @handle_mcp_errors()
    def skin_sample_reference(
        image_path: str,
        x: Optional[float] = None,
        y: Optional[float] = None,
        region: Optional[List[float]] = None,
        num_colors: int = 8,
    ) -> str:
        """Sample exact colors or extract dominant palettes from an image file."""
        path = os.path.abspath(os.path.expanduser(image_path))
        data = sample_image(path, x=x, y=y, region=region, num_colors=num_colors)
        if data["mode"] == "point":
            return (
                f"=== Sampled Point at {data['sample_coord']} in '{os.path.basename(path)}' ===\n"
                f"Hex: {data['hex']}\n"
                f"RGB: {data['rgb']}\n"
                f"RGBA: {data['rgba']}\n"
                f"Perceived Luminance: {data['luminance']}"
            )
        lines = [
            f"=== Extracted Palette from '{os.path.basename(path)}' (Crop: {data['crop_box']}) ===",
            "Colors:",
        ]
        for c in data["colors"]:
            lines.append(f"  '{c['char']}': {c['hex']} (RGB: {c['rgb']}, {c['percentage']}%, role: {c['suggested_role']})")
        lines.append("\nReady-to-use ASCII Palette dictionary:")
        lines.append(json.dumps(data["ascii_palette"], indent=2))
        return "\n".join(lines)

    @server.tool()
    @handle_mcp_errors()
    def skin_draw_text(
        part_name: str,
        text: str,
        x: int = 1,
        y: int = 1,
        color: str = "#ffffff",
        spacing: int = 1,
    ) -> str:
        """Render pixel typography on a UV face using an ultra-crisp 3x5 font matrix."""
        with session.lock:
            session.push_undo(action=f"draw_text:{part_name}:{text}")
            count = draw_text(session.canvas, part_name=part_name, text=text, x=x, y=y, color=color, spacing=spacing)
            session.mark_dirty()
        return f"Rendered text '{text}' on '{part_name}' at ({x}, {y}) using color {color} ({count} pixels drawn). Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_draw_symbol(
        part_name: str,
        symbol_name: str,
        x: int = 1,
        y: int = 1,
        color: str = "#ffffff",
    ) -> str:
        """Render a pixel symbol/emblem on a UV face ('cyber_s', 'heart', 'star', 'lightning', 'skull', 'cross')."""
        with session.lock:
            session.push_undo(action=f"draw_symbol:{part_name}:{symbol_name}")
            count = draw_symbol(session.canvas, part_name=part_name, symbol_name=symbol_name, x=x, y=y, color=color)
            session.mark_dirty()
        return f"Rendered symbol '{symbol_name}' on '{part_name}' at ({x}, {y}) with color {color} ({count} pixels drawn). Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_apply_outfit(
        style: str = "techwear_hoodie",
        primary_color: str = "#141018",
        secondary_color: str = "#1c1822",
        accent_color: str = "#af36f8",
        trim_color: str = "#faf8fc",
    ) -> str:
        """
        Apply a complete coordinated full-body outfit macro across Layer 1 and Layer 2.
        Supported styles: techwear_hoodie, cargo_streetwear, casual_tshirt, fantasy_knight,
        cyber_ninja, formal_suit, cozy_sweater.
        """
        with session.lock:
            session.push_undo(action=f"apply_outfit:{style}")
            res = apply_outfit(
                session.canvas,
                style=style,
                primary_color=primary_color,
                secondary_color=secondary_color,
                accent_color=accent_color,
                trim_color=trim_color,
            )
            session.mark_dirty()
        return (
            f"Applied outfit '{res['style']}' across {res['parts_modified_count']} parts:\n"
            f"- Primary: {primary_color} | Secondary: {secondary_color} | Accent: {accent_color} | Trim: {trim_color}\n"
            f"Live viewer updated."
        )

    @server.tool()
    @handle_mcp_errors()
    def skin_apply_preset(
        preset_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Apply a modular anatomical, facial, or accessory preset.
        Supported presets: anime_eyes_2x2, hoodie_drawstrings, cargo_pocket, hair_bangs,
        sneakers, headphones, visor_glasses, crown, scarf, blush_and_mouth.
        """
        with session.lock:
            session.push_undo(action=f"apply_preset:{preset_name}")
            execute_preset_on_canvas(session.canvas, preset_name, params)
            session.mark_dirty()
        return f"Successfully applied preset '{preset_name}'. Live viewer updated."

    @server.tool()
    @handle_mcp_errors()
    def skin_generate_color_ramp(base_color: str, steps: int = 5) -> str:
        """Generate a harmonious 5-step hue-shifted shading ramp from a single base hex or RGB color."""
        res = generate_color_ramp(base_color, steps=steps)
        lines = [f"Color Ramp for Base '{res['base_hex']}':"]
        for d in res["details"]:
            lines.append(f"  '{d['char']}': {d['hex']} {d['rgba']} (step {d['step']})")
        lines.append(f"\nCopyable ASCII Palette Dict:\n{json.dumps(res['palette'])}")
        return "\n".join(lines)

    @server.tool()
    @handle_mcp_errors(json_output=True)
    def skin_generate_palette(
        seed_color: str,
        harmony: str = "split_complementary",
    ) -> str:
        """
        Generate a complete character palette (primary ramp, secondary, accent, trim, outfit_args,
        and ready-to-use ascii_palette) from a single seed hex color using HSV color harmony theory.
        Harmonies: 'analogous', 'complementary', 'split_complementary', 'triadic', 'monochromatic', 'cyberpunk'.
        """
        res = generate_harmonious_palette(seed_color, harmony=harmony)
        return json.dumps({"status": "success", **res}, indent=2)

    @server.tool()
    @handle_mcp_errors()
    def skin_list_palettes() -> str:
        """List all available built-in color palettes, outfit styles, and modular presets."""
        return (
            "Available Built-in Palettes:\n"
            "- 'TECHWEAR_CYBERPUNK': Syntren theme (obsidian fabrics, neon violet/lavender accents, silver chains).\n"
            "- 'ANIME_SKIN': Curated skin tones ('light', 'base', 'midtone', 'shadow', 'deep').\n"
            "- 'CASUAL_STREETWEAR': Denim blues, cream/white fabrics, leather brown.\n"
            "- 'FANTASY_KNIGHT': Polished steel armor shades with gold trim specular highlights.\n"
            "- 'CYBER_NINJA': Deep navy-slate shinobi fabrics with crimson & electric cyan neon highlights.\n"
            "- 'COZY_PASTEL': Soft sakura pink, mint, cream, and warm cocoa tones.\n\n"
            f"Available Outfit Styles ({len(OUTFIT_STYLES)}): {', '.join(OUTFIT_STYLES)}\n"
            f"Available Presets ({len(PRESET_REGISTRY)}): {', '.join(sorted(PRESET_REGISTRY.keys()))}\n"
            f"Total Registered Palettes: {len(PALETTE_REGISTRY)}"
        )

    return {
        "skin_sample_reference": skin_sample_reference,
        "skin_draw_text": skin_draw_text,
        "skin_draw_symbol": skin_draw_symbol,
        "skin_apply_outfit": skin_apply_outfit,
        "skin_apply_preset": skin_apply_preset,
        "skin_generate_color_ramp": skin_generate_color_ramp,
        "skin_generate_palette": skin_generate_palette,
        "skin_list_palettes": skin_list_palettes,
    }
