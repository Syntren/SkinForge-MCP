/**
 * SkinForge Studio v1.3.0 — Client Application
 * Features:
 *  - Instant SSE (/api/events) push updates with automatic /api/status fallback
 *  - Animations: Idle, Walk, Run, Wave, Fly, Pause + Speed control + Turntable
 *  - Lighting presets: Studio, Daylight, Unlit Flat Pixel-Art (zero face shading)
 *  - Layer Toggle Matrix: Independent Base & Outer toggles for Head, Torso, Arms, Legs
 *  - Interactive 2D UV Map (64x64) with hover pixel inspector (UV part name, X/Y, HEX)
 *  - Real-time Aesthetic Engine v2 (6 metrics), color count & 4 Golden Rules status
 *  - Export Skin PNG & Screenshot 3D PNG
 */

let viewer = null;
let isSpinning = false;
let currentSkinModel = "default";
let currentAnimType = "idle";
let currentAnimSpeed = 1.0;
let currentLighting = "studio";
let lastMtime = 0;
let currentSkinDataUrl = null;
let uvImageData = null;
let currentUvMap = {};
let hoveredUvCoord = null;
let sseSource = null;
let fallbackInterval = null;
const activeModules = {};

// Default Minecraft 64x64 UV map fallback for 2D UV inspector
const DEFAULT_UV_MAP = {
    head_top: [8, 0, 16, 8], head_bottom: [16, 0, 24, 8], head_right: [0, 8, 8, 16],
    head_front: [8, 8, 16, 16], head_left: [16, 8, 24, 16], head_back: [24, 8, 32, 16],
    body_top: [20, 16, 28, 20], body_bottom: [28, 16, 36, 20], body_right: [16, 20, 20, 32],
    body_front: [20, 20, 28, 32], body_left: [28, 20, 32, 32], body_back: [32, 20, 40, 32],
    right_arm_top: [44, 16, 48, 20], right_arm_bottom: [48, 16, 52, 20], right_arm_right: [40, 20, 44, 32],
    right_arm_front: [44, 20, 48, 32], right_arm_left: [48, 20, 52, 32], right_arm_back: [52, 20, 56, 32],
    left_arm_top: [36, 48, 40, 52], left_arm_bottom: [40, 48, 44, 52], left_arm_right: [32, 52, 36, 64],
    left_arm_front: [36, 52, 40, 64], left_arm_left: [40, 52, 44, 64], left_arm_back: [44, 52, 48, 64],
    right_leg_top: [4, 16, 8, 20], right_leg_bottom: [8, 16, 12, 20], right_leg_right: [0, 20, 4, 32],
    right_leg_front: [4, 20, 8, 32], right_leg_left: [8, 20, 12, 32], right_leg_back: [12, 20, 16, 32],
    left_leg_top: [20, 48, 24, 52], left_leg_bottom: [24, 48, 28, 52], left_leg_right: [16, 52, 20, 64],
    left_leg_front: [20, 52, 24, 64], left_leg_left: [24, 52, 28, 64], left_leg_back: [28, 52, 32, 64],
    hat_top: [40, 0, 48, 8], hat_bottom: [48, 0, 56, 8], hat_right: [32, 8, 40, 16],
    hat_front: [40, 8, 48, 16], hat_left: [48, 8, 56, 16], hat_back: [56, 8, 64, 16],
    jacket_top: [20, 32, 28, 36], jacket_bottom: [28, 32, 36, 36], jacket_right: [16, 36, 20, 48],
    jacket_front: [20, 36, 28, 48], jacket_left: [28, 36, 32, 48], jacket_back: [32, 36, 40, 48],
    right_sleeve_top: [44, 32, 48, 36], right_sleeve_bottom: [48, 32, 52, 36], right_sleeve_right: [40, 36, 44, 48],
    right_sleeve_front: [44, 36, 48, 48], right_sleeve_left: [48, 36, 52, 48], right_sleeve_back: [52, 36, 56, 48],
    left_sleeve_top: [52, 48, 56, 52], left_sleeve_bottom: [56, 48, 60, 52], left_sleeve_right: [48, 52, 52, 64],
    left_sleeve_front: [52, 52, 56, 64], left_sleeve_left: [56, 52, 60, 64], left_sleeve_back: [60, 52, 64, 64],
    right_pants_top: [4, 32, 8, 36], right_pants_bottom: [8, 32, 12, 36], right_pants_right: [0, 36, 4, 48],
    right_pants_front: [4, 36, 8, 48], right_pants_left: [8, 36, 12, 48], right_pants_back: [12, 36, 16, 48],
    left_pants_top: [4, 48, 8, 52], left_pants_bottom: [8, 48, 12, 52], left_pants_right: [0, 52, 4, 64],
    left_pants_front: [4, 52, 8, 64], left_pants_left: [8, 52, 12, 64], left_pants_back: [12, 52, 16, 64]
};
currentUvMap = DEFAULT_UV_MAP;

