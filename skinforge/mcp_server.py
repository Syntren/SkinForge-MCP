"""
SkinForge Model Context Protocol (MCP) Server (v1.3.0).

Empowers LLM agents to author, inspect, edit, audit, pack RAG datasets, and visually verify
Minecraft 64x64 (and legacy 64x32) skins with dual-layer 3D depth, ASCII DSL reverse-engineering,
multimodal feedback, 30-state undo/redo history, and live SSE WebGL viewing.
"""

from __future__ import annotations

import base64
import functools
import inspect
import io
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from PIL import Image
from pydantic import BaseModel, Field

__version__ = "1.3.0"


@dataclass
class _ToolCallResult:
    """Normalized result wrapper guaranteeing a `.content` attribute across MCPServer, FastMCP, and tests."""
    content: List[Any]
    isError: bool = False


try:
    import mcp.types as types
    if hasattr(types, "ImageContent") and not hasattr(types.ImageContent, "mimeType"):
        try:
            types.ImageContent.mimeType = property(lambda self: getattr(self, "mime_type", "image/png"))  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        from mcp.server.mcpserver import MCPServer as _BaseMCPServer  # type: ignore[import-not-found]
    except ImportError:
        from mcp.server.fastmcp import FastMCP as _BaseMCPServer  # type: ignore[import-not-found]

    class MCPServer(_BaseMCPServer):  # type: ignore[misc]
        """Unified MCPServer subclass compatible with both MCPServer and FastMCP."""

        async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
            res = await super().call_tool(name, arguments or {})
            if hasattr(res, "content"):
                return res
            if isinstance(res, tuple) and len(res) >= 1 and isinstance(res[0], (list, tuple)):
                return _ToolCallResult(content=list(res[0]))
            if isinstance(res, (list, tuple)):
                return _ToolCallResult(content=list(res))
            return _ToolCallResult(content=[res])

