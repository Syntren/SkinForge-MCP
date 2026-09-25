"""
SkinForge Model Context Protocol (MCP) Server.
Empowers LLM agents to author, inspect, edit, audit, and visually verify Minecraft 64x64 skins
with dual-layer 3D depth, ASCII DSL reverse-engineering, multimodal feedback, and live WebGL viewing.
"""

import io
import os
import sys
import json
import base64
import subprocess
from typing import Optional, List, Dict, Any
from PIL import Image

import mcp.types as types
from mcp.server.mcpserver import MCPServer

from .canvas import SkinCanvas, MINECRAFT_UV_MAP
from .ascii_codec import normalize_color, rgba_to_hex, part_to_ascii, canvas_to_ascii
from .templates import create_base_body, SKIN_TONE_PALETTES
from .validator import SkinValidator
from .sampler import sample_image
from .renderer import (
    render_composite_2d,
    render_3d_turnaround,
    render_3d_single,
    render_part_zoomed,
    render_bottom_up,
    render_turntable_gif,
)
from .palettes import (
    TECHWEAR_CYBERPUNK,
    ANIME_SKIN,
    CASUAL_STREETWEAR,
    FANTASY_KNIGHT,
    generate_color_ramp,
)
from .presets import (
    draw_anime_eyes_2x2,
    draw_hoodie_drawstrings,
    draw_cargo_pocket,
    draw_hair_bangs,
    draw_sneakers,
    draw_headphones,
)


from .seams import check_seams, align_seams
from .typography import draw_text, draw_symbol
from .outfits import apply_outfit
from .converter import convert_skin_model

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SkinSession:
    """Active in-memory skin canvas session and environment state."""
    def __init__(self):
        self.canvas = SkinCanvas()
        default_skin = os.path.join(PROJECT_ROOT, "skins", "skin_syntren.png")
        custom_skin = os.environ.get("SKINFORGE_DEFAULT_SKIN")
        if custom_skin and os.path.exists(custom_skin):
            default_skin = custom_skin
        self.file_path: Optional[str] = default_skin if os.path.exists(default_skin) else None
        self.is_dirty: bool = False
        self.model: str = "default"  # "default" (Steve 4px) or "slim" (Alex 3px)
        self.viewer_process: Optional[subprocess.Popen] = None
        self.viewer_port: int = int(os.environ.get("SKINFORGE_VIEWER_PORT", "8080"))
        self.project_targets: List[str] = [
            os.path.join(PROJECT_ROOT, "skins", "skin_syntren.png"),
        ]
        if custom_skin and custom_skin not in self.project_targets:
            self.project_targets.append(custom_skin)
        self.live_file: str = os.path.join(PROJECT_ROOT, ".live_skin.png")

        if self.file_path and os.path.exists(self.file_path):
            try:
                self.canvas.load_png(self.file_path)
                self.sync_live()
            except Exception as e:
                sys.stderr.write(f"[SkinForge] Warning loading default skin: {e}\n")
                create_base_body(self.canvas, skin_tone="fair")
        else:
            create_base_body(self.canvas, skin_tone="fair")

    def sync_live(self):
        """Immediately sync current in-memory canvas to live staging file for instant 3D Web viewer display."""
        try:
            os.makedirs(os.path.dirname(self.live_file), exist_ok=True)
            self.canvas.export_png(self.live_file)
            with open(self.live_file + ".model", "w") as f:
                f.write(self.canvas.model)
        except Exception as e:
            sys.stderr.write(f"[SkinForge] Warning syncing live canvas: {e}\n")

    def mark_dirty(self):
        """Mark session dirty and trigger instant live viewer update."""
        self.is_dirty = True
        self.sync_live()

    def reset_blank(self):
        self.canvas = SkinCanvas()
        self.file_path = None
        self.mark_dirty()

    def reset_template(self, skin_tone="fair"):
        self.canvas = SkinCanvas()
        create_base_body(self.canvas, skin_tone=skin_tone)
        self.file_path = None
        self.mark_dirty()


session = SkinSession()

# Load instructions from instructions.md
INSTRUCTIONS_PATH = os.path.join(PROJECT_ROOT, "instructions.md")
if not os.path.exists(INSTRUCTIONS_PATH):
    INSTRUCTIONS_PATH = os.path.join(os.path.dirname(__file__), "instructions.md")

instructions_content = None
if os.path.exists(INSTRUCTIONS_PATH):
    try:
        with open(INSTRUCTIONS_PATH, "r", encoding="utf-8") as f:
            instructions_content = f.read()
    except Exception:
        pass

server = MCPServer(
    name="skinforge",
    instructions=instructions_content,
)


def _image_to_content(im: Image.Image) -> types.ImageContent:
    """Helper to convert PIL Image into an MCP ImageContent object for multimodal LLM feedback."""
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
    return types.ImageContent(type="image", data=b64_str, mime_type="image/png")


# ============================================================================
# 1. SESSION & CANVAS MANAGEMENT TOOLS
# ============================================================================

@server.tool()
def skin_new(
    template: str = "base_body",
    skin_tone: str = "fair",
    hair_color: str = "#221c28",
    eye_color: str = "#9a3cd4"
) -> str:
    """
    Initialize a new active in-memory skin canvas.
    Args:
        template: 'base_body' (recommended: populates a 100% solid Layer 1 humanoid template with 0 holes) or 'blank' (all transparent/empty).
        skin_tone: 'fair', 'tan', 'pale', 'dark', or 'anime'.
        hair_color: Hex color string for hair (e.g. '#221c28').
        eye_color: Hex color string for eye iris (e.g. '#9a3cd4').
    """
    if template == "base_body":
        session.reset_template(skin_tone=skin_tone)
        # Apply hair and eye accents
        session.canvas.draw_rect("head_top", 0, 0, 8, 8, hair_color)
        session.canvas.draw_rect("head_front", 0, 0, 8, 3, hair_color)
        draw_anime_eyes_2x2(session.canvas, row=5, iris_color=eye_color)
        session.file_path = None
        session.mark_dirty()
        return f"Initialized new skin canvas using template 'base_body' (skin_tone='{skin_tone}'). 100% solid Layer 1 (0 holes). Live viewer updated."
    elif template == "blank":
        session.reset_blank()
        return "Initialized new empty skin canvas (all parts transparent). Live viewer updated."
    else:
        return f"Error: Unknown template '{template}'. Choose 'base_body' or 'blank'."


@server.tool()
def skin_load(file_path: str) -> str:
    """
    Load a 64x64 Minecraft skin PNG from disk into the active working session.
    Args:
        file_path: Absolute or relative path to the skin PNG file.
    """
    path = os.path.abspath(os.path.expanduser(file_path))
    if not os.path.exists(path):
        return f"Error: File not found at '{path}'."

    try:
        session.canvas.load_png(path)
        session.file_path = path
        session.is_dirty = False
        session.canvas.history.clear()
        session.canvas.future.clear()
        session.sync_live()
        validator = SkinValidator(path)
        valid, report = validator.validate()
        status = "PASSED quality checks" if valid else "WARNINGS/ERRORS DETECTED"
        return f"Successfully loaded skin from '{path}'.\nAudit Status: {status}.\nLive 3D viewer updated.\n\nAudit Summary:\n{report}"
    except Exception as e:
        return f"Error loading skin from '{path}': {str(e)}"


@server.tool()
def skin_save(
    file_path: Optional[str] = None,
    also_export: Optional[List[str]] = None,
    update_previews: bool = True
) -> str:
    """
    Export the current active canvas to a 64x64 RGBA Minecraft skin PNG file.
    Automatically synchronizes across canonical project targets and regenerates
    2D composite and 3D turnaround previews in one single call.
    Also triggers live auto-reload if the 3D Web viewer is running.
    Args:
        file_path: Primary destination path.
        also_export: Optional list of additional paths to sync simultaneously.
        update_previews: If True (default), automatically renders and saves 'preview_2d.png',
                         'preview_3d_turnaround.png', and 'preview_bottom_up.png' in the target directory.
    """
    target = file_path or session.file_path or os.path.join(PROJECT_ROOT, "skins", "skin_syntren.png")
    target = os.path.abspath(os.path.expanduser(target))
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        session.canvas.export_png(target)
        session.file_path = target
        session.is_dirty = False
        session.sync_live()

        # Combine configured project targets and explicit also_export
        targets_to_sync = set()
        if session.project_targets:
            for pt in session.project_targets:
                targets_to_sync.add(os.path.abspath(os.path.expanduser(pt)))
        if also_export:
            for ep in also_export:
                targets_to_sync.add(os.path.abspath(os.path.expanduser(ep)))
        targets_to_sync.discard(target)

        extra_msgs = []
        for ep_abs in sorted(targets_to_sync):
            try:
                os.makedirs(os.path.dirname(ep_abs), exist_ok=True)
                session.canvas.export_png(ep_abs)
                extra_msgs.append(f"Synced to: '{ep_abs}'")
            except Exception as ex:
                extra_msgs.append(f"Failed sync to '{ep_abs}': {ex}")

        if update_previews:
            base_dir = os.path.dirname(target)
            p_2d = os.path.join(base_dir, "preview_2d.png")
            p_3d = os.path.join(base_dir, "preview_3d_turnaround.png")
            p_bu = os.path.join(base_dir, "preview_bottom_up.png")
            try:
                render_composite_2d(target, p_2d)
                render_3d_turnaround(target, p_3d)
                render_bottom_up(target, p_bu)
                p_gif = os.path.join(base_dir, "turntable_360.gif")
                render_turntable_gif(target, p_gif, frames=16, fps=12)
                extra_msgs.append(f"Rendered previews in: '{base_dir}' (2D composite, 3D turnaround, bottom-up, turntable 360 GIF)")
            except Exception as ex:
                extra_msgs.append(f"Preview render notice: {ex}")

        validator = SkinValidator(target)
        valid, report = validator.validate()
        sync_str = ("\n" + "\n".join(f"[+] {m}" for m in extra_msgs)) if extra_msgs else ""
        return (
            f"Saved 64x64 skin to '{target}' (file size: {os.path.getsize(target)} bytes)."
            f"{sync_str}\n"
            f"Quality Audit: {'PASS' if valid else 'WARNINGS/ISSUES DETECTED'}.\n\n"
            f"{report}"
        )
    except Exception as e:
        return f"Error saving skin to '{target}': {str(e)}"


