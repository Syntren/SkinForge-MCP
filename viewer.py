#!/usr/bin/env python3
"""
SkinForge Studio v1.3.0 — Real-Time 3D WebGL Viewer Server.

Features:
  - Server-Sent Events (SSE) endpoint `/api/events` on ThreadingHTTPServer for instant
    zero-polling push updates of skin texture, model ('classic'/'slim'), and 6-metric audit telemetry.
  - Fallback `/api/status` (and `/skin-status`) JSON endpoints.
  - Serves SkinForge Studio (`static/index.html`, `static/style.css`, `static/app.js`, `static/skinview3d.bundle.js`).
  - Atomic PNG I/O (`.tmp` + `os.replace`) ensuring zero corrupted texture reads.
"""

from __future__ import annotations

import base64
import json
import os
import queue
import socket
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
try:
    from http.server import ThreadingHTTPServer
except ImportError:
    ThreadingHTTPServer = HTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from skinforge import SkinCanvas, compute_aesthetic_score, get_rag
from skinforge.audit.validator import auto_fix_skin
from skinforge.core.canvas import atomic_save_png
from skinforge.core.session import atomic_write_text
from skinforge.core.uv import (
    detect_skin_model_from_array,
    get_uv_map,
    is_slim_model,
    load_skin_array,
)


class DaemonThreadingHTTPServer(ThreadingHTTPServer):
    """Multi-threaded HTTP server with daemon worker threads for SSE streaming."""
    daemon_threads = True
    allow_reuse_address = True