except ImportError:
    # Self-contained MCP JSON-RPC 2.0 implementation for environments without the `mcp` package
    class _FallbackTypes:
        @dataclass
        class TextContent:
            type: str = "text"
            text: str = ""

        @dataclass
        class ImageContent:
            type: str = "image"
            data: str = ""
            mime_type: str = "image/png"
            mimeType: str = "image/png"

            def __post_init__(self) -> None:
                if self.mime_type != "image/png" and self.mimeType == "image/png":
                    self.mimeType = self.mime_type
                elif self.mimeType != "image/png" and self.mime_type == "image/png":
                    self.mime_type = self.mimeType

        @dataclass
        class PromptMessage:
            role: str
            content: Any

        ContentBlock = Union[TextContent, ImageContent]

    types = _FallbackTypes()  # type: ignore[assignment]

    @dataclass
    class _ResourceInfo:
        uri: str
        name: str
        fn: Callable

    @dataclass
    class _PromptInfo:
        name: str
        fn: Callable

    class _ToolManager:
        def __init__(self) -> None:
            self._tools: Dict[str, Callable] = {}

    class MCPServer:  # type: ignore[no-redef]
        """Full JSON-RPC 2.0 stdio MCP server fallback when external `mcp` package is absent."""

        def __init__(self, name: str = "skinforge", instructions: Optional[str] = None) -> None:
            self.name = name
            self.instructions = instructions
            self._tool_manager = _ToolManager()
            self._resources: Dict[str, _ResourceInfo] = {}
            self._prompts: Dict[str, _PromptInfo] = {}

        def tool(self, name: Optional[str] = None) -> Callable:
            def decorator(fn: Callable) -> Callable:
                t_name = name or fn.__name__
                self._tool_manager._tools[t_name] = fn
                return fn
            return decorator

        def resource(self, uri: str) -> Callable:
            def decorator(fn: Callable) -> Callable:
                self._resources[uri] = _ResourceInfo(uri=uri, name=fn.__name__, fn=fn)
                return fn
            return decorator

        def prompt(self, name: str) -> Callable:
            def decorator(fn: Callable) -> Callable:
                self._prompts[name] = _PromptInfo(name=name, fn=fn)
                return fn
            return decorator

        def _invoke_tool_sync(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> _ToolCallResult:
            if name not in self._tool_manager._tools:
                raise ValueError(f"Unknown tool: {name}")
            fn = self._tool_manager._tools[name]
            res = fn(**(arguments or {}))
            if isinstance(res, list):
                content = [
                    item if hasattr(item, "type") else types.TextContent(type="text", text=str(item))
                    for item in res
                ]
            elif hasattr(res, "type"):
                content = [res]
            else:
                content = [types.TextContent(type="text", text=str(res))]
            return _ToolCallResult(content=content)

        async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> _ToolCallResult:
            return self._invoke_tool_sync(name, arguments)

        async def list_resources(self) -> List[_ResourceInfo]:
            return list(self._resources.values())

        async def list_prompts(self) -> List[_PromptInfo]:
            return list(self._prompts.values())

        @staticmethod
        def _build_tool_schema(t_name: str, fn: Callable) -> Dict[str, Any]:
            sig = inspect.signature(fn)
            properties: Dict[str, Any] = {}
            required: List[str] = []
            for p_name, param in sig.parameters.items():
                ann = str(param.annotation)
                if "int" in ann and "List" not in ann and "Dict" not in ann:
                    p_type = "integer"
                elif "float" in ann and "List" not in ann:
                    p_type = "number"
                elif "bool" in ann:
                    p_type = "boolean"
                elif "List" in ann or "list" in ann:
                    p_type = "array"
                elif "Dict" in ann or "dict" in ann:
                    p_type = "object"
                else:
                    p_type = "string"
                prop_schema: Dict[str, Any] = {"type": p_type}
                if param.default is not inspect.Parameter.empty:
                    prop_schema["default"] = param.default
                else:
                    required.append(p_name)
                properties[p_name] = prop_schema
            return {
                "name": t_name,
                "description": (fn.__doc__ or "").strip(),
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }

        @staticmethod
        def _serialize_content_block(block: Any) -> Dict[str, Any]:
            b_type = getattr(block, "type", "text")
            if b_type == "image":
                mime = getattr(block, "mimeType", getattr(block, "mime_type", "image/png"))
                return {
                    "type": "image",
                    "data": getattr(block, "data", ""),
                    "mimeType": mime,
                }
            return {
                "type": "text",
                "text": getattr(block, "text", str(block)),
            }

        def handle_jsonrpc_request(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            """Process a single JSON-RPC 2.0 request/notification dict and return response dict (or None for notifications)."""
            method = msg.get("method", "")
            req_id = msg.get("id")
            params = msg.get("params") or {}

            # Notifications (no id) do not receive a response
            if req_id is None or method.startswith("notifications/"):
                return None

            try:
                if method == "initialize":
                    result: Dict[str, Any] = {
                        "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "resources": {"subscribe": False, "listChanged": False},
                            "prompts": {"listChanged": False},
                        },
                        "serverInfo": {
                            "name": self.name,
                            "version": __version__,
                        },
                    }
                    if self.instructions:
                        result["instructions"] = self.instructions
                elif method == "ping":
                    result = {}
                elif method == "tools/list":
                    result = {
                        "tools": [
                            self._build_tool_schema(t_name, fn)
                            for t_name, fn in self._tool_manager._tools.items()
                        ]
                    }
                elif method == "tools/call":
                    t_name = params.get("name", "")
                    t_args = params.get("arguments") or {}
                    if t_name not in self._tool_manager._tools:
                        return {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32602, "message": f"Unknown tool: {t_name}"},
                        }
                    call_res = self._invoke_tool_sync(t_name, t_args)
                    result = {
                        "content": [self._serialize_content_block(b) for b in call_res.content],
                        "isError": bool(call_res.isError),
                    }
                elif method == "resources/list":
                    result = {
                        "resources": [
                            {
                                "uri": r.uri,
                                "name": r.name,
                                "description": (r.fn.__doc__ or "").strip(),
                                "mimeType": "text/plain",
                            }
                            for r in self._resources.values()
                        ]
                    }
                elif method == "resources/read":
                    uri = params.get("uri", "")
                    if uri not in self._resources:
                        return {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32602, "message": f"Unknown resource URI: {uri}"},
                        }
                    text_val = self._resources[uri].fn()
                    result = {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "text/plain",
                                "text": str(text_val),
                            }
                        ]
                    }
                elif method == "prompts/list":
                    result = {
                        "prompts": [
                            {
                                "name": p.name,
                                "description": (p.fn.__doc__ or "").strip(),
                            }
                            for p in self._prompts.values()
                        ]
                    }
                elif method == "prompts/get":
                    p_name = params.get("name", "")
                    if p_name not in self._prompts:
                        return {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32602, "message": f"Unknown prompt: {p_name}"},
                        }
                    p_obj = self._prompts[p_name]
                    p_msgs = p_obj.fn(**(params.get("arguments") or {}))
                    serialized_msgs = []
                    for m in p_msgs:
                        serialized_msgs.append({
                            "role": getattr(m, "role", "user"),
                            "content": self._serialize_content_block(getattr(m, "content", m)),
                        })
                    result = {
                        "description": (p_obj.fn.__doc__ or "").strip(),
                        "messages": serialized_msgs,
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    }

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": result,
                }
            except Exception as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(exc)},
                }

        def run(self, transport: str = "stdio", input_stream: Any = None, output_stream: Any = None) -> None:
            """Run full JSON-RPC 2.0 stdio event loop reading from stdin and writing to stdout."""
            in_s = input_stream if input_stream is not None else sys.stdin
            out_s = output_stream if output_stream is not None else sys.stdout

            for raw_line in in_s:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception as exc:
                    err_resp = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": f"Parse error: {exc}"},
                    }
                    out_s.write(json.dumps(err_resp) + "\n")
                    out_s.flush()
                    continue

                if isinstance(msg, dict):
                    resp = self.handle_jsonrpc_request(msg)
                    if resp is not None:
                        out_s.write(json.dumps(resp) + "\n")
                        out_s.flush()

from .ascii_codec import canvas_to_ascii, normalize_color, part_to_ascii, rgba_to_hex
from .audit import (
    SkinValidator,
    align_seams,
    auto_fix_skin,
    check_seams,
    compute_aesthetic_score,
    detect_pillow_shading,
)
from .color import (
    ANIME_SKIN,
    CASUAL_STREETWEAR,
    FANTASY_KNIGHT,
    TECHWEAR_CYBERPUNK,
    generate_color_ramp,
)
from .converter import convert_skin_model
from .core import (
    BASE_PARTS,
    MINECRAFT_UV_MAP,
    OUTER_PARTS,
    SkinCanvas,
    SkinSession,
    atomic_save_png,
)
from .outfits import apply_outfit
from .presets import (
    draw_anime_eyes_2x2,
    draw_cargo_pocket,
    draw_hair_bangs,
    draw_headphones,
    draw_hoodie_drawstrings,
    draw_sneakers,
)
from .rag import get_rag, pack_rag_database
from .renderer import (
    render_3d_single,
    render_3d_turnaround,
    render_bottom_up,
    render_composite_2d,
    render_part_zoomed,
    render_turntable_gif,
)
from .sampler import sample_image
from .templates import SKIN_TONE_PALETTES, create_base_body
from .typography import draw_symbol, draw_text

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# PYDANTIC SCHEMAS & UNIFIED ERROR HANDLING DECORATOR
# ============================================================================