@server.tool()
def skin_get_session_info() -> str:
    """
    Get detailed metrics and status of the current active working skin session.
    Returns loaded file path, modified status, layer fill percentages, undo history, checkpoints, and viewer status.
    """
    base_parts = [k for k in MINECRAFT_UV_MAP.keys() if not any(x in k for x in ['hat', 'jacket', 'sleeve', 'pants'])]
    outer_parts = [k for k in MINECRAFT_UV_MAP.keys() if any(x in k for x in ['hat', 'jacket', 'sleeve', 'pants'])]

    base_total = 0
    base_opaque = 0
    for p in base_parts:
        part = session.canvas.parts[p]
        base_total += part.shape[0] * part.shape[1]
        base_opaque += int((part[:, :, 3] == 255).sum())

    outer_total = 0
    outer_filled = 0
    for p in outer_parts:
        part = session.canvas.parts[p]
        outer_total += part.shape[0] * part.shape[1]
        outer_filled += int((part[:, :, 3] > 0).sum())

    base_ratio = (base_opaque / base_total * 100.0) if base_total else 0.0
    outer_ratio = (outer_filled / outer_total * 100.0) if outer_total else 0.0

    v_status = "Running" if session.viewer_process and session.viewer_process.poll() is None else "Stopped"
    model_desc = "Classic Steve 4px arm" if session.model == "default" else "Slim Alex 3px arm"
    ckpt_names = ", ".join(session.canvas.checkpoints.keys()) if session.canvas.checkpoints else "none"

    return (
        f"=== SkinForge Active Session Info ===\n"
        f"Loaded File: {session.file_path or '(In-memory canvas)'}\n"
        f"Unsaved Changes: {'Yes' if session.is_dirty else 'No'}\n"
        f"Player Model: {session.model} ({model_desc})\n"
        f"Undo History: {len(session.canvas.history)} step(s) | Redo: {len(session.canvas.future)} step(s)\n"
        f"Checkpoints: {len(session.canvas.checkpoints)} ({ckpt_names})\n"
        f"Layer 1 (Base Body): {base_opaque}/{base_total} opaque pixels ({base_ratio:.1f}% solid)\n"
        f"Layer 2 (3D Relief): {outer_filled}/{outer_total} active pixels ({outer_ratio:.1f}% relief density)\n"
        f"3D Web Viewer: {v_status} (Port {session.viewer_port})\n"
    )


# ============================================================================
# 1B. CANVAS HISTORY & CHECKPOINTS (UNDO / REDO / SNAPSHOTS)
# ============================================================================

@server.tool()
def skin_checkpoint(name: str) -> str:
    """
    Save a named milestone checkpoint of the active canvas state.
    Allows LLMs to experiment freely and instantly roll back if needed.
    Args:
        name: Name of the checkpoint (e.g. 'before_hair_redesign', 'base_colors_done').
    """
    count = session.canvas.create_checkpoint(name)
    return f"Created checkpoint '{name}'. Total checkpoints saved: {count}."


@server.tool()
def skin_restore_checkpoint(name: str) -> str:
    """
    Restore the canvas to a previously saved named checkpoint.
    Automatically creates an undo state before restoring and updates the live viewer.
    Args:
        name: Name of checkpoint to restore.
    """
    if name not in session.canvas.checkpoints:
        available = list(session.canvas.checkpoints.keys())
        return f"Error: Checkpoint '{name}' not found. Available checkpoints: {available}"

    session.canvas.restore_checkpoint(name)
    session.mark_dirty()
    return f"Successfully restored canvas to checkpoint '{name}'. Live viewer updated."


@server.tool()
def skin_undo() -> str:
    """
    Undo the last modification made to the active skin canvas.
    Instantly updates the live 3D viewer.
    """
    if session.canvas.undo():
        session.mark_dirty()
        remaining = len(session.canvas.history)
        return f"Undid last action. Canvas reverted to previous state ({remaining} undo steps remaining in history). Live viewer updated."
    return "Nothing to undo. Undo history is empty."


@server.tool()
def skin_redo() -> str:
    """
    Reapply the last undone modification to the active skin canvas.
    Instantly updates the live 3D viewer.
    """
    if session.canvas.redo():
        session.mark_dirty()
        remaining = len(session.canvas.future)
        return f"Redid previous action ({remaining} redo steps remaining in future history). Live viewer updated."
    return "Nothing to redo. Redo history is empty."


# ============================================================================
# 2. VISUAL RENDERING & MULTIMODAL VERIFICATION TOOLS
# ============================================================================

@server.tool()
def skin_render_3d(
    preset: str = "turnaround",
    yaw_deg: float = -30.0,
    pitch_deg: float = 15.0,
    layer_mode: str = "both",
    save_path: Optional[str] = None
) -> List[types.ContentBlock]:
    """
    Render a 3D Z-buffered rasterized model of the skin and return it directly as an image for visual verification.
    Args:
        preset: 'turnaround' (4 angles: Front 3/4, Left profile, Back 3/4, Back straight),
                'front', 'back', 'left_profile' (Rule 3 check), 'right_profile', 'bottom_up' (Rule 4 chin/hood check), or 'custom'.
        yaw_deg: Camera horizontal angle if preset is 'custom' (degrees).
        pitch_deg: Camera vertical angle if preset is 'custom' (degrees).
        layer_mode: 'both' (default), 'base' (Layer 1 only), or 'outer' (Layer 2 only).
        save_path: Optional file path to also save the rendered PNG on disk.
    """
    layer_mode = layer_mode.lower()
    if layer_mode not in ("both", "base", "outer"):
        layer_mode = "both"

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
        out = os.path.abspath(os.path.expanduser(save_path))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        img.save(out)
        saved_msg = f"\nSaved image to: '{out}'"

    return [
        types.TextContent(type="text", text=f"Rendered {desc}.{saved_msg}\nInspect the visual output below:"),
        _image_to_content(img)
    ]


@server.tool()
def skin_render_2d(
    layer_mode: str = "both",
    scale: int = 16,
    save_path: Optional[str] = None
) -> List[types.ContentBlock]:
    """
    Render front and back 2D composite view with Layer 2 overlaid and return as an image.
    Args:
        layer_mode: 'both' (composite) or 'flat_uv'.
        scale: Upscaling factor (default 16, produces a crisp 576x576 image).
        save_path: Optional path to save the 2D composite on disk.
    """
    img = render_composite_2d(session.canvas, out_path=None, scale=scale)
    saved_msg = ""
    if save_path:
        out = os.path.abspath(os.path.expanduser(save_path))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        img.save(out)
        saved_msg = f"\nSaved composite to: '{out}'"

    return [
        types.TextContent(type="text", text=f"Rendered 2D Composite (Front and Back with Layer 2 overlay).{saved_msg}"),
        _image_to_content(img)
    ]


@server.tool()
def skin_render_part(
    part_name: str,
    scale: int = 16,
    show_grid: bool = True,
    save_path: Optional[str] = None
) -> List[types.ContentBlock]:
    """
    Render an individual UV part face enlarged (e.g. 16x) with a pixel grid for micro-inspection.
    Args:
        part_name: Exact part face name (e.g. 'head_front', 'hat_front', 'jacket_back', 'body_front').
        scale: Zoom level per pixel (default 16).
        show_grid: Whether to draw subtle grid lines separating individual pixels.
        save_path: Optional path to save image.
    """
    if part_name not in MINECRAFT_UV_MAP:
        return [types.TextContent(type="text", text=f"Error: Unknown part '{part_name}'. Valid parts: {list(MINECRAFT_UV_MAP.keys())}")]

    img = render_part_zoomed(session.canvas, part_name, scale=scale, show_grid=show_grid, out_path=None)
    saved_msg = ""
    if save_path:
        out = os.path.abspath(os.path.expanduser(save_path))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        img.save(out)
        saved_msg = f"\nSaved to: '{out}'"

    h, w, _ = session.canvas.parts[part_name].shape
    return [
        types.TextContent(type="text", text=f"Zoomed view of part '{part_name}' ({w}x{h} px, scale={scale}x).{saved_msg}"),
        _image_to_content(img)
    ]