def get_skin_path() -> str:
    custom = os.environ.get("SKINFORGE_LIVE_SKIN")
    if custom and os.path.exists(custom):
        return custom
    candidates = [
        os.path.join(BASE_DIR, ".live_skin.png"),
        os.path.join(BASE_DIR, "skins", "skin_syntren.png"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def get_skin_model(skin_path: str) -> str:
    if not skin_path or not os.path.exists(skin_path):
        return "default"
    model_file = skin_path + ".model"
    if os.path.exists(model_file):
        try:
            with open(model_file, "r", encoding="utf-8") as f:
                val = f.read().strip().lower()
                if val in ("slim", "alex"):
                    return "slim"
                if val in ("default", "classic", "steve"):
                    return "default"
        except Exception:
            pass
    try:
        arr, _ = load_skin_array(skin_path)
        return detect_skin_model_from_array(arr)
    except Exception:
        return "default"


def build_viewer_telemetry(skin_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Build a complete, self-contained telemetry payload for SSE `/api/events` and `/api/status`.
    Includes base64 PNG data, model ('classic'/'slim'), 6-metric Aesthetic Score,
    unique color count, 4 Golden Rules status, and UV map coordinates.
    """
    path = skin_path or get_skin_path()
    if not path or not os.path.exists(path):
        return {
            "status": "empty",
            "mtime": 0,
            "size": 0,
            "model": "classic",
            "raw_model": "default",
            "skin_b64": None,
            "audit": None,
            "uv_map": {k: list(v) for k, v in get_uv_map("default").items()},
        }

    try:
        mtime = os.path.getmtime(path)
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            raw_bytes = f.read()
        b64_str = base64.b64encode(raw_bytes).decode("utf-8")
        raw_model = get_skin_model(path)
        ui_model = "slim" if is_slim_model(raw_model) else "classic"

        arr, _ = load_skin_array(raw_bytes)
        audit = compute_aesthetic_score(arr, model=raw_model, deduct_defects=True)
        uv_map = {k: list(v) for k, v in get_uv_map(raw_model).items()}

        return {
            "status": "ok",
            "mtime": mtime,
            "size": size,
            "model": ui_model,
            "raw_model": raw_model,
            "skin_b64": f"data:image/png;base64,{b64_str}",
            "audit": audit,
            "uv_map": uv_map,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "mtime": 0,
            "size": 0,
            "model": "classic",
            "raw_model": "default",
        }


class SSEBroadcaster:
    """Thread-safe Server-Sent Events (SSE) broadcaster watching live skin updates."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: List[queue.Queue] = []
        self._last_signature: Tuple[float, int, str] = (0.0, 0, "")
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=32)
        with self._lock:
            self._clients.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    def broadcast(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            try:
                if q.full():
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        pass
                q.put_nowait(payload)
            except Exception:
                pass

    def start_watcher(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._watch_loop, daemon=True)
            self._thread.start()

    def _watch_loop(self) -> None:
        while self._running:
            try:
                path = get_skin_path()
                if path and os.path.exists(path):
                    mtime = os.path.getmtime(path)
                    size = os.path.getsize(path)
                    model = get_skin_model(path)
                    sig = (mtime, size, model)
                    if sig != self._last_signature and size > 0:
                        self._last_signature = sig
                        telemetry = build_viewer_telemetry(path)
                        if telemetry.get("status") == "ok":
                            self.broadcast(telemetry)
            except Exception:
                pass
            time.sleep(0.06)


sse_broadcaster = SSEBroadcaster()


STATIC_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png",
    ".json": "application/json; charset=utf-8",
}


class SkinViewerServer(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def _send_json(self, data: Dict[str, Any], status_code: int = 200, head_only: bool = False) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_cors_headers()
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if not head_only:
            self.wfile.write(payload)

    def _serve_static_file(self, file_path: str, head_only: bool = False) -> None:
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_error(404, "Static file not found")
            return
        ext = os.path.splitext(file_path)[1].lower()
        mime = STATIC_MIME_TYPES.get(ext, "application/octet-stream")
        with open(file_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-cache")
        self.send_cors_headers()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self) -> None:
        self.do_GET(head_only=True)

    def do_GET(self, head_only: bool = False) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        skin_path = get_skin_path()

        if route in ("/", "/index.html"):
            index_path = os.path.join(BASE_DIR, "static", "index.html")
            self._serve_static_file(index_path, head_only=head_only)

        elif route.startswith("/static/"):
            rel_name = os.path.basename(route[len("/static/"):])
            static_file = os.path.join(BASE_DIR, "static", rel_name)
            self._serve_static_file(static_file, head_only=head_only)

        elif route == "/api/events":
            # Server-Sent Events (SSE) stream
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.send_cors_headers()
            self.end_headers()
            if head_only:
                return

            sse_broadcaster.start_watcher()
            client_q = sse_broadcaster.subscribe()
            try:
                # Immediately push initial state
                initial = build_viewer_telemetry(skin_path)
                msg = f"event: skin_update\ndata: {json.dumps(initial)}\n\n"
                self.wfile.write(msg.encode("utf-8"))
                self.wfile.flush()

                # Check if client requested single-shot SSE test via ?once=1
                query_params = parse_qs(parsed.query)
                if query_params.get("once", ["0"])[0] == "1":
                    return

                while True:
                    try:
                        event_data = client_q.get(timeout=10.0)
                        chunk = f"event: skin_update\ndata: {json.dumps(event_data)}\n\n"
                        self.wfile.write(chunk.encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                self.close_connection = True
                sse_broadcaster.unsubscribe(client_q)

        elif route in ("/api/status", "/skin-status"):
            telemetry = build_viewer_telemetry(skin_path)
            self._send_json(telemetry, head_only=head_only)

        elif route in ("/api/aesthetic_score", "/api/audit"):
            telemetry = build_viewer_telemetry(skin_path)
            audit = telemetry.get("audit") or {"score": 0.0, "tier": "unknown"}
            self._send_json(audit, head_only=head_only)

        elif route == "/skin-base64":
            if os.path.exists(skin_path):
                with open(skin_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                self._send_json(
                    {
                        "data": f"data:image/png;base64,{b64}",
                        "model": get_skin_model(skin_path),
                    },
                    head_only=head_only,
                )
            else:
                self.send_error(404, "Skin file not found")

        elif route == "/skin.png":
            if os.path.exists(skin_path):
                with open(skin_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_cors_headers()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if not head_only:
                    self.wfile.write(data)
            else:
                self.send_error(404, "Skin file not found")

        elif route == "/api/search_parts":
            query_params = parse_qs(parsed.query)
            category = query_params.get("category", ["hair"])[0]
            q = query_params.get("q", [""])[0]
            limit = int(query_params.get("limit", [6])[0])
            rag = get_rag()
            if not rag.is_available:
                self._send_json(rag.get_unavailable_response(query=q), head_only=head_only)
            else:
                try:
                    results = rag.part_search(category, q, limit=limit, min_quality="low", render_previews=False)
                    self._send_json({"status": "success", "results": results}, head_only=head_only)
                except Exception as exc:
                    self._send_json({"status": "error", "error": str(exc), "results": []}, head_only=head_only)

        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        skin_path = get_skin_path()

        if route == "/api/auto_fix":
            try:
                c = SkinCanvas(model=get_skin_model(skin_path))
                if os.path.exists(skin_path):
                    c.load_png(skin_path)
                fix_res = auto_fix_skin(c, ensure_relief=True)
                atomic_save_png(c.to_image(), skin_path)
                atomic_write_text(c.model, skin_path + ".model")
                telemetry = build_viewer_telemetry(skin_path)
                sse_broadcaster.broadcast(telemetry)
                self._send_json({"status": "success", "fix_summary": fix_res, "telemetry": telemetry})
            except Exception as exc:
                self._send_json({"status": "error", "error": str(exc)}, status_code=500)

        elif route == "/api/assemble":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8"))
                components = data.get("components", {})
                rag = get_rag()

                base_c = None
                if os.path.exists(skin_path):
                    base_c = SkinCanvas()
                    base_c.load_png(skin_path)

                target_canvas, summary = rag.assemble_modules(
                    components=components,
                    base_canvas=base_c,
                    auto_blend_seams=True,
                    auto_fix=True,
                )

                atomic_save_png(target_canvas.to_image(), skin_path)
                atomic_write_text(target_canvas.model, skin_path + ".model")
                telemetry = build_viewer_telemetry(skin_path)
                sse_broadcaster.broadcast(telemetry)

                self._send_json({
                    "status": "success",
                    "aesthetic_score": summary.get("aesthetic_score", 0.0),
                    "aesthetic_tier": summary.get("aesthetic_tier", "unknown"),
                    "seam_issues": summary.get("seam_issues_detected", 0),
                    "applied_modules": summary.get("applied_modules", []),
                    "telemetry": telemetry,
                })
            except Exception as exc:
                self._send_json({"status": "error", "error": str(exc)}, status_code=500)
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format: str, *args: Any) -> None:
        pass


def find_free_port(start_port: int = 8080) -> int:
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def main() -> None:
    req_port = int(os.environ.get("SKINFORGE_VIEWER_PORT", "8080"))
    port = find_free_port(req_port)
    server_address = ("127.0.0.1", port)
    httpd = DaemonThreadingHTTPServer(server_address, SkinViewerServer)
    sse_broadcaster.start_watcher()

    url = f"http://localhost:{port}"
    skin_path = get_skin_path()

    print("==================================================")
    print("  SkinForge Studio v1.3.0 — 3D WebGL Viewer (SSE)")
    print(f"  Server running at: {url}")
    print(f"  SSE Stream:        {url}/api/events")
    print(f"  Watching:          {skin_path}")
    print("  Press Ctrl+C to stop.")
    print("==================================================")

    if os.environ.get("SKINFORGE_NO_BROWSER") != "1":
        def open_browser() -> None:
            time.sleep(0.5)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=open_browser, daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping viewer server...")
        httpd.server_close()
        print("Server stopped.")


if __name__ == "__main__":
    main()