class PixelCoordSchema(BaseModel):
    """Pydantic schema for single pixel coordinate & color edits."""
    x: int = Field(..., ge=0, lt=64, description="0-indexed X coordinate within the UV part")
    y: int = Field(..., ge=0, lt=64, description="0-indexed Y coordinate within the UV part")
    color: Union[str, List[int]] = Field(..., description="Hex color string or RGBA [r, g, b, a] list")


class BatchActionSchema(BaseModel):
    """Pydantic schema for atomic batch action items."""
    action: str = Field(..., description="Action identifier (e.g. set_pixel, draw_rect, fill_part)")
    part_name: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    color: Optional[Any] = None
    pixels: Optional[List[Dict[str, Any]]] = None
    old_color: Optional[Any] = None
    new_color: Optional[Any] = None
    tolerance: int = 15
    layer: str = "both"
    preset_name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    src_limb: str = "right_arm"
    dst_limb: str = "left_arm"
    mirror_layer2: bool = True
    amount: int = 6
    start_color: Optional[Any] = None
    end_color: Optional[Any] = None
    direction: str = "vertical"


class RagPackConfigSchema(BaseModel):
    """Pydantic schema for RAG database packing parameters."""
    source_path: str = Field(..., description="Folder of .png skins or .zip archive")
    output_path: Optional[str] = Field(None, description="Destination .sfpack or .db path")
    metadata_path: Optional[str] = Field(None, description="Optional .json or .csv metadata file")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="Minimum aesthetic score filter")
    overwrite: bool = Field(False, description="Overwrite existing database if True")