function initViewer() {
    const container = document.getElementById("canvas-container");
    const canvas = document.getElementById("skin_container");
    const w = container.clientWidth || (window.innerWidth - 390);
    const h = container.clientHeight || window.innerHeight;

    viewer = new skinview3d.SkinViewer({
        canvas: canvas,
        width: w,
        height: h,
        preserveDrawingBuffer: true
    });

    viewer.fov = 58;
    viewer.zoom = 0.88;
    viewer.autoRotate = false;
    viewer.autoRotateSpeed = 1.2;

    if (viewer.controls) {
        viewer.controls.enablePan = true;
        viewer.controls.panSpeed = 1.2;
        viewer.controls.screenSpacePanning = true;
    }

    canvas.addEventListener("contextmenu", (e) => e.preventDefault());

    window.addEventListener("resize", () => {
        const nw = container.clientWidth || (window.innerWidth - 390);
        const nh = container.clientHeight || window.innerHeight;
        viewer.width = nw;
        viewer.height = nh;
    });

    setCameraView("front_3d");
    setLighting("studio");
    setAnimation("idle");
    initUVMapInspector();
    connectSSEStream();
}

/* =========================================================================
 * 1. SERVER-SENT EVENTS (SSE) STREAM + FALLBACK POLLING
 * ========================================================================= */
function connectSSEStream() {
    if (typeof EventSource !== "undefined") {
        sseSource = new EventSource("/api/events");

        sseSource.addEventListener("skin_update", (event) => {
            try {
                const payload = JSON.parse(event.data);
                applyTelemetryUpdate(payload, "SSE Live");
            } catch (err) {
                console.error("Failed to parse SSE skin_update:", err);
            }
        });

        sseSource.onopen = () => {
            const textEl = document.getElementById("live-text");
            const dotEl = document.getElementById("live-dot");
            if (textEl) textEl.innerText = "SSE Live Stream";
            if (dotEl) dotEl.style.background = "#10b981";
            if (fallbackInterval) {
                clearInterval(fallbackInterval);
                fallbackInterval = null;
            }
        };

        sseSource.onerror = () => {
            const textEl = document.getElementById("live-text");
            if (textEl) textEl.innerText = "Fallback Polling";
            if (!fallbackInterval) {
                fallbackInterval = setInterval(pollFallbackStatus, 1000);
            }
        };
    } else {
        fallbackInterval = setInterval(pollFallbackStatus, 1000);
    }
    // Also fetch initial status once in case SSE is buffering
    pollFallbackStatus();
}

async function pollFallbackStatus() {
    try {
        const resp = await fetch("/api/status?t=" + Date.now());
        if (resp.ok) {
            const payload = await resp.json();
            if (payload.mtime !== lastMtime || !currentSkinDataUrl) {
                applyTelemetryUpdate(payload, "Status Sync");
            }
        }
    } catch (err) {
        // Ignore transient errors
    }
}

function applyTelemetryUpdate(payload, sourceLabel) {
    if (!payload) return;
    if (payload.mtime) lastMtime = payload.mtime;
    if (payload.uv_map) currentUvMap = payload.uv_map;

    const rawModel = (payload.raw_model || payload.model || "default").toLowerCase();
    currentSkinModel = (rawModel === "slim" || rawModel === "alex") ? "slim" : "default";

    const modelBadge = document.getElementById("hud-model-badge");
    if (modelBadge) {
        modelBadge.innerText = currentSkinModel === "slim" ? "MODEL: SLIM 3PX" : "MODEL: CLASSIC 4PX";
    }

    if (payload.skin_b64) {
        currentSkinDataUrl = payload.skin_b64;
        viewer.loadSkin(payload.skin_b64, {
            model: currentSkinModel,
            makeVisible: true
        }).then(() => {
            applyLayerMatrix();
            setLighting(currentLighting);
            updateUVPreviewImage(payload.skin_b64);
        });
    } else {
        loadSkinFromBase64Endpoint();
    }

    if (payload.audit) {
        renderAuditTelemetry(payload.audit);
    }

    const dot = document.getElementById("live-dot");
    if (dot) {
        dot.style.background = "#c064ff";
        setTimeout(() => { dot.style.background = "#10b981"; }, 600);
    }

    const lastUp = document.getElementById("last-update");
    if (lastUp) {
        lastUp.innerText = `${sourceLabel} updated: ${new Date().toLocaleTimeString()} (${currentSkinModel})`;
    }
}

