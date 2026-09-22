#!/usr/bin/env python3
"""
Interactive 3D Minecraft Skin Viewer for SkinForge.
Features real-time WebGL rendering, walk/run animations, layer toggles, right-click panning, and live auto-reload.
Run with: python3 viewer.py OR python3 SkinForge/viewer.py
"""

import sys
import os
import json
import time
import socket
import base64
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)

def get_skin_path():
    candidates = [
        os.path.join(BASE_DIR, ".live_skin.png"),
        os.path.join(PARENT_DIR, ".live_skin.png"),
        os.path.join(PARENT_DIR, "skin_syntren.png"),
        os.path.join(BASE_DIR, "skins", "skin_syntren.png"),
        os.path.join(BASE_DIR, "skin_syntren.png"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[2]

def get_static_bundle():
    candidates = [
        os.path.join(BASE_DIR, "static", "skinview3d.bundle.js"),
        os.path.join(PARENT_DIR, "SkinForge", "static", "skinview3d.bundle.js"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]

HTML_PAGE = """<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SkinForge - 3D Minecraft Skin Viewer</title>
    <script src="/static/skinview3d.bundle.js"></script>
    <script>
        // Fallback to CDN if local bundle fails
        if (typeof skinview3d === 'undefined') {
            document.write('<script src="https://cdn.jsdelivr.net/npm/skinview3d@3.0.1/bundles/skinview3d.bundle.js"><\\/script>');
        }
    </script>
    <style>
        :root {
            --bg: #0e0d14;
            --panel: rgba(22, 19, 30, 0.9);
            --border: #2e2640;
            --neon: #9a32dc;
            --neon-bright: #be50fa;
            --text: #e6e2f0;
            --text-dim: #988fa8;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            user-select: none;
        }

        body {
            background-color: var(--bg);
            color: var(--text);
            overflow: hidden;
            width: 100vw;
            height: 100vh;
            display: flex;
        }

        #canvas-container {
            flex: 1;
            height: 100vh;
            position: relative;
            background: radial-gradient(circle at center, #1b1728 0%, #0c0b12 85%);
            overflow: hidden;
        }

        canvas#skin_container {
            width: 100%;
            height: 100%;
            display: block;
            cursor: grab;
        }

        canvas#skin_container:active {
            cursor: grabbing;
        }

        #ui-panel {
            width: 340px;
            height: 100%;
            background: var(--panel);
            backdrop-filter: blur(16px);
            border-left: 1px solid var(--border);
            padding: 24px 20px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            overflow-y: auto;
            z-index: 10;
            box-shadow: -8px 0 32px rgba(0, 0, 0, 0.4);
        }

        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }

        .header h1 {
            font-size: 20px;
            font-weight: 700;
            color: #fff;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .header h1 span {
            color: var(--neon-bright);
            text-shadow: 0 0 12px rgba(190, 80, 250, 0.5);
        }

        .badge {
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 12px;
            background: rgba(154, 50, 220, 0.15);
            color: var(--neon-bright);
            border: 1px solid rgba(190, 80, 250, 0.3);
        }

        .section {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .section-title {
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-dim);
        }

        .btn-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }

        button {
            background: #1c1828;
            color: var(--text);
            border: 1px solid var(--border);
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }

        button:hover {
            background: #28223a;
            border-color: var(--neon);
            color: #fff;
            transform: translateY(-1px);
        }

        button:active {
            transform: translateY(0);
        }

        button.active {
            background: linear-gradient(135deg, var(--neon) 0%, #7b1fa2 100%);
            border-color: var(--neon-bright);
            color: #fff;
            box-shadow: 0 0 16px rgba(154, 50, 220, 0.4);
        }

        .toggle-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 12px;
            background: rgba(28, 24, 40, 0.6);
            border-radius: 8px;
            border: 1px solid rgba(46, 38, 64, 0.6);
        }

        .toggle-row label {
            font-size: 13px;
            cursor: pointer;
        }

        .toggle-row input[type="checkbox"] {
            accent-color: var(--neon-bright);
            width: 16px;
            height: 16px;
            cursor: pointer;
        }

        .status-box {
            background: #13111c;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            font-size: 12px;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 6px;
            font-weight: 500;
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 8px #10b981;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.15); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }

        .status-time {
            color: var(--text-dim);
            font-size: 11px;
        }

        .footer {
            margin-top: auto;
            padding-top: 16px;
            border-top: 1px solid var(--border);
            font-size: 11px;
            color: var(--text-dim);
            text-align: center;
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div id="canvas-container">
        <canvas id="skin_container"></canvas>
    </div>

    <div id="ui-panel">
        <div class="header">
            <h1>Skin<span>Forge</span></h1>
            <div class="badge">3D Viewer</div>
        </div>

        <!-- Animations -->
        <div class="section">
            <div class="section-title">Animations</div>
            <div class="btn-grid">
                <button id="btn-walk" onclick="setAnimation('walk')">🚶 Walk</button>
                <button id="btn-run" onclick="setAnimation('run')">🏃 Run</button>
                <button id="btn-spin" onclick="toggleSpin()">🔄 Rotate</button>
                <button id="btn-idle" class="active" onclick="setAnimation('idle')">⏸️ Pause</button>
            </div>
        </div>

        <!-- Camera Angles -->
        <div class="section">
            <div class="section-title">Camera Angles</div>
            <div class="btn-grid">
                <button onclick="setCameraView('front')">Front</button>
                <button onclick="setCameraView('back')">Back</button>
                <button onclick="setCameraView('left')">Profile (Left)</button>
                <button onclick="setCameraView('right')">Profile (Right)</button>
            </div>
        </div>

        <!-- Skin Layers -->
        <div class="section">
            <div class="section-title">Layer Visibility</div>
            <div class="toggle-row">
                <label for="tog-inner">Layer 1 (Base Body)</label>
                <input type="checkbox" id="tog-inner" checked onchange="updateLayers()">
            </div>
            <div class="toggle-row">
                <label for="tog-outer">Layer 2 (3D Overlay)</label>
                <input type="checkbox" id="tog-outer" checked onchange="updateLayers()">
            </div>
        </div>

        <!-- Texture Sync -->
        <div class="section">
            <div class="section-title">Live Texture Sync</div>
            <button onclick="reloadSkinManual()" style="width: 100%;">🔄 Refresh Skin Now</button>
            <div class="status-box">
                <div class="status-indicator">
                    <div class="pulse-dot" id="live-dot"></div>
                    <span id="live-text">Live auto-reload active</span>
                </div>
                <div class="status-time" id="last-update">Last updated: Just now</div>
            </div>
        </div>

        <div class="footer">
            3D Navigation:<br>
            • Left Mouse: Rotate camera<br>
            • Right Mouse: Pan view<br>
            • Scroll Wheel: Zoom in / out
        </div>
    </div>

    <script>
        let viewer;
        let isSpinning = false;
        let lastMtime = 0;

        function initViewer() {
            const container = document.getElementById("canvas-container");
            const canvas = document.getElementById("skin_container");
            const w = container.clientWidth || (window.innerWidth - 340);
            const h = container.clientHeight || window.innerHeight;

            viewer = new skinview3d.SkinViewer({
                canvas: canvas,
                width: w,
                height: h
            });

            // Lighting & controls
            viewer.fov = 60;
            viewer.zoom = 0.9;
            viewer.autoRotate = false;
            viewer.autoRotateSpeed = 1.5;

            // Enable right-click panning and configure OrbitControls
            if (viewer.controls) {
                viewer.controls.enablePan = true;
                viewer.controls.panSpeed = 1.2;
                viewer.controls.screenSpacePanning = true;
            }

            // Prevent browser context menu on right-click on the canvas
            canvas.addEventListener("contextmenu", (e) => e.preventDefault());

            // Handle window resizing
            window.addEventListener("resize", () => {
                const nw = container.clientWidth || (window.innerWidth - 340);
                const nh = container.clientHeight || window.innerHeight;
                viewer.width = nw;
                viewer.height = nh;
            });

            // Set default view: front 3/4
            setCameraView("front_3d");

            // Load skin via base64 API for 100% reliability without CORS or caching bugs
            loadSkinFromSource();

            // Start live mtime watcher (300ms for near-instant reactivity)
            checkSkinUpdate();
            setInterval(checkSkinUpdate, 300);
        }

        function loadSkinFromSource() {
            fetch("/skin-base64?t=" + Date.now())
                .then(r => r.json())
                .then(data => {
                    if (data && data.data) {
                        viewer.loadSkin(data.data, {
                            model: "default",
                            makeVisible: true
                        }).then(() => {
                            updateLayers();
                            document.getElementById("last-update").innerText = "Last updated: " + new Date().toLocaleTimeString();
                        });
                    }
                })
                .catch(err => {
                    console.error("Skin loading failed:", err);
                    // Fallback to direct URL
                    viewer.loadSkin("/skin.png?t=" + Date.now());
                });
        }

        function setAnimation(type) {
            document.querySelectorAll("#btn-walk, #btn-run, #btn-idle").forEach(b => b.classList.remove("active"));
            
            if (viewer.animation) {
                viewer.animation.paused = true;
                viewer.animation = null;
            }

            if (type === 'walk') {
                document.getElementById("btn-walk").classList.add("active");
                viewer.animation = new skinview3d.WalkingAnimation();
                viewer.animation.speed = 0.8;
            } else if (type === 'run') {
                document.getElementById("btn-run").classList.add("active");
                viewer.animation = new skinview3d.RunningAnimation();
                viewer.animation.speed = 1.0;
            } else {
                document.getElementById("btn-idle").classList.add("active");
            }
        }

        function toggleSpin() {
            isSpinning = !isSpinning;
            viewer.autoRotate = isSpinning;
            const btn = document.getElementById("btn-spin");
            isSpinning ? btn.classList.add("active") : btn.classList.remove("active");
        }

        function setCameraView(view) {
            // 1. Stop autoRotate if active
            if (isSpinning) {
                isSpinning = false;
                viewer.autoRotate = false;
                const spinBtn = document.getElementById("btn-spin");
                if (spinBtn) spinBtn.classList.remove("active");
            }

            // 2. Reset player wrapper rotation so character is facing default orientation
            if (viewer.playerWrapper) {
                viewer.playerWrapper.rotation.set(0, 0, 0);
            }

            // 3. Reset controls target to center
            if (viewer.controls) {
                viewer.controls.target.set(0, 0, 0);
            }

            // 4. Set camera position
            if (view === 'front') {
                viewer.camera.position.set(0, 0, 60);
            } else if (view === 'front_3d') {
                viewer.camera.position.set(-25, 12, 50);
            } else if (view === 'back') {
                viewer.camera.position.set(0, 0, -60);
            } else if (view === 'left') {
                viewer.camera.position.set(60, 0, 0);
            } else if (view === 'right') {
                viewer.camera.position.set(-60, 0, 0);
            }

            viewer.camera.lookAt(0, 0, 0);
            if (viewer.controls && typeof viewer.controls.update === 'function') {
                viewer.controls.update();
            }
        }

        function updateLayers() {
            const inner = document.getElementById("tog-inner").checked;
            const outer = document.getElementById("tog-outer").checked;
            if (viewer && viewer.playerObject && viewer.playerObject.skin) {
                const skin = viewer.playerObject.skin;
                if (typeof skin.setInnerLayerVisible === 'function') {
                    skin.setInnerLayerVisible(inner);
                }
                if (typeof skin.setOuterLayerVisible === 'function') {
                    skin.setOuterLayerVisible(outer);
                }
                skin.traverse(child => {
                    if (child.name === 'inner') child.visible = inner;
                    if (child.name === 'outer') child.visible = outer;
                });
            }
        }

        function reloadSkinManual() {
            loadSkinFromSource();
        }

        async function checkSkinUpdate() {
            try {
                const resp = await fetch("/skin-status");
                if (resp.ok) {
                    const data = await resp.json();
                    if (lastMtime === 0) {
                        lastMtime = data.mtime;
                    } else if (data.mtime !== lastMtime) {
                        lastMtime = data.mtime;
                        loadSkinFromSource();
                        const dot = document.getElementById("live-dot");
                        dot.style.background = "#be50fa";
                        setTimeout(() => dot.style.background = "#10b981", 1000);
                    }
                }
            } catch (e) {
                // Ignore transient network errors
            }
        }

        window.onload = initViewer;
    </script>
</body>
</html>
"""

class SkinViewerServer(BaseHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_HEAD(self):
        self.do_GET(head_only=True)

    def do_GET(self, head_only=False):
        skin_path = get_skin_path()
        bundle_path = get_static_bundle()

        if self.path == "/" or self.path.startswith("/?"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_cors_headers()
            self.end_headers()
            if not head_only:
                self.wfile.write(HTML_PAGE.encode("utf-8"))

        elif self.path.startswith("/skin-base64"):
            if os.path.exists(skin_path):
                with open(skin_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                payload = json.dumps({"data": f"data:image/png;base64,{b64}"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_cors_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if not head_only:
                    self.wfile.write(payload)
            else:
                self.send_error(404, "Skin file not found")

        elif self.path.startswith("/skin.png"):
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

        elif self.path.startswith("/skin-status"):
            mtime = os.path.getmtime(skin_path) if os.path.exists(skin_path) else 0
            size = os.path.getsize(skin_path) if os.path.exists(skin_path) else 0
            payload = json.dumps({"mtime": mtime, "size": size}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_cors_headers()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if not head_only:
                self.wfile.write(payload)

        elif self.path.startswith("/static/skinview3d.bundle.js"):
            if os.path.exists(bundle_path):
                with open(bundle_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_cors_headers()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if not head_only:
                    self.wfile.write(data)
            else:
                self.send_error(404, "Static bundle not found")
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        # Silence routine request logging for clean terminal
        pass


def find_free_port(start_port=8080):
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def main():
    port = find_free_port(8080)
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, SkinViewerServer)
    url = f"http://localhost:{port}"
    skin_path = get_skin_path()

    print(f"==================================================")
    print(f"  SkinForge Interactive 3D Web Viewer")
    print(f"  Server running at: {url}")
    print(f"  Watching: {skin_path}")
    print(f"  Controls: Left drag = Rotate | Right drag = Pan | Scroll = Zoom")
    print(f"  Press Ctrl+C to stop.")
    print(f"==================================================")

    def open_browser():
        time.sleep(0.5)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping viewer server...")
        httpd.server_close()
        print("Server stopped.")


if __name__ == "__main__":
    main()