def handle_mcp_errors(json_output: bool = False, multimodal: bool = False) -> Callable:
    """
    Unified error-handling decorator for all SkinForge MCP tools.
    Catches exceptions cleanly and formats error responses consistently.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                if multimodal:
                    return [types.TextContent(type="text", text=f"Error in {fn.__name__}: {str(exc)}")]
                if json_output:
                    return json.dumps({"status": "error", "error": str(exc)}, indent=2)
                return f"Error: {str(exc)}"
        return wrapper
    return decorator


def _validate_part_name(part_name: str) -> Optional[str]:
    if part_name not in MINECRAFT_UV_MAP:
        return f"Error: Unknown part '{part_name}'. Valid parts: {list(MINECRAFT_UV_MAP.keys())}"
    return None


def _image_to_content(im: Image.Image) -> types.ImageContent:
    """Convert PIL Image into an MCP ImageContent object for multimodal LLM feedback."""
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
    try:
        return types.ImageContent(type="image", data=b64_str, mime_type="image/png", mimeType="image/png")
    except TypeError:
        try:
            return types.ImageContent(type="image", data=b64_str, mimeType="image/png")
        except TypeError:
            return types.ImageContent(type="image", data=b64_str, mime_type="image/png")


# Active thread-safe session singleton
session = SkinSession(project_root=PROJECT_ROOT)

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


# ============================================================================
# 1. SESSION & CANVAS MANAGEMENT TOOLS
# ============================================================================

@server.tool()
@handle_mcp_errors()
def skin_new(
    template: str = "base_body",
    skin_tone: str = "fair",
    hair_color: str = "#221c28",
    eye_color: str = "#9a3cd4"
) -> str:
    """
    Initialize a new active in-memory skin canvas.
    Args:
        template: 'base_body' (populates a 100% solid Layer 1 humanoid template with 0 holes) or 'blank' (all transparent).
        skin_tone: 'fair', 'tan', 'pale', 'dark', or 'anime'.
        hair_color: Hex color string for hair (e.g. '#221c28').
        eye_color: Hex color string for eye iris (e.g. '#9a3cd4').
    """
    with session.lock:
        if template == "base_body":
            session.reset_template(skin_tone=skin_tone)
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
@handle_mcp_errors()
def skin_load(file_path: str) -> str:
    """
    Load a 64x64 (or legacy 64x32, auto-converted to 64x64) Minecraft skin PNG from disk into the active session.
    """
    path = os.path.abspath(os.path.expanduser(file_path))
    if not os.path.exists(path):
        return f"Error: File not found at '{path}'."

    with session.lock:
        was_legacy = session.canvas.load_png(path)
        session.file_path = path
        session.model = session.canvas.model
        session.is_dirty = False
        session.canvas.undo_stack.clear()
        session.canvas.redo_stack.clear()
        session.sync_live()

        validator = SkinValidator(session.canvas)
        valid, report = validator.validate()
        status = "PASSED quality checks" if valid else "WARNINGS/ERRORS DETECTED"
        legacy_note = " (Auto-converted from legacy 64x32 -> 64x64)" if was_legacy else ""
        return (
            f"Successfully loaded skin from '{path}'{legacy_note}.\n"
            f"Audit Status: {status}.\nLive 3D viewer updated.\n\nAudit Summary:\n{report}"
        )


@server.tool()
@handle_mcp_errors()
def skin_save(
    file_path: Optional[str] = None,
    also_export: Optional[List[str]] = None,
    update_previews: bool = True
) -> str:
    """
    Atomically export the current active canvas to a 64x64 RGBA Minecraft skin PNG file.
    Synchronizes across configured targets and optionally regenerates 2D/3D previews.
    """
    with session.lock:
        target = file_path or session.file_path or os.path.join(PROJECT_ROOT, "skins", "skin_syntren.png")
        target = os.path.abspath(os.path.expanduser(target))
        session.canvas.export_png(target)
        session.file_path = target
        session.is_dirty = False
        session.sync_live()

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


@server.tool()
@handle_mcp_errors()
def skin_get_session_info() -> str:
    """Get detailed metrics and status of the current active working skin session."""
    with session.lock:
        base_total = 0
        base_opaque = 0
        for p in BASE_PARTS:
            part = session.canvas.parts[p]
            base_total += part.shape[0] * part.shape[1]
            base_opaque += int((part[:, :, 3] == 255).sum())

        outer_total = 0
        outer_filled = 0
        for p in OUTER_PARTS:
            part = session.canvas.parts[p]
            outer_total += part.shape[0] * part.shape[1]
            outer_filled += int((part[:, :, 3] > 0).sum())

        base_ratio = (base_opaque / base_total * 100.0) if base_total else 0.0
        outer_ratio = (outer_filled / outer_total * 100.0) if outer_total else 0.0

        v_status = "Running" if session.viewer_process and session.viewer_process.poll() is None else "Stopped"
        model_desc = "Classic Steve 4px arm" if session.model == "default" else "Slim Alex 3px arm"
        ckpt_names = ", ".join(session.canvas.checkpoints.keys()) if session.canvas.checkpoints else "none"
        aesthetic = compute_aesthetic_score(session.canvas)
        m = aesthetic["metrics"]

        return (
            f"=== SkinForge Active Session Info (v{__version__}) ===\n"
            f"Loaded File: {session.file_path or '(In-memory canvas)'}\n"
            f"Unsaved Changes: {'Yes' if session.is_dirty else 'No'}\n"
            f"Player Model: {session.model} ({model_desc})\n"
            f"Aesthetic Score: {aesthetic['score']:.2f} / 1.0 [{aesthetic['tier'].upper()}] "
            f"(Relief: {int(m['relief_3d']*100)}%, Palette: {int(m['palette_harmony']*100)}%, "
            f"Coherence: {int(m['spatial_coherence']*100)}%, HueShift: {int(m['hue_shifting']*100)}%)\n"
            f"Undo History: {len(session.undo_stack)} step(s) | Redo: {len(session.redo_stack)} step(s)\n"
            f"Checkpoints: {len(session.canvas.checkpoints)} ({ckpt_names})\n"
            f"Layer 1 (Base Body): {base_opaque}/{base_total} opaque pixels ({base_ratio:.1f}% solid)\n"
            f"Layer 2 (3D Relief): {outer_filled}/{outer_total} active pixels ({outer_ratio:.1f}% relief density)\n"
            f"3D Web Viewer: {v_status} (Port {session.viewer_port})\n"
        )


# ============================================================================
# 1B. CANVAS HISTORY & CHECKPOINTS (UNDO / REDO / HISTORY / SNAPSHOTS)
# ============================================================================

@server.tool()
@handle_mcp_errors()
def skin_checkpoint(name: str) -> str:
    """Save a named milestone checkpoint of the active canvas state."""
    with session.lock:
        count = session.canvas.create_checkpoint(name)
        return f"Created checkpoint '{name}'. Total checkpoints saved: {count}."


@server.tool()
@handle_mcp_errors()
def skin_restore_checkpoint(name: str) -> str:
    """Restore the canvas to a previously saved named checkpoint."""
    with session.lock:
        if name not in session.canvas.checkpoints:
            available = list(session.canvas.checkpoints.keys())
            return f"Error: Checkpoint '{name}' not found. Available checkpoints: {available}"
        session.canvas.restore_checkpoint(name)
        session.mark_dirty()
        return f"Successfully restored canvas to checkpoint '{name}'. Live viewer updated."


@server.tool()
@handle_mcp_errors()
def skin_undo() -> str:
    """Undo the last modification made to the active skin canvas (up to 30 states)."""
    if session.undo():
        remaining = len(session.undo_stack)
        return f"Undid last action. Canvas reverted to previous state ({remaining} undo steps remaining in history). Live viewer updated."
    return "Nothing to undo. Undo history is empty."


@server.tool()
@handle_mcp_errors()
def skin_redo() -> str:
    """Reapply the last undone modification from redo_stack."""
    if session.redo():
        remaining = len(session.redo_stack)
        return f"Redid previous action ({remaining} redo steps remaining in future history). Live viewer updated."
    return "Nothing to redo. Redo history is empty."


@server.tool()
@handle_mcp_errors(json_output=True)
def skin_history() -> str:
    """
    Inspect the current session's in-memory undo_stack, redo_stack (up to 30 states),
    and named checkpoints.
    """
    hist = session.get_history()
    return json.dumps({
        "status": "success",
        **hist,
    }, indent=2)


# ============================================================================
# 2. VISUAL RENDERING & MULTIMODAL VERIFICATION TOOLS
# ============================================================================

@server.tool()
@handle_mcp_errors(multimodal=True)
def skin_render_3d(
    preset: str = "turnaround",
    yaw_deg: float = -30.0,
    pitch_deg: float = 15.0,
    layer_mode: str = "both",
    save_path: Optional[str] = None
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
        _image_to_content(img),
    ]


@server.tool()
@handle_mcp_errors(multimodal=True)
def skin_render_2d(
    layer_mode: str = "both",
    scale: int = 16,
    save_path: Optional[str] = None
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
        _image_to_content(img),
    ]


@server.tool()
@handle_mcp_errors(multimodal=True)
def skin_render_part(
    part_name: str,
    scale: int = 16,
    show_grid: bool = True,
    save_path: Optional[str] = None
) -> List[types.ContentBlock]:
    """Render an individual UV part face enlarged with a pixel grid for micro-inspection."""
    err = _validate_part_name(part_name)
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
        _image_to_content(img),
    ]


@server.tool()
@handle_mcp_errors(multimodal=True)
def skin_render_turntable_gif(
    frames: int = 16,
    fps: int = 12,
    layer_mode: str = "both",
    out_path: Optional[str] = None
) -> List[Any]:
    """Generate an animated 360-degree turntable rotation GIF of the player model."""
    if not out_path and session.file_path:
        out = os.path.join(os.path.dirname(session.file_path), "turntable_360.gif")
    else:
        out = out_path or os.path.join(PROJECT_ROOT, "previews", "turntable_360.gif")
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


# ============================================================================
# 3. RAG SEARCH, VISUAL SEARCH, MODULAR LEGO ASSEMBLY & PACKING
# ============================================================================

@server.tool()
@handle_mcp_errors(json_output=True)
def skin_rag_pack(
    source_path: str,
    output_path: Optional[str] = None,
    metadata_path: Optional[str] = None,
    min_score: float = 0.0,
    overwrite: bool = False
) -> str:
    """
    Pack a folder of .png skins or a .zip archive (with optional .json/.csv metadata) into a
    single compact, portable SQLite FTS5 + 299-dim CIELAB float16 database (.sfpack / .db).
    """
    cfg = RagPackConfigSchema(
        source_path=source_path,
        output_path=output_path,
        metadata_path=metadata_path,
        min_score=min_score,
        overwrite=overwrite,
    )
    res = pack_rag_database(
        source_path=cfg.source_path,
        output_path=cfg.output_path,
        metadata_path=cfg.metadata_path,
        min_score=cfg.min_score,
        overwrite=cfg.overwrite,
    )
    return json.dumps(res, indent=2)


@server.tool()
@handle_mcp_errors(json_output=True)
def skin_search(
    query: str,
    limit: int = 5,
    min_quality: str = "medium",
    render_previews: bool = True
) -> str:
    """Search across indexed Minecraft skins using SQLite FTS5 BM25 relevance ranking."""
    rag = get_rag()
    if not rag.is_available:
        return json.dumps(rag.get_unavailable_response(query=query), indent=2)

    results = rag.search(query=query, limit=min(limit, 20), min_quality=min_quality, render_previews=render_previews)
    if not results:
        return json.dumps({
            "status": "empty",
            "message": f"No skins found matching query: '{query}'. Total skins in DB: {rag.count()}",
            "results": [],
        }, indent=2)

    return json.dumps({
        "status": "success",
        "query": query,
        "total_results": len(results),
        "results": results,
    }, indent=2)


@server.tool()
@handle_mcp_errors(json_output=True)
def skin_get_reference(
    skin_id: str,
    load_to_canvas: bool = False,
    as_ascii: bool = True
) -> str:
    """Retrieve full details for a reference skin by ID from the RAG dataset."""
    rag = get_rag()
    if not rag.is_available:
        return json.dumps(rag.get_unavailable_response(query=skin_id), indent=2)

    skin_data = rag.get_skin(skin_id, as_canvas=load_to_canvas, as_ascii=as_ascii)
    if not skin_data:
        return json.dumps({"status": "not_found", "error": f"Skin '{skin_id}' not found in RAG database."})

    if load_to_canvas and "canvas" in skin_data:
        with session.lock:
            session.push_undo(action=f"load_reference:{skin_id}")
            session.canvas = skin_data["canvas"]
            session.model = skin_data.get("model_type", "default")
            session.mark_dirty()

    resp: Dict[str, Any] = {
        "status": "success",
        "skin_id": skin_data["skin_id"],
        "title": skin_data.get("title"),
        "caption": skin_data.get("caption"),
        "model_type": skin_data.get("model_type", "default"),
        "loaded_to_active_canvas": load_to_canvas,
    }
    if as_ascii:
        resp["palette"] = skin_data.get("palette")
        resp["parts"] = skin_data.get("parts")

    return json.dumps(resp, indent=2)


@server.tool()
@handle_mcp_errors(json_output=True)
def skin_remix(
    base_skin_id: str,
    overlay_skin_id: str,
    parts_to_take: Optional[List[str]] = None,
    auto_fix: bool = True,
    save_path: Optional[str] = None
) -> str:
    """Remix two reference skins from the RAG dataset or file paths."""
    rag = get_rag()
    if not rag.is_available and not (os.path.exists(base_skin_id) and os.path.exists(overlay_skin_id)):
        return json.dumps(rag.get_unavailable_response(), indent=2)

    remixed_canvas, info = rag.remix_skins(
        base_skin_id=base_skin_id,
        overlay_skin_id=overlay_skin_id,
        parts_to_take=parts_to_take,
        auto_fix=auto_fix,
        save_path=save_path,
    )
    with session.lock:
        session.push_undo(action=f"remix:{base_skin_id}+{overlay_skin_id}")
        session.canvas = remixed_canvas
        session.mark_dirty()

    return json.dumps({
        "status": "success",
        "message": f"Successfully remixed '{base_skin_id}' with '{overlay_skin_id}'.",
        "preview_3d_path": info.get("preview_3d"),
        "saved_to": save_path,
    }, indent=2)


@server.tool()
@handle_mcp_errors(json_output=True)
def skin_rag_status() -> str:
    """Get the status of the SkinForge RAG database (number of indexed skins, database path)."""
    rag = get_rag()
    count = rag.count()
    if count == 0:
        info = rag.get_unavailable_response()
        info["database_size_mb"] = round(os.path.getsize(rag.db_path) / (1024 * 1024), 2) if os.path.exists(rag.db_path) else 0
        return json.dumps(info, indent=2)

    return json.dumps({
        "status": "ready",
        "available": True,
        "total_indexed_skins": count,
        "database_path": str(rag.db_path),
        "database_size_mb": round(os.path.getsize(rag.db_path) / (1024 * 1024), 2) if os.path.exists(rag.db_path) else 0,
    }, indent=2)


@server.tool()
@handle_mcp_errors(json_output=True)
def skin_part_search(
    category: str,
    query: str,
    limit: int = 5,
    min_quality: str = "medium",
    render_previews: bool = True
) -> str:
    """Search for specific anatomical components (hair, face, torso, arms, legs, outfit)."""
    rag = get_rag()
    if not rag.is_available:
        return json.dumps(rag.get_unavailable_response(query=query), indent=2)

    results = rag.part_search(
        category=category,
        query=query,
        limit=limit,
        min_quality=min_quality,
        render_previews=render_previews,
    )
    return json.dumps({
        "status": "success",
        "category": category,
        "query": query,
        "total_results": len(results),
        "results": results,
    }, indent=2)


@server.tool()
@handle_mcp_errors(json_output=True)
def skin_assemble(
    components: Dict[str, str],
    auto_blend_seams: bool = True,
    auto_fix: bool = True
) -> str:
    """Lego Constructor: Assemble a complete Minecraft skin from modular component sources."""
    rag = get_rag()
    resolved_components: Dict[str, Union[str, SkinCanvas]] = {}
    for mod, src in components.items():
        if src == "active":
            resolved_components[mod] = session.canvas
        else:
            if not os.path.exists(src) and not rag.is_available:
                return json.dumps(rag.get_unavailable_response(query=src), indent=2)
            resolved_components[mod] = src

    assembled_canvas, summary = rag.assemble_modules(
        components=resolved_components,
        base_canvas=session.canvas,
        auto_blend_seams=auto_blend_seams,
        auto_fix=auto_fix,
    )
    with session.lock:
        session.push_undo(action="assemble_skin")
        session.canvas = assembled_canvas
        session.mark_dirty()

    return json.dumps({
        "status": "success",
        "message": f"Successfully assembled skin from {list(components.keys())}.",
        "summary": summary,
        "preview_3d_path": summary.get("preview_3d_path"),
    }, indent=2)


@server.tool()
@handle_mcp_errors(json_output=True)
def skin_search_by_image(
    image_path: str,
    limit: int = 5,
    min_quality: str = "medium",
    render_previews: bool = True
) -> str:
    """Visual Reference Search: Find skins matching a concept image using 299-dim CIELAB pyramids."""
    if not os.path.exists(image_path):
        return json.dumps({"status": "error", "error": f"Reference image not found: {image_path}"})

    rag = get_rag()
    if not rag.is_available:
        return json.dumps(rag.get_unavailable_response(query=image_path), indent=2)

    results = rag.search_by_image(
        image_input=image_path,
        limit=limit,
        min_quality=min_quality,
        render_previews=render_previews,
    )
    return json.dumps({
        "status": "success",
        "query_image": image_path,
        "total_results": len(results),
        "results": results,
    }, indent=2)


# ============================================================================
# 4. DRAWING & PART MANIPULATION TOOLS (LLM ERGONOMIC)
# ============================================================================

@server.tool()
@handle_mcp_errors()
def skin_get_part_ascii(part_name: str, tolerance: int = 6) -> str:
    """Reverse-engineer an existing part's pixels into a clean ASCII grid string and palette dictionary."""
    err = _validate_part_name(part_name)
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
    part_name: Optional[str] = None
) -> str:
    """Clean up compression noise and isolated color artifacts."""
    with session.lock:
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
    target_part_name: Optional[str] = None
) -> str:
    """Import an individual anatomical part from an external skin file or RAG skin_id."""
    if part_name not in MINECRAFT_UV_MAP:
        return json.dumps({"error": f"Invalid part_name: '{part_name}'"})
    dst_name = target_part_name or part_name
    if dst_name not in MINECRAFT_UV_MAP:
        return json.dumps({"error": f"Invalid target_part_name: '{dst_name}'"})

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
    save_path: Optional[str] = None
) -> str:
    """Generate and assemble a complete 64x64 dual-layer Minecraft skin in a single atomic call."""
    with session.lock:
        session.push_undo(action="skin_build")
        session.canvas.model = "slim" if model_type and model_type.lower() == "slim" else "default"
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
@handle_mcp_errors()
def skin_set_part_ascii(
    part_name: str,
    ascii_grid: str,
    palette: Optional[Dict[str, Any]] = None,
    palette_name: Optional[str] = None
) -> str:
    """Draw a part using a multiline ASCII grid."""
    err = _validate_part_name(part_name)
    if err:
        return err

    chosen_palette: Dict[str, Any] = palette or {}
    if isinstance(chosen_palette, str):
        try:
            chosen_palette = json.loads(chosen_palette)
        except Exception:
            chosen_palette = {}

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
            return f"Error: Unknown palette_name '{palette_name}'."

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
    err = _validate_part_name(part_name)
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
    color: str
) -> str:
    """Draw a filled rectangle on a part."""
    err = _validate_part_name(part_name)
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
    err = _validate_part_name(part_name)
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
    err = _validate_part_name(part_name)
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
    direction: str = "vertical"
) -> str:
    """Apply a smooth linear color gradient across a part."""
    err = _validate_part_name(part_name)
    if err:
        return err
    with session.lock:
        session.push_undo(action=f"gradient:{part_name}")
        session.canvas.apply_gradient(part_name, start_color, end_color, direction=direction)
        session.mark_dirty()
    return f"Applied {direction} gradient ({start_color} -> {end_color}) on '{part_name}'. Live viewer updated."