function loadSkinFromBase64Endpoint() {
    fetch("/skin-base64?t=" + Date.now())
        .then(r => r.json())
        .then(data => {
            if (data && data.data) {
                currentSkinDataUrl = data.data;
                viewer.loadSkin(data.data, { model: currentSkinModel, makeVisible: true }).then(() => {
                    applyLayerMatrix();
                    setLighting(currentLighting);
                    updateUVPreviewImage(data.data);
                });
            }
        })
        .catch(() => {});
}

/* =========================================================================
 * 2. ANIMATIONS (Idle, Walk, Run, Wave, Fly, Pause) & SPEED
 * ========================================================================= */
function setAnimation(type) {
    currentAnimType = type;
    document.querySelectorAll(".anim-btn").forEach(b => b.classList.remove("active"));
    const activeBtn = document.getElementById("btn-anim-" + type);
    if (activeBtn) activeBtn.classList.add("active");

    if (!viewer) return;

    if (type === "pause") {
        if (viewer.animation) {
            viewer.animation.paused = true;
        }
        return;
    }

    if (viewer.animation) {
        viewer.animation.paused = true;
        viewer.animation = null;
    }
    resetPlayerPose();

    if (type === "idle") {
        if (skinview3d.IdleAnimation) {
            viewer.animation = new skinview3d.IdleAnimation();
        }
    } else if (type === "walk") {
        viewer.animation = new skinview3d.WalkingAnimation();
    } else if (type === "run") {
        viewer.animation = new skinview3d.RunningAnimation();
    } else if (type === "fly") {
        if (skinview3d.FlyingAnimation) {
            viewer.animation = new skinview3d.FlyingAnimation();
        }
    } else if (type === "wave") {
        if (skinview3d.FunctionAnimation) {
            viewer.animation = new skinview3d.FunctionAnimation((player, progress) => {
                const t = progress * 6.0;
                player.skin.rightArm.rotation.x = -2.6;
                player.skin.rightArm.rotation.z = 0.35 + Math.sin(t) * 0.38;
                player.skin.leftArm.rotation.z = -0.06 - Math.cos(progress * 2.0) * 0.04;
                player.skin.head.rotation.z = Math.sin(t * 0.5) * 0.06;
                player.skin.head.rotation.y = Math.cos(t * 0.5) * 0.08;
            });
        }
    }

    if (viewer.animation) {
        viewer.animation.paused = false;
        viewer.animation.speed = currentAnimSpeed;
    }
}

function resetPlayerPose() {
    if (!viewer || !viewer.playerObject || !viewer.playerObject.skin) return;
    const s = viewer.playerObject.skin;
    ["head", "body", "rightArm", "leftArm", "rightLeg", "leftLeg"].forEach(part => {
        if (s[part] && s[part].rotation) {
            s[part].rotation.set(0, 0, 0);
        }
    });
}

function updateAnimSpeed(val) {
    currentAnimSpeed = parseFloat(val) || 1.0;
    const label = document.getElementById("anim-speed-val");
    if (label) label.innerText = currentAnimSpeed.toFixed(1) + "×";
    if (viewer && viewer.animation) {
        viewer.animation.speed = currentAnimSpeed;
    }
}

function toggleSpin() {
    isSpinning = !isSpinning;
    if (viewer) viewer.autoRotate = isSpinning;
    const btn = document.getElementById("btn-spin");
    if (btn) {
        isSpinning ? btn.classList.add("active") : btn.classList.remove("active");
    }
}

/* =========================================================================
 * 3. LIGHTING PRESETS (Studio, Daylight, Unlit Flat Pixel-Art)
 * ========================================================================= */
