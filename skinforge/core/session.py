"""
Thread-safe Session Manager, Atomic I/O, and Undo/Redo Stack for SkinForge (v1.3.0).

Manages the active in-memory SkinCanvas, thread synchronization via RLock,
in-memory undo_stack and redo_stack (up to 30 states), and atomic .tmp + os.replace()
disk synchronization for live WebGL viewer updates.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from typing import Any, Callable, Dict, List, Optional
import numpy as np
from PIL import Image

from .canvas import MAX_HISTORY_STATES, CanvasSnapshot, SkinCanvas, atomic_save_png
from .uv import is_slim_model

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def atomic_write_text(text: str, path: str) -> str:
    """Atomically write UTF-8 text to path via .tmp file + os.replace()."""
    target = os.path.abspath(os.path.expanduser(str(path)))
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = f"{target}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, target)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    return target


class SkinSession:
    """Thread-safe active skin canvas session with atomic I/O and 30-state undo/redo stacks."""

    def __init__(self, project_root: Optional[str] = None):
        self._lock = threading.RLock()
        self.project_root = project_root or PROJECT_ROOT
        self._canvas = SkinCanvas()
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []

        default_skin = os.path.join(self.project_root, "skins", "skin_syntren.png")
        custom_skin = os.environ.get("SKINFORGE_DEFAULT_SKIN")
        if custom_skin and os.path.exists(custom_skin):
            default_skin = custom_skin

        self.file_path: Optional[str] = default_skin if os.path.exists(default_skin) else None
        self.is_dirty: bool = False
        self.model: str = "default"
        self.viewer_process: Optional[subprocess.Popen] = None
        self.viewer_port: int = int(os.environ.get("SKINFORGE_VIEWER_PORT", "8080"))
        self.project_targets: List[str] = [
            os.path.join(self.project_root, "skins", "skin_syntren.png"),
        ]
        if custom_skin and custom_skin not in self.project_targets:
            self.project_targets.append(custom_skin)

        live_override = os.environ.get("SKINFORGE_LIVE_SKIN")
        self.live_file: str = live_override if live_override else os.path.join(self.project_root, ".live_skin.png")

        from ..templates import create_base_body

        if self.file_path and os.path.exists(self.file_path):
            try:
                self._canvas.load_png(self.file_path)
                self.model = self._canvas.model
                self.sync_live()
            except Exception as exc:
                sys.stderr.write(f"[SkinForge] Warning loading default skin: {exc}\n")
                create_base_body(self._canvas, skin_tone="fair")
        else:
            create_base_body(self._canvas, skin_tone="fair")

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    @property
    def canvas(self) -> SkinCanvas:
        return self._canvas

    @canvas.setter
    def canvas(self, new_canvas: SkinCanvas) -> None:
        with self._lock:
            if hasattr(self, "_canvas") and self._canvas is not None and new_canvas is not self._canvas:
                if not new_canvas.undo_stack and self._canvas.undo_stack:
                    new_canvas.undo_stack = list(self._canvas.undo_stack[-MAX_HISTORY_STATES:])
                if not new_canvas.redo_stack and self._canvas.redo_stack:
                    new_canvas.redo_stack = list(self._canvas.redo_stack[-MAX_HISTORY_STATES:])
                if not new_canvas.checkpoints and self._canvas.checkpoints:
                    new_canvas.checkpoints = dict(self._canvas.checkpoints)
            self._canvas = new_canvas
            self.model = new_canvas.model

    @property
    def undo_stack(self) -> List[CanvasSnapshot]:
        return self._canvas.undo_stack

    @property
    def redo_stack(self) -> List[CanvasSnapshot]:
        return self._canvas.redo_stack

    def push_undo(self, action: str = "edit") -> None:
        """Thread-safely push current state onto undo_stack (max 30 states)."""
        with self._lock:
            self._canvas.push_undo(action=action)

    def undo(self) -> bool:
        """Thread-safely revert to previous state from undo_stack."""
        with self._lock:
            ok = self._canvas.undo()
            if ok:
                self.model = self._canvas.model
                self.mark_dirty()
            return ok

    def redo(self) -> bool:
        """Thread-safely reapply state from redo_stack."""
        with self._lock:
            ok = self._canvas.redo()
            if ok:
                self.model = self._canvas.model
                self.mark_dirty()
            return ok

    def get_history(self) -> Dict[str, Any]:
        """Return thread-safe structured undo/redo history and checkpoints."""
        with self._lock:
            return self._canvas.get_history_summary()

    def register_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def sync_live(self) -> None:
        """
        Atomically write current in-memory canvas and model metadata to live staging files
        (.tmp + os.replace) so viewer.py never reads a partial or corrupted PNG texture.
        """
        with self._lock:
            try:
                atomic_save_png(self._canvas.to_image(), self.live_file)
                atomic_write_text(self._canvas.model, self.live_file + ".model")
                for cb in list(self._listeners):
                    try:
                        cb({"model": self._canvas.model, "live_file": self.live_file})
                    except Exception:
                        pass
            except Exception as exc:
                sys.stderr.write(f"[SkinForge] Warning syncing live canvas: {exc}\n")

    def mark_dirty(self) -> None:
        """Mark session dirty and atomically sync live viewer texture."""
        with self._lock:
            self.is_dirty = True
            self.model = self._canvas.model
            self.sync_live()

    def reset_blank(self) -> None:
        with self._lock:
            self._canvas = SkinCanvas()
            self.model = "default"
            self.file_path = None
            self.mark_dirty()

    def reset_template(self, skin_tone: str = "fair") -> None:
        from ..templates import create_base_body
        with self._lock:
            self._canvas = SkinCanvas()
            self.model = "default"
            create_base_body(self._canvas, skin_tone=skin_tone)
            self.file_path = None
            self.mark_dirty()