@server.tool()
@handle_mcp_errors()
def skin_sample_reference(
    image_path: str,
    x: Optional[float] = None,
    y: Optional[float] = None,
    region: Optional[List[float]] = None,
    num_colors: int = 8
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
def skin_replace_color(
    old_color: str,
    new_color: str,
    part_name: Optional[str] = None,
    tolerance: int = 15,
    layer: str = "both"
) -> str:
    """Fuzzy replace occurrences of old_color with new_color within an RGB tolerance threshold."""
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
    layer: str = "both"
) -> str:
    """Vectorized Hue, Saturation, and Brightness adjustment across part(s) or entire skin."""
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
    layer: str = "both"
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
    pixels: List[Dict[str, Any]]
) -> str:
    """Efficiently set multiple individual pixels on a part in a single call."""
    err = _validate_part_name(part_name)
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
    top_n: int = 16
) -> str:
    """Inspect unique colors and frequency counts on a specific face or the entire skin canvas."""
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
    part_name: Optional[str] = None
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


def _execute_preset_on_canvas(canvas: SkinCanvas, preset_name: str, params: Optional[Dict[str, Any]] = None) -> None:
    p = params or {}
    if preset_name == "anime_eyes_2x2":
        draw_anime_eyes_2x2(
            canvas,
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
            canvas,
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
            canvas,
            part_name=p.get("part_name", "right_pants_right"),
            y_start=p.get("y_start", 2),
            flap_color=p.get("flap_color", "#26222e"),
            pouch_color=p.get("pouch_color", "#1e1a24"),
            buckle_color=p.get("buckle_color", "#9a32dc"),
        )
    elif preset_name == "hair_bangs":
        draw_hair_bangs(
            canvas,
            style=p.get("style", "cyberpunk"),
            hair_color=p.get("hair_color", "#1e1824"),
            highlight_color=p.get("highlight_color", "#9a3cd4"),
        )
    elif preset_name == "sneakers":
        draw_sneakers(
            canvas,
            limb=p.get("limb", "right_leg"),
            sole_color=p.get("sole_color", "#ffffff"),
            body_color=p.get("body_color", "#16141e"),
            accent_color=p.get("accent_color", "#9a32dc"),
        )
    elif preset_name == "headphones":
        draw_headphones(
            canvas,
            earcup_color=p.get("earcup_color", "#9a3cd4"),
            band_color=p.get("band_color", "#221c2c"),
            glow_color=p.get("glow_color", "#d264ff"),
        )
    else:
        raise ValueError(
            f"Unknown preset '{preset_name}'. Supported: anime_eyes_2x2, hoodie_drawstrings, "
            "cargo_pocket, hair_bangs, sneakers, headphones."
        )