function setLighting(preset) {
    currentLighting = preset;
    document.querySelectorAll(".light-btn").forEach(b => b.classList.remove("active"));
    const btn = document.getElementById("btn-light-" + preset);
    if (btn) btn.classList.add("active");

    if (!viewer) return;

    if (preset === "studio") {
        viewer.globalLight.color.setHex(0xffffff);
        viewer.globalLight.intensity = 2.35;
        viewer.cameraLight.color.setHex(0xf5edff);
        viewer.cameraLight.intensity = 1.15;
    } else if (preset === "daylight") {
        viewer.globalLight.color.setHex(0xfffbeb);
        viewer.globalLight.intensity = 2.85;
        viewer.cameraLight.color.setHex(0xffffff);
        viewer.cameraLight.intensity = 0.85;
    } else if (preset === "unlit") {
        // Pure flat unshaded pixel-art mode: zero directional face shading
        viewer.globalLight.color.setHex(0xffffff);
        viewer.globalLight.intensity = Math.PI;
        viewer.cameraLight.color.setHex(0xffffff);
        viewer.cameraLight.intensity = 0.0;
    }
}

/* =========================================================================
 * 4. LAYER TOGGLE MATRIX (Head, Torso, Arms, Legs x Base / Outer)
 * ========================================================================= */
function applyLayerMatrix() {
    if (!viewer || !viewer.playerObject || !viewer.playerObject.skin) return;
    const skin = viewer.playerObject.skin;

    const headBase = document.getElementById("mat-head-base").checked;
    const headOuter = document.getElementById("mat-head-outer").checked;
    const torsoBase = document.getElementById("mat-torso-base").checked;
    const torsoOuter = document.getElementById("mat-torso-outer").checked;
    const armsBase = document.getElementById("mat-arms-base").checked;
    const armsOuter = document.getElementById("mat-arms-outer").checked;
    const legsBase = document.getElementById("mat-legs-base").checked;
    const legsOuter = document.getElementById("mat-legs-outer").checked;

    const setPartLayers = (partObj, baseVis, outerVis) => {
        if (!partObj) return;
        if (partObj.innerLayer) partObj.innerLayer.visible = baseVis;
        if (partObj.outerLayer) partObj.outerLayer.visible = outerVis;
    };

    setPartLayers(skin.head, headBase, headOuter);
    setPartLayers(skin.body, torsoBase, torsoOuter);
    setPartLayers(skin.rightArm, armsBase, armsOuter);
    setPartLayers(skin.leftArm, armsBase, armsOuter);
    setPartLayers(skin.rightLeg, legsBase, legsOuter);
    setPartLayers(skin.leftLeg, legsBase, legsOuter);
}

function setAllLayers(baseState, outerState) {
    ["head", "torso", "arms", "legs"].forEach(region => {
        document.getElementById(`mat-${region}-base`).checked = baseState;
        document.getElementById(`mat-${region}-outer`).checked = outerState;
    });
    applyLayerMatrix();
}

/* =========================================================================
 * 5. CAMERA ANGLES
 * ========================================================================= */
function setCameraView(view) {
    if (!viewer) return;
    if (isSpinning) {
        isSpinning = false;
        viewer.autoRotate = false;
        const spinBtn = document.getElementById("btn-spin");
        if (spinBtn) spinBtn.classList.remove("active");
    }
    if (viewer.playerWrapper) {
        viewer.playerWrapper.rotation.set(0, 0, 0);
    }
    if (viewer.controls) {
        viewer.controls.target.set(0, 0, 0);
    }
    if (view === "front") {
        viewer.camera.position.set(0, 0, 60);
    } else if (view === "front_3d") {
        viewer.camera.position.set(-25, 12, 50);
    } else if (view === "back") {
        viewer.camera.position.set(0, 0, -60);
    } else if (view === "left") {
        viewer.camera.position.set(60, 0, 0);
    } else if (view === "right") {
        viewer.camera.position.set(-60, 0, 0);
    }
    viewer.camera.lookAt(0, 0, 0);
    if (viewer.controls && typeof viewer.controls.update === "function") {
        viewer.controls.update();
    }
}

/* =========================================================================
 * 6. INTERACTIVE 2D UV MAP PREVIEW (64x64) & HOVER INSPECTOR
 * ========================================================================= */