@server.tool()
def skin_render_turntable_gif(
    frames: int = 16,
    fps: int = 12,
    layer_mode: str = "both",
    out_path: Optional[str] = None
) -> List[Any]:
    """
    Generate an animated 360-degree turntable rotation GIF of the player model.
    Args:
        frames: Number of rotation frames (default 16).
        fps: Animation frames per second (default 12).
        layer_mode: 'both', 'base', or 'outer'.
        out_path: Output path for GIF (defaults to project output directory or 'previews/turntable_360.gif').
    """
    if not out_path and session.file_path:
        out = os.path.join(os.path.dirname(session.file_path), "turntable_360.gif")
    else:
        out = out_path or os.path.join(PROJECT_ROOT, "previews", "turntable_360.gif")
    out = os.path.abspath(os.path.expanduser(out))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        render_turntable_gif(session.canvas, out, frames=frames, fps=fps, layer_mode=layer_mode)
        with open(out, "rb") as f:
            b64_str = base64.b64encode(f.read()).decode("utf-8")
        return [
            types.TextContent(type="text", text=f"Successfully generated {frames}-frame turntable GIF at: '{out}' ({os.path.getsize(out)} bytes)."),
            types.ImageContent(type="image", data=b64_str, mime_type="image/gif")
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error generating turntable GIF: {str(e)}")]


# ============================================================================
# 3. DRAWING & PART MANIPULATION TOOLS (LLM ERGONOMIC)
# ============================================================================

@server.tool()
def skin_get_part_ascii(part_name: str, tolerance: int = 6) -> str:
    """
    Reverse-engineer an existing part's pixels into a clean ASCII grid string and palette dictionary.
    Allows LLMs to inspect what is currently drawn on any face and perform incremental edits.
    Args:
        part_name: Name of face (e.g. 'head_front', 'hat_front', 'jacket_back', 'body_front').
        tolerance: Color grouping threshold (default 6).
    """
    if part_name not in MINECRAFT_UV_MAP:
        return f"Error: Unknown part '{part_name}'. Valid parts: {list(MINECRAFT_UV_MAP.keys())}"

    part_arr = session.canvas.parts[part_name]
    h, w, _ = part_arr.shape
    grid, palette = part_to_ascii(part_arr, tolerance=tolerance)

    pal_lines = []
    for ch, rgba in sorted(palette.items()):
        hex_c = rgba_to_hex(rgba)
        pal_lines.append(f"  '{ch}': {rgba}  # {hex_c}")

    pal_str = "\n".join(pal_lines)
    return (
        f"=== Part: {part_name} ({w}x{h} px) ===\n"
        f"Palette:\n"
        f"{pal_str}\n\n"
        f"ASCII Grid:\n"
        f"{grid}\n\n"
        f"To edit this part: Modify the characters in the grid above and call 'skin_set_part_ascii'."
    )




@server.tool()
def skin_search(
    query: str,
    limit: int = 5,
    min_quality: str = "medium",
    render_previews: bool = True
) -> str:
    """
    Search across 900,000+ captioned Minecraft skins using BM25 relevance ranking.
    Returns matching skin IDs, descriptive captions, palette colors, and on-the-fly 3D turnaround previews.

    Args:
        query: Search keywords or visual description (e.g. 'cyberpunk samurai', 'purple scarf ninja', 'medieval knight', 'goth girl').
        limit: Number of candidate skins to return (default: 5, max: 20).
        render_previews: Whether to render 3D turnaround previews for visual inspection (default: True).
    """
    from .rag import get_rag
    rag = get_rag()
    if rag.count() == 0:
        return json.dumps({
            "status": "db_not_initialized",
            "message": "The RAG database is empty or not yet indexed. Run 'python scripts/ingest_full_dataset.py' or use built-in procedural templates and outfits.",
            "results": []
        }, indent=2)

    results = rag.search(query=query, limit=min(limit, 20), min_quality=min_quality, render_previews=render_previews)
    if not results:
        return json.dumps({
            "status": "empty",
            "message": f"No skins found matching query: '{query}'. Total skins in DB: {rag.count()}",
            "results": []
        }, indent=2)

    return json.dumps({
        "status": "success",
        "query": query,
        "total_results": len(results),
        "results": results
    }, indent=2)


@server.tool()
def skin_get_reference(
    skin_id: str,
    load_to_canvas: bool = False,
    as_ascii: bool = True
) -> str:
    """
    Retrieve full details for a reference skin by ID from the 900k dataset.
    Can load the skin directly into the active editing session and/or return its ASCII parts and palette.

    Args:
        skin_id: Unique identifier of the skin (from skin_search).
        load_to_canvas: If True, replaces the current active session skin with this reference skin (default: False).
        as_ascii: If True, returns full 2D ASCII grids for all parts and the color palette (default: True).
    """
    from .rag import get_rag
    rag = get_rag()
    skin_data = rag.get_skin(skin_id, as_canvas=load_to_canvas, as_ascii=as_ascii)
    if not skin_data:
        return json.dumps({"error": f"Skin '{skin_id}' not found in RAG database."})

    if load_to_canvas and "canvas" in skin_data:
        session.canvas = skin_data["canvas"]
        session.model = skin_data.get("model_type", "default")
        session.mark_dirty()

    resp = {
        "skin_id": skin_data["skin_id"],
        "title": skin_data.get("title"),
        "caption": skin_data.get("caption"),
        "model_type": skin_data.get("model_type", "default"),
        "loaded_to_active_canvas": load_to_canvas
    }
    if as_ascii:
        resp["palette"] = skin_data.get("palette")
        resp["parts"] = skin_data.get("parts")

    return json.dumps(resp, indent=2)


@server.tool()
def skin_remix(
    base_skin_id: str,
    overlay_skin_id: str,
    parts_to_take: Optional[List[str]] = None,
    auto_fix: bool = True,
    save_path: Optional[str] = None
) -> str:
    """
    Remix two reference skins from the 900k dataset:
    Takes the base body/armor from base_skin and overlays accessories/parts from overlay_skin.
    Loads the remixed result into the active session canvas.

    Args:
        base_skin_id: ID of the base skin (provides primary body and clothing).
        overlay_skin_id: ID of the overlay skin (provides accessories, hats, jackets, or scarves).
        parts_to_take: Specific UV parts to transfer (default: all Layer 2 outer parts like hat, jacket, sleeves, pants).
        auto_fix: Automatically heal Layer 1 holes and sanitize Layer 2 (default: True).
        save_path: Optional path to save the resulting skin PNG.
    """
    from .rag import get_rag
    rag = get_rag()
    try:
        remixed_canvas, info = rag.remix_skins(
            base_skin_id=base_skin_id,
            overlay_skin_id=overlay_skin_id,
            parts_to_take=parts_to_take,
            auto_fix=auto_fix,
            save_path=save_path
        )
        session.canvas = remixed_canvas
        session.mark_dirty()
        return json.dumps({
            "status": "success",
            "message": f"Successfully remixed '{base_skin_id}' with '{overlay_skin_id}'.",
            "preview_3d_path": info.get("preview_3d"),
            "saved_to": save_path
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@server.tool()
def skin_rag_status() -> str:
    """
    Get the status of the SkinForge RAG database (number of indexed skins, database path).
    """
    import os
    from .rag import get_rag
    rag = get_rag()
    return json.dumps({
        "status": "ready" if rag.count() > 0 else "empty",
        "total_indexed_skins": rag.count(),
        "database_path": str(rag.db_path),
        "database_size_mb": round(os.path.getsize(rag.db_path) / (1024 * 1024), 2) if os.path.exists(rag.db_path) else 0
    }, indent=2)

@server.tool()
def skin_part_search(
    category: str,
    query: str,
    limit: int = 5,
    min_quality: str = "medium",
    render_previews: bool = True
) -> str:
    """
    Search for specific anatomical components (hair, face, torso, arms, legs, outfit)
    and render isolated 3D component previews on a neutral mannequin for modular Lego assembly.

    Args:
        category: Anatomical module ('hair', 'face', 'torso', 'arms', 'legs', 'head', 'outfit').
        query: Descriptive keywords (e.g. 'anime messy bangs', 'business suit tie', 'sneakers').
        limit: Max candidates to return (default: 5).
        min_quality: 'all', 'low', 'medium', or 'high'.
        render_previews: Whether to render isolated 3D previews on mannequin (default: True).
    """
    from .rag import get_rag
    rag = get_rag()
    if rag.count() == 0:
        return json.dumps({
            "status": "db_not_initialized",
            "message": "The RAG database is empty or not yet indexed. Run 'python scripts/ingest_full_dataset.py' to populate it.",
            "results": []
        }, indent=2)
    try:
        results = rag.part_search(
            category=category,
            query=query,
            limit=limit,
            min_quality=min_quality,
            render_previews=render_previews
        )
        return json.dumps({
            "status": "success",
            "category": category,
            "query": query,
            "total_results": len(results),
            "results": results
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@server.tool()
def skin_assemble(
    components: Dict[str, str],
    auto_blend_seams: bool = True,
    auto_fix: bool = True
) -> str:
    """
    Lego Constructor: Assemble a complete Minecraft skin from modular component sources.
    Loads the assembled skin directly into the active editing session with boundary seam blending.

    Args:
        components: Dict mapping module names ('hair', 'face', 'torso', 'arms', 'legs', 'outfit')
                    to either a RAG skin_id (e.g. 'skin21181765flamez-suit') or 'active' (to keep current part).
        auto_blend_seams: Automatically blend texture seams across anatomical joints (default: True).
        auto_fix: Automatically heal Layer 1 holes and sanitize Layer 2 depth (default: True).
    """
    from .rag import get_rag
    rag = get_rag()
    try:
        resolved_components = {}
        for mod, src in components.items():
            if src == "active":
                resolved_components[mod] = session.canvas
            else:
                resolved_components[mod] = src

        assembled_canvas, summary = rag.assemble_modules(
            components=resolved_components,
            base_canvas=session.canvas,
            auto_blend_seams=auto_blend_seams,
            auto_fix=auto_fix
        )
        session.canvas = assembled_canvas
        session.mark_dirty()

        return json.dumps({
            "status": "success",
            "message": f"Successfully assembled skin from {list(components.keys())}.",
            "summary": summary,
            "preview_3d_path": summary.get("preview_3d_path")
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@server.tool()
def skin_search_by_image(
    image_path: str,
    limit: int = 5,
    min_quality: str = "medium",
    render_previews: bool = True
) -> str:
    """
    Visual Reference Search: Find Minecraft skins that visually match a concept art image,
    reference photo, or character drawing using spatial-color pyramid feature matching (LAB color space).

    Args:
        image_path: Absolute or relative path to reference image on disk.
        limit: Number of visually similar candidate skins to return (default: 5).
        min_quality: 'all', 'low', 'medium', or 'high'.
        render_previews: Whether to render 3D turnaround previews (default: True).
    """
    import os
    if not os.path.exists(image_path):
        return json.dumps({"error": f"Reference image not found: {image_path}"})

    from .rag import get_rag
    rag = get_rag()
    try:
        results = rag.search_by_image(
            image_input=image_path,
            limit=limit,
            min_quality=min_quality,
            render_previews=render_previews
        )
        return json.dumps({
            "status": "success",
            "query_image": image_path,
            "total_results": len(results),
            "results": results
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})




@server.tool()
def skin_denoise_palette(
    min_pixel_count: int = 3,
    part_name: Optional[str] = None
) -> str:
    """
    Automatically clean up compression noise and isolated color artifacts.
    Replaces pixels that appear fewer than `min_pixel_count` times with their
    closest dominant palette color, achieving clean pixel-art aesthetics.
    
    Args:
        min_pixel_count: Minimum times a color must appear to be considered legitimate palette color (default: 3).
        part_name: Optional part to limit denoising to (or None for entire skin).
    """
    try:
        modified = session.canvas.denoise_palette(min_pixel_count=min_pixel_count, part_name=part_name)
        session.mark_dirty()
        colors = session.canvas.list_colors(top_n=100)
        return json.dumps({
            "status": "success",
            "modified_pixels": modified,
            "current_unique_colors": len(colors),
            "message": f"Denoised palette: healed {modified} artifact pixels. Unique colors now: {len(colors)}."
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@server.tool()
def skin_import_part(
    source: str,
    part_name: str,
    target_part_name: Optional[str] = None
) -> str:
    """
    Import an individual anatomical part from an external skin (file path or RAG skin_id)
    directly into the active editing session.
    
    Args:
        source: External skin PNG file path OR RAG skin_id (e.g. 'skin_syntren_tuxedo.png' or '019a5f6e...').
        part_name: Name of the part to import (e.g. 'head_front', 'hat_front', 'jacket_front').
        target_part_name: Optional target part name (defaults to same as part_name).
    """
    from .canvas import MINECRAFT_UV_MAP, SkinCanvas
    from .rag import get_rag
    
    if part_name not in MINECRAFT_UV_MAP:
        return json.dumps({"error": f"Invalid part_name: '{part_name}'"})
        
    dst_name = target_part_name or part_name
    if dst_name not in MINECRAFT_UV_MAP:
        return json.dumps({"error": f"Invalid target_part_name: '{dst_name}'"})
        
    try:
        src_canvas = SkinCanvas()
        if os.path.exists(source):
            src_canvas.load_png(source)
        else:
            rag = get_rag()
            s_data = rag.get_skin(source, as_canvas=True, as_ascii=False)
            if not s_data or "canvas" not in s_data:
                return json.dumps({"error": f"Source '{source}' is neither a valid file path nor an existing skin_id"})
            src_canvas = s_data["canvas"]
            
        session.canvas.push_undo()
        session.canvas.set_part(dst_name, src_canvas.get_part(part_name))
        session.mark_dirty()
        
        return json.dumps({
            "status": "success",
            "message": f"Successfully imported '{part_name}' from '{source}' into '{dst_name}'. Live viewer updated."
        })
    except Exception as e:
        return json.dumps({"error": str(e)})



@server.tool()
def skin_build(
    palette: Dict[str, str],
    parts: Dict[str, str],
    model_type: str = "default",
    auto_fix: bool = True,
    save_path: Optional[str] = None
) -> str:
    """
    Generate and assemble a complete 64x64 dual-layer Minecraft skin in a single atomic tool call
    using an ASCII grid for each UV face with a shared color palette.

    Args:
        palette: Mapping from symbol characters to hex colors (e.g. {"#": "#1a1422", "=": "#4d3d5f", ".": "transparent"}).
        parts: Dictionary of non-empty UV parts mapped to multiline ASCII grid strings (e.g. {"head_front": "...", "jacket_front": "..."}).
        model_type: Player model geometry ("default" for Steve 4px arms, "slim" for Alex 3px arms).
        auto_fix: Automatically heal Layer 1 holes (Rule 1) and sanitize Layer 2 floating profile pixels (Rule 2 & 3).
        save_path: Optional file path to immediately export the 64x64 PNG and update turnaround previews.
    """
    session.canvas.push_undo()
    session.canvas.model = model_type

    session.canvas.apply_ascii_skin(palette, parts)

    fix_summary = []
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
        save_res = skin_save(file_path=save_path, update_previews=True)
        msg += f" {save_res}"
    return msg

@server.tool()
def skin_set_part_ascii(
    part_name: str,
    ascii_grid: str,
    palette: Optional[Dict[str, Any]] = None,
    palette_name: Optional[str] = None
) -> str:
    """
    Draw a part using a multiline ASCII grid.
    Automatically handles 8-row vs 12-row/4-row scaling.
    Args:
        part_name: Target part (e.g. 'head_front', 'hat_front', 'body_front', 'jacket_front').
        ascii_grid: Multiline string where characters map to colors. Whitespace is stripped.
        palette: Dictionary mapping characters to hex strings (e.g. {'#': '#1a1422', '.': 'transparent'}) or RGBA lists.
        palette_name: Optional built-in palette name ('TECHWEAR_CYBERPUNK', 'ANIME_SKIN', 'CASUAL_STREETWEAR', 'FANTASY_KNIGHT').
    """
    if part_name not in MINECRAFT_UV_MAP:
        return f"Error: Unknown part '{part_name}'. Valid parts: {list(MINECRAFT_UV_MAP.keys())}"

    chosen_palette = palette or {}
    if isinstance(chosen_palette, str):
        import json
        try:
            chosen_palette = json.loads(chosen_palette)
        except Exception:
            pass
    if palette_name:
        p_name = palette_name.upper().strip()
        if p_name in ("TECHWEAR", "CYBERPUNK", "TECHWEAR_CYBERPUNK"):
            chosen_palette = {**TECHWEAR_CYBERPUNK, **chosen_palette}
        elif p_name in ("ANIME", "ANIME_SKIN"):
            chosen_palette = {**ANIME_SKIN, **chosen_palette}
        elif p_name in ("CASUAL", "CASUAL_STREETWEAR", "STREETWEAR"):
            chosen_palette = {**CASUAL_STREETWEAR, **chosen_palette}
        elif p_name in ("FANTASY", "FANTASY_KNIGHT", "KNIGHT"):
            chosen_palette = {**FANTASY_KNIGHT, **chosen_palette}
        else:
            return f"Error: Unknown palette_name '{palette_name}'. Use 'TECHWEAR_CYBERPUNK', 'ANIME_SKIN', 'CASUAL_STREETWEAR', 'FANTASY_KNIGHT', or pass a palette dict."

    if not chosen_palette:
        chosen_palette = TECHWEAR_CYBERPUNK

    try:
        session.canvas.push_undo()
        session.canvas.set_ascii(part_name, ascii_grid, chosen_palette)
        session.mark_dirty()
        h, w, _ = session.canvas.parts[part_name].shape
        return f"Successfully updated '{part_name}' ({w}x{h} px) using ASCII grid. Live viewer updated."
    except Exception as e:
        return f"Error applying ASCII grid to '{part_name}': {str(e)}"


@server.tool()
def skin_fill_part(part_name: str, color: str) -> str:
    """
    Fill an entire UV face with a solid color.
    Args:
        part_name: Target part name (e.g. 'jacket_front', 'head_top').
        color: Hex string (e.g. '#201624', '#ff00aa', 'transparent') or RGBA list.
    """
    if part_name not in MINECRAFT_UV_MAP:
        return f"Error: Unknown part '{part_name}'."
    try:
        session.canvas.push_undo()
        session.canvas.fill_part(part_name, color)
        session.mark_dirty()
        return f"Filled '{part_name}' with {color}. Live viewer updated."
    except Exception as e:
        return f"Error filling part: {str(e)}"


@server.tool()
def skin_draw_rect(
    part_name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    color: str
) -> str:
    """
    Draw a filled rectangle on a part.
    Args:
        part_name: Target part name.
        x: Top-left X coordinate within the part (0-indexed).
        y: Top-left Y coordinate within the part (0-indexed).
        width: Rectangle width in pixels.
        height: Rectangle height in pixels.
        color: Hex color string (e.g. '#be50fa') or RGBA list.
    """
    if part_name not in MINECRAFT_UV_MAP:
        return f"Error: Unknown part '{part_name}'."
    try:
        session.canvas.push_undo()
        session.canvas.draw_rect(part_name, x, y, width, height, color)
        session.mark_dirty()
        return f"Drawn rect at ({x}, {y}) of size {width}x{height} on '{part_name}' with color {color}. Live viewer updated."
    except Exception as e:
        return f"Error drawing rect: {str(e)}"


@server.tool()
def skin_set_pixel(part_name: str, x: int, y: int, color: str) -> str:
    """
    Set an individual pixel on a UV part.
    Args:
        part_name: Target part name.
        x: X coordinate (0-indexed).
        y: Y coordinate (0-indexed).
        color: Hex string (e.g. '#9a3cd4') or RGBA list.
    """
    if part_name not in MINECRAFT_UV_MAP:
        return f"Error: Unknown part '{part_name}'."
    try:
        session.canvas.push_undo()
        session.canvas.set_pixel(part_name, x, y, color)
        session.mark_dirty()
        return f"Set pixel ({x}, {y}) on '{part_name}' to {color}. Live viewer updated."
    except Exception as e:
        return f"Error setting pixel: {str(e)}"


@server.tool()
def skin_get_pixel(part_name: str, x: int, y: int) -> str:
    """
    Get the color of an individual pixel on a UV part.
    """
    if part_name not in MINECRAFT_UV_MAP:
        return f"Error: Unknown part '{part_name}'."
    try:
        rgba = session.canvas.get_pixel(part_name, x, y)
        hex_c = rgba_to_hex(rgba)
        return f"Pixel at ({x}, {y}) on '{part_name}': {rgba} ({hex_c})"
    except Exception as e:
        return f"Error getting pixel: {str(e)}"


@server.tool()
def skin_apply_gradient(
    part_name: str,
    start_color: str,
    end_color: str,
    direction: str = "vertical"
) -> str:
    """
    Apply a smooth linear color gradient across a part.
    Args:
        part_name: Target part name.
        start_color: Beginning color (top for vertical, left for horizontal).
        end_color: Ending color (bottom for vertical, right for horizontal).
        direction: 'vertical' or 'horizontal'.
    """
    if part_name not in MINECRAFT_UV_MAP:
        return f"Error: Unknown part '{part_name}'."
    try:
        session.canvas.push_undo()
        session.canvas.apply_gradient(part_name, start_color, end_color, direction=direction)
        session.mark_dirty()
        return f"Applied {direction} gradient ({start_color} -> {end_color}) on '{part_name}'. Live viewer updated."
    except Exception as e:
        return f"Error applying gradient: {str(e)}"


@server.tool()
def skin_sample_reference(
    image_path: str,
    x: Optional[float] = None,
    y: Optional[float] = None,
    region: Optional[List[float]] = None,
    num_colors: int = 8
) -> str:
    """
    Sample exact colors or extract dominant palettes from an image file (PNG, JPEG, WebP)
    such as concept art, turnaround sheets, or reference skins.
    Eliminates the need for LLMs to run external Python scripts to inspect reference art.
    Args:
        image_path: Absolute or relative path to image file (e.g. 'Reference Skin/reference.jpeg').
        x: Optional point X coordinate (int pixel or 0.0-1.0 percentage of width).
        y: Optional point Y coordinate (int pixel or 0.0-1.0 percentage of height).
        region: Optional bounding box [x0, y0, x1, y1] to crop (pixels or 0.0-1.0 percentages).
        num_colors: Number of dominant colors to extract (default 8).
    """
    path = os.path.abspath(os.path.expanduser(image_path))
    try:
        data = sample_image(path, x=x, y=y, region=region, num_colors=num_colors)
        if data["mode"] == "point":
            return (
                f"=== Sampled Point at {data['sample_coord']} in '{os.path.basename(path)}' ===\n"
                f"Hex: {data['hex']}\n"
                f"RGB: {data['rgb']}\n"
                f"RGBA: {data['rgba']}\n"
                f"Perceived Luminance: {data['luminance']}"
            )
        else:
            lines = [
                f"=== Extracted Palette from '{os.path.basename(path)}' (Crop: {data['crop_box']}) ===",
                "Colors:"
            ]
            for c in data["colors"]:
                lines.append(f"  '{c['char']}': {c['hex']} (RGB: {c['rgb']}, {c['percentage']}%, role: {c['suggested_role']})")
            lines.append("\nReady-to-use ASCII Palette dictionary:")
            lines.append(json.dumps(data["ascii_palette"], indent=2))
            return "\n".join(lines)
    except Exception as e:
        return f"Error sampling reference image '{path}': {str(e)}"


@server.tool()
def skin_replace_color(
    old_color: str,
    new_color: str,
    part_name: Optional[str] = None,
    tolerance: int = 15,
    layer: str = "both"
) -> str:
    """
    Fuzzy replace occurrences of old_color with new_color within an RGB tolerance threshold.
    Allows LLMs to perform color tweaks (e.g. 'make the purple eyes brighter' or 'change trim color')
    in a single tool call without sending massive ASCII grids.
    Args:
        old_color: Target color to match (hex e.g. '#9a3cd4' or RGBA list).
        new_color: Replacement color (hex e.g. '#af36f8' or RGBA list).
        part_name: Optional specific face name (e.g. 'head_front') or None/'all' for the whole skin.
        tolerance: Euclidean RGB color distance threshold (default 15).
        layer: 'both', 'base' (Layer 1 only), or 'outer' (Layer 2 only).
    """
    try:
        session.canvas.push_undo()
        count, affected = session.canvas.replace_color(
            old_color=old_color,
            new_color=new_color,
            part_name=part_name,
            tolerance=tolerance,
            layer=layer
        )
        session.mark_dirty()
        return (
            f"Successfully replaced color {old_color} -> {new_color} (tolerance={tolerance}):\n"
            f"- Total pixels replaced: {count}\n"
            f"- Affected parts ({len(affected)}): {', '.join(affected) if affected else 'none'}\n"
            f"Live viewer updated."
        )
    except Exception as e:
        return f"Error replacing color: {str(e)}"


@server.tool()
def skin_adjust_hsv(
    part_name: Optional[str] = None,
    hue_shift: float = 0.0,
    sat_mult: float = 1.0,
    val_mult: float = 1.0,
    target_color: Optional[str] = None,
    tolerance: int = 30,
    layer: str = "both"
) -> str:
    """
    Vectorized Hue, Saturation, and Brightness adjustment across part(s) or entire skin (< 1ms).
    Can optionally target only pixels matching a specific color within an RGB tolerance threshold.
    Args:
        part_name: Face name (e.g. 'head_front', 'hat_front') or None/'all' for whole skin.
        hue_shift: Degrees to rotate hue (-180..+180 or 0..360). E.g. +120 shifts purple -> green/cyan.
        sat_mult: Saturation multiplier (0.0 = grayscale, 1.0 = unchanged, 1.5 = +50% more vivid).
        val_mult: Value/Brightness multiplier (0.8 = 20% darker, 1.2 = 20% brighter).
        target_color: Optional hex or RGBA color to selectively adjust only matching pixels (e.g. '#9a3cd4').
        tolerance: Euclidean distance threshold for target_color filter (default 30).
        layer: 'both', 'base' (Layer 1 only), or 'outer' (Layer 2 only).
    """
    try:
        session.canvas.push_undo()
        adjusted, affected = session.canvas.adjust_hsv(
            part_name=part_name,
            hue_shift=hue_shift,
            sat_mult=sat_mult,
            val_mult=val_mult,
            target_color=target_color,
            tolerance=tolerance,
            layer=layer
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
    except Exception as e:
        return f"Error adjusting HSV: {str(e)}"


@server.tool()
def skin_shift_hue(
    hue_shift: float,
    part_name: Optional[str] = None,
    target_color: Optional[str] = None,
    tolerance: int = 30,
    layer: str = "both"
) -> str:
    """
    Convenience tool to rotate color hue (e.g. shift purple accents to neon cyan or red)
    without altering saturation or brightness.
    Args:
        hue_shift: Degrees to rotate hue (-180..+180 or 0..360).
        part_name: Specific face or None for entire skin.
        target_color: Optional hex color to only shift matching accents (e.g. '#af36f8').
        tolerance: RGB distance threshold (default 30).
        layer: 'both', 'base', or 'outer'.
    """
    return skin_adjust_hsv(
        part_name=part_name,
        hue_shift=hue_shift,
        sat_mult=1.0,
        val_mult=1.0,
        target_color=target_color,
        tolerance=tolerance,
        layer=layer
    )


@server.tool()
def skin_set_pixels(
    part_name: str,
    pixels: List[Dict[str, Any]]
) -> str:
    """
    Efficiently set multiple individual pixels on a part in a single call.
    Ideal for micro-edits (e.g. changing 4 eye pixels or a 2-pixel logo) without dumping a full ASCII grid.
    Args:
        part_name: Target part name (e.g. 'head_front').
        pixels: List of dicts, each with 'x', 'y', and 'color' keys.
                Example: [{'x': 1, 'y': 5, 'color': '#b59ddb'}, {'x': 2, 'y': 5, 'color': '#7d0bd2'}]
    """
    if part_name not in MINECRAFT_UV_MAP:
        return f"Error: Unknown part '{part_name}'. Valid parts: {list(MINECRAFT_UV_MAP.keys())}"
    try:
        session.canvas.push_undo()
        count = session.canvas.set_pixels(part_name, pixels)
        session.mark_dirty()
        return f"Successfully updated {count} pixel(s) on part '{part_name}'. Live viewer updated."
    except Exception as e:
        return f"Error setting pixels on '{part_name}': {str(e)}"


@server.tool()
def skin_list_colors(
    part_name: Optional[str] = None,
    top_n: int = 16
) -> str:
    """
    Inspect unique colors and frequency counts on a specific face or the entire skin canvas.
    Args:
        part_name: Optional part name (e.g. 'head_front', 'body_front') or None for all parts.
        top_n: Max number of dominant colors to display (default 16).
    """
    try:
        colors = session.canvas.list_colors(part_name=part_name, top_n=top_n)
        target_name = part_name or "entire canvas"
        lines = [f"=== Top Colors on {target_name} ==="]
        for c in colors:
            alpha_note = " (transparent)" if c["alpha"] == 0 else ""
            lines.append(f"  {c['hex']} - RGB: {c['rgb']} | count: {c['count']} px ({c['percentage']}%) {alpha_note}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing colors: {str(e)}"


@server.tool()
def skin_diff(
    other_file_path: str,
    part_name: Optional[str] = None
) -> str:
    """
    Compare the current in-memory skin canvas against another skin PNG file.
    Identifies which of the 72 parts differ and by how many pixels, with exact sample coordinates.
    Args:
        other_file_path: Absolute or relative path to other skin PNG.
        part_name: Optional part name to restrict comparison to a single face.
    """
    path = os.path.abspath(os.path.expanduser(other_file_path))
    if not os.path.exists(path):
        return f"Error: File not found at '{path}'."
    try:
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
    except Exception as e:
        return f"Error comparing skins: {str(e)}"


@server.tool()
def skin_batch_actions(
    actions: List[Dict[str, Any]]
) -> str:
    """
    Execute multiple skin authoring actions in a single atomic MCP call.
    Drastically reduces token usage and network round trips.
    Supported actions:
      - {'action': 'set_pixel', 'part_name': '...', 'x': int, 'y': int, 'color': '...'}
      - {'action': 'set_pixels', 'part_name': '...', 'pixels': [...]}
      - {'action': 'replace_color', 'old_color': '...', 'new_color': '...', 'part_name': '...'}
      - {'action': 'draw_rect', 'part_name': '...', 'x': int, 'y': int, 'width': int, 'height': int, 'color': '...'}
      - {'action': 'fill_part', 'part_name': '...', 'color': '...'}
      - {'action': 'apply_preset', 'preset_name': '...', 'params': {...}}
      - {'action': 'mirror_limb', 'src_limb': '...', 'dst_limb': '...', 'mirror_layer2': bool}
      - {'action': 'add_noise', 'part_name': '...', 'amount': int}
      - {'action': 'apply_gradient', 'part_name': '...', 'start_color': '...', 'end_color': '...', 'direction': '...'}
    """
    session.canvas.push_undo()
    summary = []
    success_count = 0
    for idx, act in enumerate(actions):
        a_type = act.get("action")
        try:
            if a_type == "set_pixel":
                session.canvas.set_pixel(act["part_name"], act["x"], act["y"], normalize_color(act["color"]))
                summary.append(f"[{idx+1}] set_pixel on '{act['part_name']}' at ({act['x']}, {act['y']})")
            elif a_type == "set_pixels":
                c = session.canvas.set_pixels(act["part_name"], act["pixels"])
                summary.append(f"[{idx+1}] set_pixels on '{act['part_name']}': {c} px")
            elif a_type == "replace_color":
                c, aff = session.canvas.replace_color(
                    act["old_color"], act["new_color"],
                    part_name=act.get("part_name"),
                    tolerance=act.get("tolerance", 15),
                    layer=act.get("layer", "both")
                )
                summary.append(f"[{idx+1}] replace_color: {c} px across {len(aff)} parts")
            elif a_type == "draw_rect":
                session.canvas.draw_rect(
                    act["part_name"], act["x"], act["y"], act["width"], act["height"],
                    normalize_color(act["color"])
                )
                summary.append(f"[{idx+1}] draw_rect on '{act['part_name']}'")
            elif a_type == "fill_part":
                session.canvas.fill_part(act["part_name"], normalize_color(act["color"]))
                summary.append(f"[{idx+1}] fill_part on '{act['part_name']}'")
            elif a_type == "apply_preset":
                skin_apply_preset(act["preset_name"], act.get("params"))
                summary.append(f"[{idx+1}] apply_preset '{act['preset_name']}'")
            elif a_type == "mirror_limb":
                session.canvas.mirror_limb(
                    src_limb=act.get("src_limb", "right_arm"),
                    dst_limb=act.get("dst_limb", "left_arm"),
                    mirror_layer2=act.get("mirror_layer2", True)
                )
                summary.append(f"[{idx+1}] mirror_limb {act.get('src_limb')} -> {act.get('dst_limb')}")
            elif a_type == "add_noise":
                session.canvas.add_noise(act["part_name"], amount=act.get("amount", 6))
                summary.append(f"[{idx+1}] add_noise on '{act['part_name']}'")
            elif a_type == "apply_gradient":
                session.canvas.apply_gradient(
                    act["part_name"], act["start_color"], act["end_color"],
                    direction=act.get("direction", "vertical")
                )
                summary.append(f"[{idx+1}] apply_gradient on '{act['part_name']}'")
            else:
                summary.append(f"[{idx+1}] WARNING: Unknown action '{a_type}'")
                continue
            success_count += 1
        except Exception as e:
            summary.append(f"[{idx+1}] ERROR in action '{a_type}': {str(e)}")

    session.mark_dirty()
    return f"Batch Execution Complete ({success_count}/{len(actions)} succeeded). Live viewer updated:\n" + "\n".join(summary)


# ============================================================================
# 4. HIGH-LEVEL PRESETS, TYPOGRAPHY & OUTFITS
# ============================================================================

@server.tool()
def skin_draw_text(
    part_name: str,
    text: str,
    x: int = 1,
    y: int = 1,
    color: str = "#ffffff",
    spacing: int = 1
) -> str:
    """
    Render pixel typography on a UV face using an ultra-crisp 3x5 font matrix.
    Supports letters A-Z, numbers 0-9, and punctuation (!, ?, -, :, .).
    Args:
        part_name: Target UV face (e.g. 'jacket_back', 'body_front').
        text: Text string to render.
        x: Column starting coordinate (0-indexed).
        y: Row starting coordinate (0-indexed).
        color: Hex or RGBA string.
        spacing: Pixel spacing between characters (default 1).
    """
    try:
        session.canvas.push_undo()
        count = draw_text(session.canvas, part_name=part_name, text=text, x=x, y=y, color=color, spacing=spacing)
        session.mark_dirty()
        return f"Rendered text '{text}' on '{part_name}' at ({x}, {y}) using color {color} ({count} pixels drawn). Live viewer updated."
    except Exception as e:
        return f"Error rendering text: {str(e)}"


@server.tool()
def skin_draw_symbol(
    part_name: str,
    symbol_name: str,
    x: int = 1,
    y: int = 1,
    color: str = "#ffffff"
) -> str:
    """
    Render a pixel symbol/emblem on a UV face without guessing pixel coordinates.
    Available symbols: 'cyber_s' (6x8 crest), 'heart' (5x5), 'star' (5x5), 'lightning' (3x6), 'skull' (5x5), 'cross' (5x5).
    Args:
        part_name: Target face (e.g. 'jacket_back', 'body_front', 'right_arm_right').
        symbol_name: Name of symbol from library.
        x: Top-left X coordinate.
        y: Top-left Y coordinate.
        color: Hex color string.
    """
    try:
        session.canvas.push_undo()
        count = draw_symbol(session.canvas, part_name=part_name, symbol_name=symbol_name, x=x, y=y, color=color)
        session.mark_dirty()
        return f"Rendered symbol '{symbol_name}' on '{part_name}' at ({x}, {y}) with color {color} ({count} pixels drawn). Live viewer updated."
    except Exception as e:
        return f"Error rendering symbol: {str(e)}"


@server.tool()
def skin_apply_outfit(
    style: str = "techwear_hoodie",
    primary_color: str = "#141018",
    secondary_color: str = "#1c1822",
    accent_color: str = "#af36f8",
    trim_color: str = "#faf8fc"
) -> str:
    """
    Apply a complete coordinated full-body outfit macro across Layer 1 and Layer 2.
    Ensures 100% adherence to Rule 1 (solid body) and Rule 2 (relief accents).
    Styles:
        - 'techwear_hoodie': Oversized cyberpunk hoodie, kangaroo pouch, asymmetric drawstrings, cargo pants, 3D back crest.
        - 'cargo_streetwear': Relaxed hoodie with cargo pockets on both legs and cyber sneakers.
        - 'casual_tshirt': Everyday crewneck t-shirt with denim jeans, belt, and sneaker shoes.
    """
    try:
        session.canvas.push_undo()
        res = apply_outfit(
            session.canvas,
            style=style,
            primary_color=primary_color,
            secondary_color=secondary_color,
            accent_color=accent_color,
            trim_color=trim_color
        )
        session.mark_dirty()
        return (
            f"Applied outfit '{res['style']}' across {res['parts_modified_count']} parts:\n"
            f"- Primary: {primary_color} | Secondary: {secondary_color} | Accent: {accent_color} | Trim: {trim_color}\n"
            f"Live viewer updated."
        )
    except Exception as e:
        return f"Error applying outfit: {str(e)}"


@server.tool()
def skin_convert_model(target_model: str = "slim") -> str:
    """
    Convert canvas between 'default' (Steve 4px arms) and 'slim' (Alex 3px arms).
    Automatically resamples arm front/back/top/bottom UV islands.
    Args:
        target_model: 'slim' (Alex 3px arms) or 'default' (Steve 4px arms).
    """
    try:
        session.canvas.push_undo()
        res = convert_skin_model(session.canvas, target_model=target_model)
        session.model = target_model
        session.mark_dirty()
        return f"{res['message']} (status: {res['status']}). Live viewer updated."
    except Exception as e:
        return f"Error converting model geometry: {str(e)}"


@server.tool()
def skin_mirror_limb(
    src_limb: str = "right_arm",
    dst_limb: str = "left_arm",
    mirror_layer2: bool = True
) -> str:
    """
    Mirror an entire limb (arm or leg) to the other side.
    Correctly swaps outer and inner faces (right <-> left) and flips front/back.
    Args:
        src_limb: 'right_arm', 'left_arm', 'right_leg', or 'left_leg'.
        dst_limb: Target limb to overwrite with mirrored version.
        mirror_layer2: Whether to also mirror the outer layer (sleeve or pants).
    """
    try:
        session.canvas.push_undo()
        session.canvas.mirror_limb(src_limb=src_limb, dst_limb=dst_limb, mirror_layer2=mirror_layer2)
        session.mark_dirty()
        return f"Mirrored {src_limb} -> {dst_limb} (with Layer 2: {mirror_layer2}). Live viewer updated."
    except Exception as e:
        return f"Error mirroring limb: {str(e)}"


@server.tool()
def skin_add_noise(part_name: str, amount: int = 6) -> str:
    """
    Inject subtle procedural microtexture/noise into a part to prevent a flat, plastic look.
    Preserves transparent pixels.
    Args:
        part_name: Part name.
        amount: Noise intensity (default 6, values 2-10 recommended).
    """
    if part_name not in MINECRAFT_UV_MAP:
        return f"Error: Unknown part '{part_name}'."
    session.canvas.push_undo()
    session.canvas.add_noise(part_name, amount=amount)
    session.mark_dirty()
    return f"Injected microtexture (amount={amount}) on '{part_name}'. Live viewer updated."


@server.tool()
def skin_apply_preset(
    preset_name: str,
    params: Optional[Dict[str, Any]] = None
) -> str:
    """
    Apply a modular anatomical or clothing preset.
    Available presets:
      - 'anime_eyes_2x2': params: {'row': 5, 'left_col': 1, 'right_col': 5, 'iris_color': '#9a3cd4', 'highlight_color': '#e9d6f0', 'shadow_color': '#5f2987'}
      - 'hoodie_drawstrings': params: {'col_left': 2, 'col_right': 5, 'row_start': 1, 'len_left': 7, 'len_right': 4, 'color_bright': '#c355ff', 'color_tip': '#501278'}
      - 'cargo_pocket': params: {'part_name': 'right_pants_right', 'y_start': 2, 'flap_color': '#26222e', 'pouch_color': '#1e1a24', 'buckle_color': '#9a32dc'}
      - 'hair_bangs': params: {'style': 'cyberpunk', 'hair_color': '#1e1824', 'highlight_color': '#9a3cd4'}
      - 'sneakers': params: {'limb': 'right_leg', 'sole_color': '#ffffff', 'body_color': '#16141e', 'accent_color': '#9a32dc'}
      - 'headphones': params: {'earcup_color': '#9a32dc', 'band_color': '#221c2c', 'glow_color': '#d264ff'}
    """
    p = params or {}
    try:
        session.canvas.push_undo()
        if preset_name == "anime_eyes_2x2":
            draw_anime_eyes_2x2(
                session.canvas,
                left_col=p.get("left_col", 1),
                right_col=p.get("right_col", 5),
                row=p.get("row", 5),
                iris_color=p.get("iris_color", "#af36f8"),
                highlight_color=p.get("highlight_color", "#b59ddb"),
                shadow_color=p.get("shadow_color", "#7d0bd2"),
                shine_color=p.get("shine_color", "#faf8fc"),
                style=p.get("style", "cyber_glow"),
            )
        elif preset_name == "hoodie_drawstrings":
            draw_hoodie_drawstrings(
                session.canvas,
                col_left=p.get("col_left", 2),
                col_right=p.get("col_right", 5),
                row_start=p.get("row_start", 1),
                len_left=p.get("len_left", 7),
                len_right=p.get("len_right", 4),
                color_bright=p.get("color_bright", "#c355ff"),
                color_tip=p.get("color_tip", "#501278"),
            )
        elif preset_name == "cargo_pocket":
            draw_cargo_pocket(
                session.canvas,
                part_name=p.get("part_name", "right_pants_right"),
                y_start=p.get("y_start", 2),
                flap_color=p.get("flap_color", "#26222e"),
                pouch_color=p.get("pouch_color", "#1e1a24"),
                buckle_color=p.get("buckle_color", "#9a32dc"),
            )
        elif preset_name == "hair_bangs":
            draw_hair_bangs(
                session.canvas,
                style=p.get("style", "cyberpunk"),
                hair_color=p.get("hair_color", "#1e1824"),
                highlight_color=p.get("highlight_color", "#9a3cd4"),
            )
        elif preset_name == "sneakers":
            draw_sneakers(
                session.canvas,
                limb=p.get("limb", "right_leg"),
                sole_color=p.get("sole_color", "#ffffff"),
                body_color=p.get("body_color", "#16141e"),
                accent_color=p.get("accent_color", "#9a32dc"),
            )
        elif preset_name == "headphones":
            draw_headphones(
                session.canvas,
                earcup_color=p.get("earcup_color", "#9a3cd4"),
                band_color=p.get("band_color", "#221c2c"),
                glow_color=p.get("glow_color", "#d264ff"),
            )
        else:
            return f"Error: Unknown preset '{preset_name}'. Supported: anime_eyes_2x2, hoodie_drawstrings, cargo_pocket, hair_bangs, sneakers, headphones."

        session.mark_dirty()
        return f"Successfully applied preset '{preset_name}'. Live viewer updated."
    except Exception as e:
        return f"Error applying preset '{preset_name}': {str(e)}"


@server.tool()
def skin_clear_outer_layer(parts: Optional[List[str]] = None) -> str:
    """
    Clear all Layer 2 (Outer Overlay) parts or specific parts to transparent [0, 0, 0, 0].
    Useful for removing bloated overlay elements before re-applying clean 3D relief.
    """
    session.canvas.push_undo()
    cleared = session.canvas.clear_layer(layer="outer", parts=parts)
    session.mark_dirty()
    return f"Cleared {cleared} outer parts to 100% transparency. Live viewer updated."


# ============================================================================
# 5. VALIDATION, SEAM AUDITING & AUTO-HEALING
# ============================================================================

@server.tool()
def skin_check_seams(tolerance: int = 35) -> str:
    """
    Audit 3D cube edge wrap-around continuity across adjacent faces (Head ring, crown, torso ring, jacket).
    Detects texture tears, color misalignments, and seam borders visible when orbiting around the 3D model.
    Args:
        tolerance: Color distance threshold above which an edge pixel is flagged (default 35).
    """
    discrepancies = check_seams(session.canvas, tolerance=tolerance)
    if not discrepancies:
        return f"Pass: All 3D seams are continuous and well-aligned (tolerance={tolerance}). Zero texture tears detected."

    total_mismatches = sum(d["mismatch_count"] for d in discrepancies)
    lines = [
        f"=== 3D Seam Continuity Audit ({len(discrepancies)} seam(s) flagged, {total_mismatches} mismatched pixel(s)) ==="
    ]
    for d in discrepancies:
        lines.append(f"\n* Seam: {d['seam_name']} ({d['part_a']} <-> {d['part_b']}) - {d['mismatch_count']} mismatched px:")
        for m in d["mismatches"][:5]:  # limit to 5 per seam to save tokens
            lines.append(f"    - Index {m['index']}: {m['color_a']} vs {m['color_b']} (dist: {m['color_distance']})")
        if len(d["mismatches"]) > 5:
            lines.append(f"    ... and {len(d['mismatches']) - 5} more.")
    lines.append("\nTip: Call 'skin_align_seams()' to automatically heal and blend these seams.")
    return "\n".join(lines)


@server.tool()
def skin_align_seams(seam_name: str = "all", mode: str = "blend") -> str:
    """
    Automatically heal and harmonize color continuity along adjacent 3D cube edges.
    Args:
        seam_name: Substring matching seam description (e.g. 'Head Front-Right', 'Torso', 'all').
        mode: 'blend' (smooth average of both edges) or 'copy_a_to_b'.
    """
    session.canvas.push_undo()
    aligned = align_seams(session.canvas, seam_name=seam_name, mode=mode)
    session.mark_dirty()
    return f"Successfully aligned {aligned} edge pixel(s) across seam(s) matching '{seam_name}' using mode='{mode}'. Live viewer updated."


@server.tool()
def skin_validate() -> str:
    """
    Run full quality and layer discipline audit on the active working canvas.
    Checks:
      1. 64x64 dimensions.
      2. Layer 1 holes: Any non-opaque pixels on base body parts (Rule 1).
      3. Layer 2 floating profile planes on hat_front rows 4-7 (Rule 3).
      4. Layer 2 floating isolated crown planks on hat_top (Rule 4).
      5. Head front/side seam continuity.
    Returns structured pass/fail report with exact remediation suggestions.
    """
    validator = SkinValidator(session.canvas)
    res = validator.validate_structured()

    out = [res["report"]]
    if res["suggestions"]:
        out.append("\n[RECOMMENDED ACTIONS]:")
        for s in res["suggestions"]:
            out.append(f"  -> {s}")

    return "\n".join(out)


@server.tool()
def skin_auto_fix(default_skin_color: Optional[str] = None) -> str:
    """
    Autonomous self-healing tool for common LLM mistakes:
      1. Plugs all non-opaque holes on Layer 1 using neighbor colors or default_skin_color (Rule 1).
      2. Wipes out illegal floating cheek pixels on hat_front rows 4-7 (Rule 3).
      3. Clears isolated floating lines on hat_top (Rule 4).
    """
    session.canvas.push_undo()
    healed = session.canvas.heal_layer1_holes(default_color=default_skin_color)
    sanitized = session.canvas.sanitize_outer_layer()
    session.mark_dirty()

    return (
        f"=== Autonomous Self-Healing Report ===\n"
        f"- Healed Layer 1 holes: {healed} pixels made 100% solid (Rule 1 compliant).\n"
        f"- Sanitized Layer 2: {sanitized} floating profile/crown pixels cleared (Rules 3 & 4 compliant).\n"
        f"Active canvas is now compliant with Minecraft dual-layer depth rules! Live viewer updated."
    )


# ============================================================================
# 6. PALETTES & COLOR ASSISTANT
# ============================================================================

@server.tool()
def skin_generate_color_ramp(base_color: str, steps: int = 5) -> str:
    """
    Generate a harmonious 5-step shading ramp (deep shadow, shadow, base, highlight, rim highlight)
    from a single base hex or RGB color.
    Returns ASCII characters ('_', '#', '=', '+', '~') mapped to exact hex and RGBA values.
    """
    try:
        res = generate_color_ramp(base_color, steps=steps)
        lines = [f"Color Ramp for Base '{res['base_hex']}':"]
        for d in res["details"]:
            lines.append(f"  '{d['char']}': {d['hex']} {d['rgba']} (step {d['step']})")
        lines.append(f"\nCopyable ASCII Palette Dict:\n{json.dumps(res['palette'])}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error generating color ramp: {str(e)}"


@server.tool()
def skin_list_palettes() -> str:
    """
    List all available built-in color palettes and their theme styles.
    """
    return (
        "Available Built-in Palettes:\n"
        "- 'TECHWEAR_CYBERPUNK': Syntren theme (dark obsidian fabrics, neon violet/lavender accents, silver chains, sneakers).\n"
        "- 'ANIME_SKIN': Curated skin tones ('light', 'base', 'midtone', 'shadow', 'deep').\n"
        "- 'CASUAL_STREETWEAR': Denim blues, cream/white fabrics, leather brown.\n"
        "- 'FANTASY_KNIGHT': Polished steel armor shades with gold trim specular highlights.\n"
    )


# ============================================================================
# 7. 3D WEB VIEWER INTEGRATION
# ============================================================================

@server.tool()
def viewer_start(port: int = 8080) -> str:
    """
    Launch the interactive Three.js 3D WebGL skin viewer in the background.
    Live auto-reloads automatically whenever 'skin_save' is called.
    """
    if session.viewer_process and session.viewer_process.poll() is None:
        return f"Viewer is already running at: http://localhost:{session.viewer_port}"

    viewer_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "viewer.py"))
    if not os.path.exists(viewer_script):
        viewer_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "viewer.py"))

    # If skin file not yet saved, save current canvas to a temporary preview
    if not session.file_path:
        default_skin = os.path.abspath("skins/skin_current.png")
        session.canvas.export_png(default_skin)
        session.file_path = default_skin

    session.sync_live()

    try:
        proc = subprocess.Popen(
            [sys.executable, viewer_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(viewer_script)
        )
        session.viewer_process = proc
        session.viewer_port = port
        return (
            f"Started interactive 3D WebGL viewer on http://localhost:{port} (PID {proc.pid}).\n"
            f"Watching active skin file: '{session.file_path}'.\n"
            f"User can view walk/run animations, orbit rotate, and right-click pan in their web browser."
        )
    except Exception as e:
        return f"Error starting viewer: {str(e)}"


@server.tool()
def viewer_status() -> str:
    """
    Check the status and URL of the 3D WebGL viewer server.
    """
    is_running = session.viewer_process and session.viewer_process.poll() is None
    if is_running:
        return f"Viewer is RUNNING at http://localhost:{session.viewer_port} (PID {session.viewer_process.pid}). Watching: '{session.file_path}'"
    return "Viewer is currently STOPPED. Start it using 'viewer_start'."


@server.tool()
def viewer_stop() -> str:
    """
    Terminate the background 3D WebGL viewer server process.
    """
    if session.viewer_process and session.viewer_process.poll() is None:
        session.viewer_process.terminate()
        session.viewer_process = None
        return "3D WebGL viewer stopped."
    return "Viewer was not running."


# ============================================================================
# 8. MCP RESOURCES
# ============================================================================

@server.resource("skin://uv-map")
def get_uv_map_resource() -> str:
    """Complete Minecraft 1.8+ 64x64 dual-layer UV coordinate matrix."""
    lines = ["Face Identifier | Layer | Texture Box (u0, v0, u1, v1) | Dimensions (W x H)"]
    for name, (u0, v0, u1, v1) in MINECRAFT_UV_MAP.items():
        layer = "Outer (Layer 2)" if any(x in name for x in ['hat', 'jacket', 'sleeve', 'pants']) else "Base (Layer 1)"
        lines.append(f"{name:20} | {layer:15} | ({u0:2}, {v0:2}, {u1:2}, {v1:2}) | {u1-u0}x{v1-v0}")
    return "\n".join(lines)


@server.resource("skin://layer-rules")
def get_layer_rules_resource() -> str:
    """The 4 Golden Rules of Minecraft Skin Depth from instructions.md."""
    return (
        "THE 4 GOLDEN RULES OF MINECRAFT SKIN DEPTH:\n"
        "-------------------------------------------\n"
        "Rule 1: Layer 1 is 100% Solid (Zero Holes)\n"
        "  - All 36 Base Layer parts MUST have alpha = 255 on every single pixel.\n"
        "  - Transparent pixels on Layer 1 render as black empty voids through the skull/torso.\n\n"
        "Rule 2: Layer 2 is Exclusively for 3D Relief (+0.35 Blocks)\n"
        "  - Floats +0.35 blocks outside Layer 1.\n"
        "  - DO NOT duplicate the whole solid body on Layer 2 (causes bloated marshmallow look).\n"
        "  - Use ONLY for bangs, hood rim, pocket flaps, badges, cuffs, hems.\n\n"
        "Rule 3: The Floating Cardboard Plane Trap (hat_front Profile Bug)\n"
        "  - On 'hat_front', rows 4 to 7 MUST be 100% transparent across all columns.\n"
        "  - Bangs belong ONLY on rows 0 to 3. Pixels on rows 4-7 float detached in empty space in 90° profile view.\n\n"
        "Rule 4: The Floating Plank Trap (hat_top Crown Bug)\n"
        "  - 'hat_top' must either be solid (hood crown) or 100% transparent.\n"
        "  - Never leave isolated single stripes (< 20 pixels) hovering 0.5 blocks above the head."
    )


@server.resource("skin://palettes")
def get_palettes_resource() -> str:
    """JSON representation of all built-in color palettes."""
    return json.dumps({
        "TECHWEAR_CYBERPUNK": TECHWEAR_CYBERPUNK,
        "ANIME_SKIN": ANIME_SKIN,
        "CASUAL_STREETWEAR": CASUAL_STREETWEAR,
        "FANTASY_KNIGHT": FANTASY_KNIGHT,
    }, indent=2)


@server.resource("skin://session-state")
def get_session_state_resource() -> str:
    """Real-time diagnostic summary of the active working canvas."""
    return skin_get_session_info()


# ============================================================================
# 9. MCP PROMPTS
# ============================================================================

@server.prompt("create-skin")
def prompt_create_skin() -> List[types.PromptMessage]:
    """Autonomous agent workflow prompt for designing a skin from scratch."""
    instructions = (
        "You are an expert Minecraft skin artist using SkinForge MCP server.\n\n"
        "RECOMMENDED WORKFLOW:\n"
        "1. Start by calling 'skin_new(template=\"base_body\", skin_tone=...)' to get a solid, 0-hole Layer 1.\n"
        "2. Paint the head and face with 'skin_set_part_ascii(\"head_front\", ...)' or presets like 'skin_apply_preset(\"anime_eyes_2x2\")'.\n"
        "3. Design clothing on Layer 1 ('body_front', 'right_arm_front', 'right_leg_front').\n"
        "4. Mirror limbs with 'skin_mirror_limb(\"right_arm\", \"left_arm\")' and 'skin_mirror_limb(\"right_leg\", \"left_leg\")'.\n"
        "5. Add 3D relief on Layer 2 (e.g. bangs on 'hat_front' rows 0-3 only, hood on 'hat_top', pocket on 'right_pants_right').\n"
        "6. Call 'skin_validate()'. If any warnings appear, call 'skin_auto_fix()'.\n"
        "7. Call 'skin_render_3d(preset=\"turnaround\")' to visually inspect your design across 4 camera angles.\n"
        "8. Call 'skin_save(file_path=...)' to save the final PNG."
    )
    return [
        types.PromptMessage(
            role="user",
            content=types.TextContent(type="text", text=instructions)
        )
    ]


@server.prompt("audit-and-fix-skin")
def prompt_audit_and_fix() -> List[types.PromptMessage]:
    """Workflow prompt for auditing and fixing an existing skin PNG."""
    instructions = (
        "You are auditing and fixing a Minecraft skin using SkinForge MCP.\n\n"
        "STEPS:\n"
        "1. Call 'skin_load(file_path=...)' to load the skin.\n"
        "2. Call 'skin_validate()' to inspect Layer 1 holes, Rule 3 profile bugs, and Rule 4 crown bugs.\n"
        "3. Call 'skin_auto_fix()' to autonomously patch transparent holes and strip illegal floating cardboard.\n"
        "4. Call 'skin_render_3d(preset=\"turnaround\")' and 'skin_render_3d(preset=\"left_profile\")' to visually confirm the fixes.\n"
        "5. Save with 'skin_save()'."
    )
    return [
        types.PromptMessage(
            role="user",
            content=types.TextContent(type="text", text=instructions)
        )
    ]


def main():
    """Run the SkinForge MCP Server over stdio."""
    server.run("stdio")


if __name__ == "__main__":
    main()