@server.tool()
@handle_mcp_errors()
def skin_batch_actions(actions: List[Dict[str, Any]]) -> str:
    """Execute multiple skin authoring actions in a single atomic MCP call."""
    with session.lock:
        session.push_undo(action=f"batch_actions({len(actions)})")
        summary = []
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
                elif a_type == "apply_preset":
                    _execute_preset_on_canvas(session.canvas, str(act.preset_name), act.params)
                    summary.append(f"[{idx+1}] apply_preset '{act.preset_name}'")
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
                else:
                    summary.append(f"[{idx+1}] WARNING: Unknown action '{a_type}'")
                    continue
                success_count += 1
            except Exception as exc:
                summary.append(f"[{idx+1}] ERROR in action '{raw_act.get('action')}': {str(exc)}")

        session.mark_dirty()
    return f"Batch Execution Complete ({success_count}/{len(actions)} succeeded). Live viewer updated:\n" + "\n".join(summary)


# ============================================================================
# 5. HIGH-LEVEL PRESETS, TYPOGRAPHY & OUTFITS
# ============================================================================

@server.tool()
@handle_mcp_errors()
def skin_draw_text(
    part_name: str,
    text: str,
    x: int = 1,
    y: int = 1,
    color: str = "#ffffff",
    spacing: int = 1
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
    color: str = "#ffffff"
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
    trim_color: str = "#faf8fc"
) -> str:
    """Apply a complete coordinated full-body outfit macro across Layer 1 and Layer 2."""
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
    mirror_layer2: bool = True
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
    err = _validate_part_name(part_name)
    if err:
        return err
    with session.lock:
        session.push_undo(action=f"add_noise:{part_name}")
        session.canvas.add_noise(part_name, amount=amount)
        session.mark_dirty()
    return f"Injected microtexture (amount={amount}) on '{part_name}'. Live viewer updated."


