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
try:
    from http.server import ThreadingHTTPServer
except ImportError:
    ThreadingHTTPServer = HTTPServer
from urllib.parse import parse_qs, urlparse
import threading
from PIL import Image
import numpy as np
from skinforge import SkinCanvas, get_rag, compute_aesthetic_score

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

def get_skin_path():
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

def get_skin_model(skin_path):
    if not skin_path or not os.path.exists(skin_path):
        return "default"
    model_file = skin_path + ".model"
    if os.path.exists(model_file):
        try:
            with open(model_file, "r") as f:
                val = f.read().strip().lower()
                if val in ("slim", "default"):
                    return val
        except Exception:
            pass
    try:
        im = Image.open(skin_path).convert("RGBA")
        arr = np.array(im)
        if arr.shape[0] >= 64 and arr.shape[1] >= 56:
            r_unused = np.max(arr[20:32, 54:56, 3])
            l_unused = np.max(arr[52:64, 46:48, 3])
            if r_unused == 0 and l_unused == 0:
                return "slim"
    except Exception:
        pass
    return "default"

def get_static_bundle():
    return os.path.join(BASE_DIR, "static", "skinview3d.bundle.js")

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

        /* Tabs Bar & Lego Constructor UI */
        .tabs-bar {
            display: flex;
            background: #14111f;
            border-radius: 8px;
            padding: 3px;
            border: 1px solid var(--border);
            gap: 4px;
        }

        .tab-btn {
            flex: 1;
            padding: 8px 6px;
            font-size: 11px;
            font-weight: 600;
            border-radius: 6px;
            border: none;
            background: transparent;
            color: var(--text-dim);
            cursor: pointer;
            transition: all 0.2s;
        }

        .tab-btn.active {
            background: var(--neon);
            color: #fff;
            box-shadow: 0 0 10px rgba(154, 50, 220, 0.4);
        }

        .tab-content {
            display: flex;
            flex-direction: column;
            gap: 14px;
        }

        .mod-box {
            display: flex;
            flex-direction: column;
            gap: 6px;
            background: #13111c;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px;
        }

        .mod-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            font-weight: 600;
            color: var(--text);
        }

        .mod-input-row {
            display: flex;
            gap: 6px;
        }

        .mod-input {
            flex: 1;
            background: #1c1828;
            border: 1px solid var(--border);
            border-radius: 6px;
            color: #fff;
            padding: 6px 8px;
            font-size: 12px;
            outline: none;
        }

        .mod-input:focus {
            border-color: var(--neon-bright);
        }

        .mod-btn {
            padding: 6px 10px;
            font-size: 11px;
            background: #252033;
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            cursor: pointer;
        }

        .mod-btn:hover {
            border-color: var(--neon);
            color: #fff;
        }

        .mod-results {
            display: flex;
            flex-direction: column;
            gap: 4px;
            max-height: 100px;
            overflow-y: auto;
            margin-top: 4px;
        }

        .mod-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 4px 8px;
            background: #1a1626;
            border: 1px solid #2e2640;
            border-radius: 4px;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.15s;
        }

        .mod-item:hover {
            border-color: var(--neon);
            background: #251d38;
        }

        .mod-item.selected {
            border-color: var(--neon-bright);
            background: rgba(154, 50, 220, 0.3);
            color: #fff;
            font-weight: 600;
        }

        .btn-assemble {
            background: linear-gradient(135deg, #af36f8 0%, #7b1fa2 100%);
            color: #fff;
            padding: 12px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 13px;
            border: 1px solid #c05cff;
            box-shadow: 0 0 16px rgba(175, 54, 248, 0.4);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            width: 100%;
        }

        .btn-assemble:hover {
            filter: brightness(1.15);
            transform: translateY(-1px);
        }

        .score-box {
            background: #14111f;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            font-size: 11px;
        }

        .score-badge {
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            text-transform: uppercase;
            font-weight: 700;
            background: #10b981;
            color: #000;
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

        <!-- Mode Tabs -->
        <div class="tabs-bar">
            <button id="tab-btn-controls" class="tab-btn active" onclick="switchTab('controls')">🕹️ 3D Controls</button>
            <button id="tab-btn-lego" class="tab-btn" onclick="switchTab('lego')">🧩 Lego Constructor</button>
        </div>

        <!-- Tab 1: 3D Controls -->
        <div id="tab-controls-content" class="tab-content">

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

        </div><!-- End tab-controls-content -->

        <!-- Tab 2: Lego Constructor -->
        <div id="tab-lego-content" class="tab-content" style="display: none;">
            <!-- Hair Module -->
            <div class="mod-box">
                <div class="mod-header">
                    <span>💇 Hair / Hairstyle</span>
                    <span id="sel-hair" style="color: var(--neon-bright); font-size: 10px;">Default</span>
                </div>
                <div class="mod-input-row">
                    <input type="text" id="input-hair" class="mod-input" placeholder="e.g. purple anime, ponytail" onkeydown="if(event.key==='Enter') searchModule('hair')">
                    <button class="mod-btn" onclick="searchModule('hair')">Find</button>
                </div>
                <div id="results-hair" class="mod-results"></div>
            </div>

            <!-- Face Module -->
            <div class="mod-box">
                <div class="mod-header">
                    <span>👀 Face / Eyes</span>
                    <span id="sel-face" style="color: var(--neon-bright); font-size: 10px;">Default</span>
                </div>
                <div class="mod-input-row">
                    <input type="text" id="input-face" class="mod-input" placeholder="e.g. violet eyes, mask" onkeydown="if(event.key==='Enter') searchModule('face')">
                    <button class="mod-btn" onclick="searchModule('face')">Find</button>
                </div>
                <div id="results-face" class="mod-results"></div>
            </div>

            <!-- Torso Module -->
            <div class="mod-box">
                <div class="mod-header">
                    <span>👔 Torso / Outfit</span>
                    <span id="sel-torso" style="color: var(--neon-bright); font-size: 10px;">Default</span>
                </div>
                <div class="mod-input-row">
                    <input type="text" id="input-torso" class="mod-input" placeholder="e.g. tuxedo, hoodie, suit" onkeydown="if(event.key==='Enter') searchModule('torso')">
                    <button class="mod-btn" onclick="searchModule('torso')">Find</button>
                </div>
                <div id="results-torso" class="mod-results"></div>
            </div>

            <!-- Legs Module -->
            <div class="mod-box">
                <div class="mod-header">
                    <span>👖 Legs / Pants</span>
                    <span id="sel-legs" style="color: var(--neon-bright); font-size: 10px;">Default</span>
                </div>
                <div class="mod-input-row">
                    <input type="text" id="input-legs" class="mod-input" placeholder="e.g. tailored pants, cargo" onkeydown="if(event.key==='Enter') searchModule('legs')">
                    <button class="mod-btn" onclick="searchModule('legs')">Find</button>
                </div>
                <div id="results-legs" class="mod-results"></div>
            </div>

            <!-- Assemble Button -->
            <button class="btn-assemble" onclick="assembleCharacter()">
                ⚡ Assemble & Harmonize
            </button>

            <!-- Quality Score Display -->
            <div class="score-box" id="lego-score-box">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 600;">Aesthetic Score</span>
                    <span class="score-badge" id="lego-score-badge">Top Tier</span>
                </div>
                <div style="font-size: 16px; font-weight: 700; color: #fff;" id="lego-score-val">1.0 / 1.0</div>
                <div style="color: var(--text-dim); font-size: 10px;" id="lego-score-details">3D Relief: 28% | Seams: 0 errors</div>
            </div>
        </div><!-- End tab-lego-content -->

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

        let currentSkinModel = "default";

        function loadSkinFromSource(modelOverride) {
            if (modelOverride) {
                currentSkinModel = modelOverride;
            }
            fetch("/skin-base64?t=" + Date.now())
                .then(r => r.json())
                .then(data => {
                    if (data && data.data) {
                        viewer.loadSkin(data.data, {
                            model: currentSkinModel,
                            makeVisible: true
                        }).then(() => {
                            updateLayers();
                            document.getElementById("last-update").innerText = "Last updated: " + new Date().toLocaleTimeString() + " (" + currentSkinModel + ")";
                        });
                    }
                })
                .catch(err => {
                    console.error("Skin loading failed:", err);
                    // Fallback to direct URL
                    viewer.loadSkin("/skin.png?t=" + Date.now(), { model: currentSkinModel });
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
                    const modelChanged = data.model && data.model !== currentSkinModel;
                    if (modelChanged) {
                        currentSkinModel = data.model;
                    }
                    if (lastMtime === 0 || modelChanged) {
                        lastMtime = data.mtime;
                        loadSkinFromSource();
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

        
        const activeModules = {};

        function switchTab(tab) {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            if (tab === 'controls') {
                document.getElementById("tab-btn-controls").classList.add("active");
                document.getElementById("tab-controls-content").style.display = "flex";
                document.getElementById("tab-lego-content").style.display = "none";
            } else {
                document.getElementById("tab-btn-lego").classList.add("active");
                document.getElementById("tab-controls-content").style.display = "none";
                document.getElementById("tab-lego-content").style.display = "flex";
            }
        }

        async function searchModule(category) {
            const input = document.getElementById("input-" + category);
            const q = input.value.trim();
            if (!q) return;

            const resDiv = document.getElementById("results-" + category);
            resDiv.innerHTML = "<div style='color: var(--text-dim); padding: 4px;'>Searching 900k skins...</div>";

            try {
                const resp = await fetch("/api/search_parts?category=" + encodeURIComponent(category) + "&q=" + encodeURIComponent(q));
                const data = await resp.json();
                if (data.results && data.results.length > 0) {
                    resDiv.innerHTML = "";
                    data.results.forEach((r, idx) => {
                        const item = document.createElement("div");
                        item.className = "mod-item" + (activeModules[category] === r.skin_id ? " selected" : "");
                        item.innerHTML = `<span>#${idx+1} ${r.title || r.caption.substring(0, 24)}...</span><span style='color: #10b981; font-size: 10px;'>★ ${r.quality_score}</span>`;
                        item.onclick = () => selectModule(category, r.skin_id, r.title || ('#' + (idx+1)));
                        resDiv.appendChild(item);
                    });
                } else {
                    resDiv.innerHTML = "<div style='color: var(--text-dim); padding: 4px;'>No modules found.</div>";
                }
            } catch (err) {
                resDiv.innerHTML = "<div style='color: #ef4444; padding: 4px;'>Error searching.</div>";
            }
        }

        function selectModule(category, skinId, label) {
            activeModules[category] = skinId;
            document.getElementById("sel-" + category).innerText = label;
            const resDiv = document.getElementById("results-" + category);
            resDiv.querySelectorAll(".mod-item").forEach(el => el.classList.remove("selected"));
            event.currentTarget.classList.add("selected");
        }

        async function assembleCharacter() {
            if (Object.keys(activeModules).length === 0) {
                alert("Please select at least one module (Hair, Face, Torso, or Legs) to assemble!");
                return;
            }

            const btn = document.querySelector(".btn-assemble");
            const originalText = btn.innerHTML;
            btn.innerHTML = "⏳ Assembling & Blending...";
            btn.style.opacity = "0.7";

            try {
                const resp = await fetch("/api/assemble", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ components: activeModules })
                });
                const res = await resp.json();
                if (res.status === "success") {
                    document.getElementById("lego-score-val").innerText = res.aesthetic_score + " / 1.0";
                    document.getElementById("lego-score-badge").innerText = res.aesthetic_tier;
                    document.getElementById("lego-score-details").innerText = "Applied: " + res.applied_modules.join(", ") + " | Seams healed: " + res.seam_issues;
                    loadSkinFromSource();
                } else {
                    alert("Assembly error: " + (res.error || "Unknown"));
                }
            } catch (err) {
                alert("Error calling assemble API: " + err);
            } finally {
                btn.innerHTML = originalText;
                btn.style.opacity = "1.0";
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
            model = get_skin_model(skin_path)
            payload = json.dumps({"mtime": mtime, "size": size, "model": model}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_cors_headers()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if not head_only:
                self.wfile.write(payload)

        elif self.path.startswith("/api/search_parts"):
            query_params = parse_qs(urlparse(self.path).query)
            category = query_params.get("category", ["hair"])[0]
            q = query_params.get("q", [""])[0]
            limit = int(query_params.get("limit", [6])[0])
            rag = get_rag()
            if not rag.is_available:
                payload = json.dumps({"results": []}).encode("utf-8")
            else:
                try:
                    results = rag.part_search(category, q, limit=limit, min_quality="low", render_previews=False)
                    payload = json.dumps({"results": results}).encode("utf-8")
                except Exception as e:
                    payload = json.dumps({"error": str(e), "results": []}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if not head_only:
                self.wfile.write(payload)

        elif self.path.startswith("/api/aesthetic_score"):
            if os.path.exists(skin_path):
                c = SkinCanvas()
                c.load_png(skin_path)
                score_info = compute_aesthetic_score(c)
                payload = json.dumps(score_info).encode("utf-8")
            else:
                payload = json.dumps({"score": 0.0, "tier": "unknown"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
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

    def do_POST(self):
        skin_path = get_skin_path()
        if self.path == "/api/assemble":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
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
                    auto_fix=True
                )
                
                target_canvas.export_png(skin_path)
                
                payload = json.dumps({
                    "status": "success",
                    "aesthetic_score": summary.get("aesthetic_score", 0.0),
                    "aesthetic_tier": summary.get("aesthetic_tier", "unknown"),
                    "seam_issues": summary.get("seam_issues_detected", 0),
                    "applied_modules": summary.get("applied_modules", [])
                }).encode("utf-8")
                self.send_response(200)
            except Exception as e:
                payload = json.dumps({"status": "error", "error": str(e)}).encode("utf-8")
                self.send_response(500)

            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
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
    httpd = ThreadingHTTPServer(server_address, SkinViewerServer)
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
