"""
Session, History, Checkpoints, File I/O & 3D WebGL Viewer MCP Tools (v2.0.0).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

from ..audit import SkinValidator, compute_aesthetic_score
from ..core import BASE_PARTS, OUTER_PARTS
from ..presets import draw_anime_eyes_2x2
from ..renderer import (
    render_3d_turnaround,
    render_bottom_up,
    render_composite_2d,
    render_turntable_gif,
)
from .protocol import MCPServer, __version__, handle_mcp_errors


def register_session_tools(server: MCPServer, session: Any, project_root: str) -> Dict[str, Any]:
    """Register session lifecycle, undo/redo history, checkpoint, and 3D viewer tools."""

    @server.tool()
    @handle_mcp_errors()
    def skin_new(
        template: str = "base_body",
        skin_tone: str = "fair",
        hair_color: str = "#221c28",
        eye_color: str = "#9a3cd4",
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
        update_previews: bool = True,
    ) -> str:
        """
        Atomically export the current active canvas to a 64x64 RGBA Minecraft skin PNG file.
        Synchronizes across configured targets and optionally regenerates 2D/3D previews.
        """
        with session.lock:
            target = file_path or session.file_path or os.path.join(project_root, "skins", "skin_syntren.png")
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
                    extra_msgs.append(
                        f"Rendered previews in: '{base_dir}' (2D composite, 3D turnaround, bottom-up, turntable 360 GIF)"
                    )
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
        """Inspect the current session's in-memory undo_stack, redo_stack (up to 30 states), and named checkpoints."""
        hist = session.get_history()
        return json.dumps({"status": "success", **hist}, indent=2)

    @server.tool()
    @handle_mcp_errors()
    def viewer_start(port: int = 8080) -> str:
        """Launch the interactive Three.js 3D WebGL skin viewer with SSE real-time push in the background."""
        with session.lock:
            if session.viewer_process and session.viewer_process.poll() is None:
                return f"Viewer is already running at: http://localhost:{session.viewer_port}"

            viewer_script = os.path.abspath(os.path.join(project_root, "viewer.py"))
            if not os.path.exists(viewer_script):
                viewer_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "viewer.py"))

            if not session.file_path:
                default_skin = os.path.abspath(os.path.join(project_root, "skins", "skin_current.png"))
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

    return {
        "skin_new": skin_new,
        "skin_load": skin_load,
        "skin_save": skin_save,
        "skin_get_session_info": skin_get_session_info,
        "skin_checkpoint": skin_checkpoint,
        "skin_restore_checkpoint": skin_restore_checkpoint,
        "skin_undo": skin_undo,
        "skin_redo": skin_redo,
        "skin_history": skin_history,
        "viewer_start": viewer_start,
        "viewer_status": viewer_status,
        "viewer_stop": viewer_stop,
    }