@server.tool()
@handle_mcp_errors()
def skin_apply_preset(
    preset_name: str,
    params: Optional[Dict[str, Any]] = None
) -> str:
    """Apply a modular anatomical or clothing preset."""
    with session.lock:
        session.push_undo(action=f"apply_preset:{preset_name}")
        _execute_preset_on_canvas(session.canvas, preset_name, params)
        session.mark_dirty()
    return f"Successfully applied preset '{preset_name}'. Live viewer updated."


@server.tool()
@handle_mcp_errors()
def skin_clear_outer_layer(parts: Optional[List[str]] = None) -> str:
    """Clear all Layer 2 (Outer Overlay) parts or specific parts to transparent [0, 0, 0, 0]."""
    with session.lock:
        session.push_undo(action="clear_outer_layer")
        cleared = session.canvas.clear_layer(layer="outer", parts=parts)
        session.mark_dirty()
    return f"Cleared {cleared} outer parts to 100% transparency. Live viewer updated."


# ============================================================================
# 6. VALIDATION, SEAM AUDITING & AUTO-HEALING
# ============================================================================

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


# ============================================================================
# 7. PALETTES & COLOR ASSISTANT
# ============================================================================

@server.tool()
@handle_mcp_errors()
def skin_generate_color_ramp(base_color: str, steps: int = 5) -> str:
    """Generate a harmonious 5-step shading ramp from a single base hex or RGB color."""
    res = generate_color_ramp(base_color, steps=steps)
    lines = [f"Color Ramp for Base '{res['base_hex']}':"]
    for d in res["details"]:
        lines.append(f"  '{d['char']}': {d['hex']} {d['rgba']} (step {d['step']})")
    lines.append(f"\nCopyable ASCII Palette Dict:\n{json.dumps(res['palette'])}")
    return "\n".join(lines)