function initUVMapInspector() {
    const wrapper = document.getElementById("uv-canvas-wrapper");
    if (!wrapper) return;

    wrapper.addEventListener("mousemove", (e) => {
        const rect = wrapper.getBoundingClientRect();
        const x = Math.max(0, Math.min(63, Math.floor(((e.clientX - rect.left) / rect.width) * 64)));
        const y = Math.max(0, Math.min(63, Math.floor(((e.clientY - rect.top) / rect.height) * 64)));
        hoveredUvCoord = { x, y };
        inspectUVPixel(x, y);
        drawUVOverlay();
    });

    wrapper.addEventListener("mouseleave", () => {
        hoveredUvCoord = null;
        drawUVOverlay();
    });
}

function updateUVPreviewImage(dataUrl) {
    const canvas = document.getElementById("uv-preview-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const img = new Image();
    img.onload = () => {
        ctx.clearRect(0, 0, 64, 64);
        ctx.drawImage(img, 0, 0, 64, 64);
        uvImageData = ctx.getImageData(0, 0, 64, 64);
        drawUVOverlay();
    };
    img.src = dataUrl;
}

function findUVZoneAt(x, y) {
    const map = currentUvMap || DEFAULT_UV_MAP;
    for (const [partName, box] of Object.entries(map)) {
        const [u0, v0, u1, v1] = box;
        if (x >= u0 && x < u1 && y >= v0 && y < v1) {
            const isOuter = partName.startsWith("hat_") || partName.startsWith("jacket_") || partName.includes("sleeve") || partName.includes("pants");
            return {
                name: partName,
                layer: isOuter ? "Outer L2" : "Base L1",
                box: box,
                lx: x - u0,
                ly: y - v0
            };
        }
    }
    return null;
}

function inspectUVPixel(x, y) {
    const partEl = document.getElementById("uv-part-name");
    const coordHexEl = document.getElementById("uv-coord-hex");
    const swatchEl = document.getElementById("uv-swatch");

    const zone = findUVZoneAt(x, y);
    let hexStr = "#00000000";
    let rgbaCss = "transparent";

    if (uvImageData) {
        const idx = (y * 64 + x) * 4;
        const r = uvImageData.data[idx];
        const g = uvImageData.data[idx + 1];
        const b = uvImageData.data[idx + 2];
        const a = uvImageData.data[idx + 3];
        const toHex = (n) => n.toString(16).padStart(2, "0").toUpperCase();
        if (a === 0) {
            hexStr = "TRANSPARENT (α=0)";
            rgbaCss = "transparent";
        } else if (a === 255) {
            hexStr = `#${toHex(r)}${toHex(g)}${toHex(b)}`;
            rgbaCss = `rgb(${r},${g},${b})`;
        } else {
            hexStr = `#${toHex(r)}${toHex(g)}${toHex(b)}${toHex(a)}`;
            rgbaCss = `rgba(${r},${g},${b},${(a / 255).toFixed(2)})`;
        }
    }

    if (swatchEl) swatchEl.style.background = rgbaCss;
    if (partEl) {
        partEl.innerText = zone ? `${zone.name} (${zone.layer})` : "Unused UV Region";
    }
    if (coordHexEl) {
        coordHexEl.innerText = `X: ${x}, Y: ${y} | ${hexStr}`;
    }
}

function drawUVOverlay() {
    const overlay = document.getElementById("uv-overlay-canvas");
    if (!overlay) return;
    const ctx = overlay.getContext("2d");
    const scale = 4; // 64 * 4 = 256
    ctx.clearRect(0, 0, 256, 256);

    const showZones = document.getElementById("tog-uv-zones")?.checked;
    const map = currentUvMap || DEFAULT_UV_MAP;

    if (showZones) {
        ctx.lineWidth = 1;
        for (const [partName, box] of Object.entries(map)) {
            const [u0, v0, u1, v1] = box;
            const isOuter = partName.startsWith("hat_") || partName.startsWith("jacket_") || partName.includes("sleeve") || partName.includes("pants");
            ctx.strokeStyle = isOuter ? "rgba(192, 100, 255, 0.45)" : "rgba(56, 189, 248, 0.40)";
            ctx.strokeRect(u0 * scale + 0.5, v0 * scale + 0.5, (u1 - u0) * scale - 1, (v1 - v0) * scale - 1);
        }
    }

    if (hoveredUvCoord) {
        const zone = findUVZoneAt(hoveredUvCoord.x, hoveredUvCoord.y);
        if (zone) {
            const [u0, v0, u1, v1] = zone.box;
            ctx.strokeStyle = "#f59e0b";
            ctx.lineWidth = 1.5;
            ctx.strokeRect(u0 * scale, v0 * scale, (u1 - u0) * scale, (v1 - v0) * scale);
        }
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.5;
        ctx.strokeRect(hoveredUvCoord.x * scale, hoveredUvCoord.y * scale, scale, scale);
    }
}

/* =========================================================================
 * 7. REAL-TIME AESTHETIC SCORE (6 METRICS) & 4 GOLDEN RULES RENDERING
 * ========================================================================= */
function renderAuditTelemetry(audit) {
    if (!audit) return;

    const scoreVal = document.getElementById("audit-score-val");
    if (scoreVal && audit.score !== undefined) {
        scoreVal.innerHTML = `${Number(audit.score).toFixed(2)} <small>/ 1.00</small>`;
    }

    const tierBadge = document.getElementById("audit-tier-badge");
    if (tierBadge && audit.tier) {
        tierBadge.innerText = String(audit.tier).toUpperCase();
        tierBadge.style.background =
            audit.tier === "top_tier" ? "#10b981" :
            audit.tier === "high" ? "#38bdf8" :
            audit.tier === "medium" ? "#f59e0b" : "#f43f5e";
    }

    const colorsCount = audit.unique_colors ?? 0;
    const l2Ratio = ((audit.layer2_ratio ?? 0) * 100).toFixed(1);

    const colorsEl = document.getElementById("audit-colors-count");
    if (colorsEl) colorsEl.innerText = `Colors: ${colorsCount}`;

    const hudColors = document.getElementById("hud-colors-badge");
    if (hudColors) hudColors.innerText = `🎨 ${colorsCount} COLORS`;

    const l2El = document.getElementById("audit-l2-density");
    if (l2El) l2El.innerText = `L2 Relief: ${l2Ratio}%`;

    const m = audit.metrics || {};
    const updateMetricBar = (key, val) => {
        const pct = Math.max(0, Math.min(100, Math.round((val ?? 0) * 100)));
        const valEl = document.getElementById("m-val-" + key);
        const barEl = document.getElementById("m-bar-" + key);
        if (valEl) valEl.innerText = pct + "%";
        if (barEl) barEl.style.width = pct + "%";
    };

    updateMetricBar("relief", m.relief_3d);
    updateMetricBar("palette", m.palette_harmony);
    updateMetricBar("shading", m.shading_depth);
    updateMetricBar("coherence", m.spatial_coherence);
    updateMetricBar("hue", m.hue_shifting);
    updateMetricBar("seams", m.seam_continuity);

    const gr = audit.golden_rules;
    if (gr) {
        const setRuleStatus = (idx, ruleObj, detailPass, detailFail) => {
            const badge = document.getElementById("rule-badge-" + idx);
            if (!badge || !ruleObj) return;
            const passed = Boolean(ruleObj.passed);
            badge.className = "rule-badge " + (passed ? "pass" : "fail");
            badge.innerText = passed ? detailPass : detailFail;
        };

        setRuleStatus(
            1,
            gr.rule1_zero_holes,
            "PASS (0 holes)",
            `FAIL (${gr.rule1_zero_holes?.holes || 0} holes)`
        );
        setRuleStatus(
            2,
            gr.rule2_relief_depth,
            `PASS (${gr.rule2_relief_depth?.layer2_pct ?? l2Ratio}%)`,
            `FAIL (${gr.rule2_relief_depth?.layer2_pct ?? l2Ratio}%)`
        );
        setRuleStatus(
            3,
            gr.rule3_hat_front,
            "PASS (Clear)",
            `FAIL (${gr.rule3_hat_front?.violating_pixels || 0} px)`
        );
        setRuleStatus(
            4,
            gr.rule4_hat_top,
            "PASS",
            `FAIL (${gr.rule4_hat_top?.hat_top_pixels || 0} px)`
        );
    }
}

async function triggerAutoFix() {
    try {
        const resp = await fetch("/api/auto_fix", { method: "POST" });
        const data = await resp.json();
        if (data && data.telemetry) {
            applyTelemetryUpdate(data.telemetry, "Auto-Fix");
        }
    } catch (err) {
        console.error("Auto-fix failed:", err);
    }
}

/* =========================================================================
 * 8. EXPORT SKIN PNG & SCREENSHOT 3D PNG
 * ========================================================================= */
function exportSkinPNG() {
    const a = document.createElement("a");
    a.href = currentSkinDataUrl || ("/skin.png?t=" + Date.now());
    a.download = `skinforge_${currentSkinModel}_64x64.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function screenshot3DPNG() {
    if (!viewer) return;
    if (typeof viewer.render === "function") {
        viewer.render();
    }
    const canvas = document.getElementById("skin_container");
    if (!canvas) return;
    const dataUrl = canvas.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = `skinforge_3d_render_${Date.now()}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

/* =========================================================================
 * 9. STUDIO TABS & LEGO CONSTRUCTOR
 * ========================================================================= */
function switchTab(tab) {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    if (tab === "studio") {
        document.getElementById("tab-btn-studio").classList.add("active");
        document.getElementById("tab-studio-content").style.display = "flex";
        document.getElementById("tab-lego-content").style.display = "none";
    } else {
        document.getElementById("tab-btn-lego").classList.add("active");
        document.getElementById("tab-studio-content").style.display = "none";
        document.getElementById("tab-lego-content").style.display = "flex";
    }
}

async function searchModule(category) {
    const input = document.getElementById("input-" + category);
    const q = input.value.trim();
    if (!q) return;

    const resDiv = document.getElementById("results-" + category);
    resDiv.innerHTML = "<div style='color: var(--text-dim); padding: 4px; font-size: 11px;'>Searching RAG database...</div>";

    try {
        const resp = await fetch(`/api/search_parts?category=${encodeURIComponent(category)}&q=${encodeURIComponent(q)}`);
        const data = await resp.json();
        if (data.status === "db_not_initialized") {
            resDiv.innerHTML = `<div style='color: var(--amber); padding: 4px; font-size: 11px;'>${data.message}</div>`;
            return;
        }
        if (data.results && data.results.length > 0) {
            resDiv.innerHTML = "";
            data.results.forEach((r, idx) => {
                const item = document.createElement("div");
                item.className = "mod-item" + (activeModules[category] === r.skin_id ? " selected" : "");
                item.innerHTML = `<span>#${idx + 1} ${r.title || (r.caption || "").substring(0, 24)}</span><span style='color: #10b981; font-size: 10px;'>★ ${r.quality_score}</span>`;
                item.onclick = (ev) => selectModule(ev, category, r.skin_id, r.title || ("#" + (idx + 1)));
                resDiv.appendChild(item);
            });
        } else {
            resDiv.innerHTML = "<div style='color: var(--text-dim); padding: 4px; font-size: 11px;'>No matching modules found.</div>";
        }
    } catch (err) {
        resDiv.innerHTML = "<div style='color: var(--rose); padding: 4px; font-size: 11px;'>Search error.</div>";
    }
}

function selectModule(ev, category, skinId, label) {
    activeModules[category] = skinId;
    document.getElementById("sel-" + category).innerText = label;
    const resDiv = document.getElementById("results-" + category);
    resDiv.querySelectorAll(".mod-item").forEach(el => el.classList.remove("selected"));
    if (ev && ev.currentTarget) {
        ev.currentTarget.classList.add("selected");
    }
}

async function assembleCharacter() {
    if (Object.keys(activeModules).length === 0) {
        alert("Select at least one anatomical module (Hair, Face, Torso, or Legs) first.");
        return;
    }

    const btn = document.querySelector(".btn-assemble");
    const origText = btn.innerHTML;
    btn.innerHTML = "⏳ Assembling & Blending...";
    btn.disabled = true;

    try {
        const resp = await fetch("/api/assemble", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ components: activeModules })
        });
        const res = await resp.json();
        if (res.status === "success") {
            if (res.telemetry) {
                applyTelemetryUpdate(res.telemetry, "Lego Assemble");
            }
            switchTab("studio");
        } else {
            alert("Assembly notice: " + (res.error || res.message || "Unknown error"));
        }
    } catch (err) {
        alert("Error calling assemble API: " + err);
    } finally {
        btn.innerHTML = origText;
        btn.disabled = false;
    }
}

window.addEventListener("DOMContentLoaded", initViewer);
