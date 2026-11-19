"""
MCP Resources & Autonomous Agent Workflow Prompts for SkinForge (v2.0.0).
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List

from ..color import PALETTE_REGISTRY
from ..core import MINECRAFT_UV_MAP, OUTER_PARTS
from ..outfits import OUTFIT_STYLES
from ..presets import PRESET_REGISTRY
from ..regions import PRIMITIVE_TYPES, REGION_PARTS, REGION_PATTERNS
from ..shading import SHADING_STYLES, SHADING_TARGET_GROUPS
from .protocol import MCPServer, __version__, types


def register_resources_and_prompts(
    server: MCPServer,
    get_session_info_fn: Callable[[], str],
) -> Dict[str, Any]:
    """Register all MCP resources and workflow prompts."""

    @server.resource("skin://uv-map")
    def get_uv_map_resource() -> str:
        """Complete Minecraft 1.8+ 64x64 dual-layer UV coordinate matrix."""
        lines = ["Face Identifier | Layer | Texture Box (u0, v0, u1, v1) | Dimensions (W x H)"]
        for name, (u0, v0, u1, v1) in MINECRAFT_UV_MAP.items():
            layer = "Outer (Layer 2)" if name in OUTER_PARTS else "Base (Layer 1)"
            lines.append(f"{name:20} | {layer:15} | ({u0:2}, {v0:2}, {u1:2}, {v1:2}) | {u1-u0}x{v1-v0}")
        return "\n".join(lines)

    @server.resource("skin://layer-rules")
    def get_layer_rules_resource() -> str:
        """The 4 Golden Rules of Minecraft Skin Depth."""
        return (
            "THE 4 GOLDEN RULES OF MINECRAFT SKIN DEPTH:\n"
            "-------------------------------------------\n"
            "Rule 1: Layer 1 is 100% Solid (Zero Holes)\n"
            "  - All 36 Base Layer parts MUST have alpha = 255 on every single pixel.\n\n"
            "Rule 2: Layer 2 is Exclusively for 3D Relief (+0.35 Blocks)\n"
            "  - Floats +0.35 blocks outside Layer 1 (optimal 12–45% coverage, never >65%).\n\n"
            "Rule 3: The Floating Cardboard Plane Trap (hat_front Profile Bug)\n"
            "  - On 'hat_front', rows 4 to 7 MUST be 100% transparent across all columns.\n\n"
            "Rule 4: The Floating Plank Trap (hat_top Crown Bug)\n"
            "  - 'hat_top' must either be solid (>=20 pixels) or 100% transparent (never isolated stripes < 20 px)."
        )

    @server.resource("skin://palettes")
    def get_palettes_resource() -> str:
        """JSON representation of all built-in color palettes."""
        return json.dumps(PALETTE_REGISTRY, indent=2)

    @server.resource("skin://session-state")
    def get_session_state_resource() -> str:
        """Real-time diagnostic summary of the active working canvas."""
        return get_session_info_fn()

    @server.resource("skin://regions-and-presets")
    def get_regions_and_presets_resource() -> str:
        """JSON catalog of semantic regions, patterns, shading styles, primitives, outfits, and presets."""
        return json.dumps(
            {
                "regions": sorted(list(REGION_PARTS.keys()) + ["shoes", "hands"]),
                "region_patterns": list(REGION_PATTERNS),
                "shading_styles": list(SHADING_STYLES),
                "shading_targets": sorted(SHADING_TARGET_GROUPS.keys()),
                "primitives": list(PRIMITIVE_TYPES),
                "outfits": list(OUTFIT_STYLES),
                "presets": sorted(PRESET_REGISTRY.keys()),
            },
            indent=2,
        )

    @server.prompt("create-skin")
    def prompt_create_skin() -> List[types.PromptMessage]:
        """Autonomous agent workflow prompt for designing a top-tier skin from scratch."""
        instructions = (
            f"You are an expert Minecraft pixel-art skin artist using SkinForge MCP v{__version__}.\n\n"
            "RECOMMENDED HIGH-CRAFT WORKFLOW (FEWEST CALLS, TOP-TIER QUALITY):\n"
            "1. Plan palette: Call 'skin_generate_palette(seed_color=..., harmony=...)' to get coordinated hue-shifted colors.\n"
            "2. Initialize base: Call 'skin_new(template=\"base_body\", skin_tone=..., hair_color=..., eye_color=...)'.\n"
            "3. Macro composition: Use 'skin_apply_outfit(style=..., primary_color=..., ...)' or 'skin_paint_region(region=..., pattern=...)' to block in clothing & hair across 3D cuboids in 1–2 calls.\n"
            "4. Fine details: Bundle face/accessories/symbols into 'skin_batch_actions' (using 'apply_preset', 'set_ascii', 'draw_primitive' with 'mirror_x', 'mirror_limb').\n"
            "5. Procedural Pixel-Art Shading: Call 'skin_auto_shade(target=\"base\", style=\"directional\", strength=0.35, hue_shift_deg=18)' and 'skin_auto_shade(target=\"hair_cap\", style=\"hair_strands\")' (or 'fabric_folds'/'metallic') to eliminate flat plastic shading.\n"
            "6. Closed-Loop Critique: Call 'skin_critic()' to visually inspect the 3D turnaround AND receive exact fix recipes.\n"
            "7. Polish & Save: Execute any recommended 'skin_align_seams()' / 'skin_auto_fix()', then save with 'skin_save(file_path=...)'."
        )
        return [types.PromptMessage(role="user", content=types.TextContent(type="text", text=instructions))]

    @server.prompt("audit-and-fix-skin")
    def prompt_audit_and_fix() -> List[types.PromptMessage]:
        """Workflow prompt for auditing and fixing an existing skin PNG."""
        instructions = (
            f"You are auditing and upgrading a Minecraft skin using SkinForge MCP v{__version__}.\n\n"
            "STEPS:\n"
            "1. Call 'skin_load(file_path=...)' (legacy 64x32 skins are auto-converted to 64x64).\n"
            "2. Call 'skin_critic()' to inspect the 3D turnaround, 6 craftsmanship metrics, 4 Golden Rules, and exact fix recipes in ONE call.\n"
            "3. Apply the recommended fixes ('skin_auto_fix', 'skin_align_seams', 'skin_auto_shade', or 'skin_denoise_palette').\n"
            "4. Call 'skin_critic()' again to visually verify the upgraded result.\n"
            "5. Save with 'skin_save()'."
        )
        return [types.PromptMessage(role="user", content=types.TextContent(type="text", text=instructions))]

    @server.prompt("restyle-skin")
    def prompt_restyle_skin() -> List[types.PromptMessage]:
        """Workflow prompt for recoloring, reshading, or restyling an existing skin while preserving identity."""
        instructions = (
            f"You are restyling an existing Minecraft skin using SkinForge MCP v{__version__}.\n\n"
            "STEPS:\n"
            "1. Load the skin with 'skin_load(file_path=...)' and save a backup with 'skin_checkpoint(\"original\")'.\n"
            "2. Inspect dominant colors and layout in 1 call via 'skin_inspect_blueprint()'.\n"
            "3. Generate a new cohesive color theme via 'skin_generate_palette(seed_color=..., harmony=...)'.\n"
            "4. Apply targeted recolors via 'skin_replace_color' / 'skin_adjust_hsv', swap clothing via 'skin_apply_outfit' or 'skin_paint_region', and enhance depth via 'skin_auto_shade'.\n"
            "5. Verify with 'skin_critic()' and save with 'skin_save(file_path=...)'."
        )
        return [types.PromptMessage(role="user", content=types.TextContent(type="text", text=instructions))]

    return {
        "get_uv_map_resource": get_uv_map_resource,
        "get_layer_rules_resource": get_layer_rules_resource,
        "get_palettes_resource": get_palettes_resource,
        "get_session_state_resource": get_session_state_resource,
        "get_regions_and_presets_resource": get_regions_and_presets_resource,
        "prompt_create_skin": prompt_create_skin,
        "prompt_audit_and_fix": prompt_audit_and_fix,
        "prompt_restyle_skin": prompt_restyle_skin,
    }