@server.tool()
@handle_mcp_errors()
def skin_list_palettes() -> str:
    """List all available built-in color palettes and their theme styles."""
    return (
        "Available Built-in Palettes:\n"
        "- 'TECHWEAR_CYBERPUNK': Syntren theme (dark obsidian fabrics, neon violet/lavender accents, silver chains, sneakers).\n"
        "- 'ANIME_SKIN': Curated skin tones ('light', 'base', 'midtone', 'shadow', 'deep').\n"
        "- 'CASUAL_STREETWEAR': Denim blues, cream/white fabrics, leather brown.\n"
        "- 'FANTASY_KNIGHT': Polished steel armor shades with gold trim specular highlights.\n"
    )


# ============================================================================
# 8. 3D WEB VIEWER INTEGRATION
# ============================================================================

@server.tool()
@handle_mcp_errors()
def viewer_start(port: int = 8080) -> str:
    """Launch the interactive Three.js 3D WebGL skin viewer with SSE real-time push in the background."""
    with session.lock:
        if session.viewer_process and session.viewer_process.poll() is None:
            return f"Viewer is already running at: http://localhost:{session.viewer_port}"

        viewer_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "viewer.py"))
        if not os.path.exists(viewer_script):
            viewer_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "viewer.py"))

        if not session.file_path:
            default_skin = os.path.abspath(os.path.join(PROJECT_ROOT, "skins", "skin_current.png"))
            session.canvas.export_png(default_skin)
            session.file_path = default_skin

        session.sync_live()

        env = os.environ.copy()
        env["SKINFORGE_VIEWER_PORT"] = str(port)
        env["SKINFORGE_NO_BROWSER"] = "1"

        proc = subprocess.Popen(
            [sys.executable, viewer_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(viewer_script),
            env=env,
        )
        session.viewer_process = proc
        session.viewer_port = port
        return (
            f"Started interactive 3D WebGL Studio viewer on http://localhost:{port} (PID {proc.pid}).\n"
            f"SSE Stream active at: http://localhost:{port}/api/events\n"
            f"Watching active skin file: '{session.file_path}'."
        )


@server.tool()
@handle_mcp_errors()
def viewer_status() -> str:
    """Check the status and URL of the 3D WebGL viewer server."""
    is_running = session.viewer_process and session.viewer_process.poll() is None
    if is_running:
        return f"Viewer is RUNNING at http://localhost:{session.viewer_port} (PID {session.viewer_process.pid}). Watching: '{session.file_path}'"
    return "Viewer is currently STOPPED. Start it using 'viewer_start'."


@server.tool()
@handle_mcp_errors()
def viewer_stop() -> str:
    """Terminate the background 3D WebGL viewer server process."""
    with session.lock:
        if session.viewer_process and session.viewer_process.poll() is None:
            session.viewer_process.terminate()
            session.viewer_process = None
            return "3D WebGL viewer stopped."
    return "Viewer was not running."


# ============================================================================
# 9. MCP RESOURCES & PROMPTS
# ============================================================================

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


@server.prompt("create-skin")
def prompt_create_skin() -> List[types.PromptMessage]:
    """Autonomous agent workflow prompt for designing a skin from scratch."""
    instructions = (
        "You are an expert Minecraft skin artist using SkinForge MCP server v1.3.0.\n\n"
        "RECOMMENDED WORKFLOW:\n"
        "1. Start by calling 'skin_new(template=\"base_body\", skin_tone=...)' to get a solid, 0-hole Layer 1.\n"
        "2. Paint the head and face with 'skin_set_part_ascii(\"head_front\", ...)' or presets.\n"
        "3. Design clothing on Layer 1 ('body_front', 'right_arm_front', 'right_leg_front').\n"
        "4. Mirror limbs with 'skin_mirror_limb(\"right_arm\", \"left_arm\")'.\n"
        "5. Add 3D relief on Layer 2 (bangs on 'hat_front' rows 0-3 only, hood on 'hat_top').\n"
        "6. Call 'skin_validate()'. If any warnings appear, call 'skin_auto_fix()'.\n"
        "7. Call 'skin_render_3d(preset=\"turnaround\")' to visually inspect your design.\n"
        "8. Call 'skin_save(file_path=...)' to save the final PNG."
    )
    return [types.PromptMessage(role="user", content=types.TextContent(type="text", text=instructions))]


@server.prompt("audit-and-fix-skin")
def prompt_audit_and_fix() -> List[types.PromptMessage]:
    """Workflow prompt for auditing and fixing an existing skin PNG."""
    instructions = (
        "You are auditing and fixing a Minecraft skin using SkinForge MCP v1.3.0.\n\n"
        "STEPS:\n"
        "1. Call 'skin_load(file_path=...)' to load the skin (64x32 legacy skins are auto-converted to 64x64).\n"
        "2. Call 'skin_validate()' and 'skin_aesthetic_audit()' to inspect the 4 Golden Rules and 6 metrics.\n"
        "3. Call 'skin_auto_fix()' to autonomously heal Rule 1, Rule 2, Rule 3, and Rule 4.\n"
        "4. Call 'skin_render_3d(preset=\"turnaround\")' to visually confirm the fixes.\n"
        "5. Save with 'skin_save()'."
    )
    return [types.PromptMessage(role="user", content=types.TextContent(type="text", text=instructions))]


def main() -> None:
    """Run the SkinForge MCP Server over stdio."""
    server.run("stdio")


if __name__ == "__main__":
    main()
