# SkinForge MCP 🎨🔨

**Autonomous Model Context Protocol (MCP) Server & Procedural Engine for Minecraft Skins.**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-1.0%20Compliant-purple.svg)](https://modelcontextprotocol.io/)
[![Tools](https://img.shields.io/badge/MCP%20Tools-45%20Native%20Tools-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-19%2F19%20Passed-success.svg)]()
[![WebGL](https://img.shields.io/badge/Viewer-Three.js%20WebGL-orange.svg)]()

SkinForge is an all-in-one professional toolkit designed for both **human skin artists** and **autonomous AI/LLM coding agents** (Antigravity, Gemini, Claude, GPT-4o, Cursor, Kilo) to create, sample, inspect, edit, audit, and visually verify Minecraft skins with true 3D dual-layer depth — **without requiring ad-hoc Python scripts**.

---

## 🌟 Key Features

### 1. 45 Native MCP Tools for AI Agents
- **Model Context Protocol (MCP) v3**: Enables LLMs to design, recolor, audit, and verify skins directly over stdio.
- **Full Skin Assembly & VLM Fine-Tuning (`skin_build`)**: Assembles complete 64×64 dual-layer skins in a single atomic call using a global palette and ASCII matrices (~1,200 tokens vs 20,000 for raw pixels), purpose-built for Vision-Language model fine-tuning.
- **Direct Reference Sampling (`skin_sample_reference`)**: Samples exact colors or extracts dominant palettes from concept art (`reference.jpeg`) and screenshots without writing Python scripts.
- **Multimodal Visual Feedback (`skin_render_3d`, `skin_render_2d`)**: Generates and returns base64 PNG turnaround images directly inside tool results for autonomous visual verification.

### 2. Real-Time 3D WebGL Viewer with Live Sync (`viewer.py`)
- **Interactive Three.js Player**: Orbit rotate (Left Click drag), pan (Right Click drag), zoom (Scroll), and preview walk/run animations.
- **Instant Reactive Updates (300ms)**: The moment an AI agent or developer calls an editing tool, the 3D model in the browser automatically updates its texture with zero lag, preserving camera angles and animation state.
- **Live Status Indicator**: Header dot pulses violet when updates arrive and returns to emerald green.

### 3. Dual-Layer 3D Depth Discipline (The 4 Golden Rules)
- **Rule 1 (Zero Holes)**: Strictly enforces 100% opacity on all 36 Base Layer parts (prevents the hollow black skull/torso bug).
- **Rule 2 (+0.35 Relief)**: Restricts Layer 2 exclusively to 3D relief accents (bangs, hood rims, cuffs, pockets, emblems).
- **Rule 3 (No Floating Profile Cardboard)**: `hat_front` rows 4–7 are kept transparent to prevent detached cardboard planes in 90° profile view.
- **Rule 4 (No Floating Crown Planks)**: `hat_top` is either solid or transparent, eliminating single detached hovering stripes.
- **Autonomous Self-Healing (`skin_auto_fix`)**: One-click autonomous healing that plugs holes and strips illegal floating planes.

### 4. Vectorized HSL / HSV Color Engine
- Pure-NumPy color manipulation running in **< 1 millisecond**.
- Rotate hue, boost saturation, or adjust brightness across specific parts or the entire skin with optional target color filtering (`skin_adjust_hsv`, `skin_shift_hue`).

### 5. 3D Seam Continuity Auditor & Edge Healer
- **3D Edge Connectivity Matrix**: Scans cube fold boundaries (head vertical ring, top crown fold, torso flanks, jacket) to detect texture tears or color misalignments.
- **Auto-Healing (`skin_align_seams`)**: Harmonizes and blends color jumps along adjacent 3D cube edges.

### 6. Pixel Typography & Cyber Symbols
- **3×5 Pixel Font Matrix (`skin_draw_text`)**: Writes crisp letters (A–Z), numbers (0–9), and punctuation (!, ?, -, :, .) on any face.
- **Emblem Library (`skin_draw_symbol`)**: Instantly stamps cyber emblems (`cyber_s` 6×8 crest, `heart`, `star`, `lightning`, `skull`, `cross`) without coordinate guesswork.

### 7. Full Outfits Macro & Model Converter
- **Coordinated Outfits (`skin_apply_outfit`)**: Applies full-body anatomical outfits (`techwear_hoodie`, `cargo_streetwear`, `casual_tshirt`) across Layer 1 and Layer 2 in a single call.
- **Geometry Converter (`skin_convert_model`)**: Seamlessly converts between classic Steve (4px arms) and Alex Slim (3px arms) with UV island resampling.

### 8. Multi-Target Synchronization & Auto-Previews (`skin_save`)
- Automatically saves to primary destination, synchronizes across canonical project paths, and regenerates 2D composite, 3D turnaround, and bottom-up previews in one atomic tool call.

### 9. Canvas History, Undo/Redo & Named Checkpoints
- Full undo/redo stack (`skin_undo`, `skin_redo`).
- Save milestone snapshots (`skin_checkpoint`) and instantly roll back (`skin_restore_checkpoint`).

---

## 📁 Repository Layout

```
SkinForge/
├── instructions.md            # System instructions & architectural guide for AI models / MCP clients
├── pyproject.toml             # Standard Python packaging metadata
├── README.md                  # Project overview & documentation
├── cli.py                     # Command-line interface
├── mcp_server.py              # Stdio MCP server entry point
├── viewer.py                  # Interactive 3D WebGL viewer server (port 8080)
├── skinforge/                 # Core library
│   ├── __init__.py            # Public exports
│   ├── mcp_server.py          # MCPServer implementation (44 tools, 4 resources, 2 prompts)
│   ├── canvas.py              # SkinCanvas, 72 UV parts, undo/redo, HSV adjustments
│   ├── seams.py               # 3D wrap-around seam auditing and edge blending
│   ├── typography.py          # 3x5 pixel font matrix & cyber symbols
│   ├── outfits.py             # Full anatomical outfit macros
│   ├── converter.py           # Steve 4px <-> Alex 3px slim model converter
│   ├── ascii_codec.py         # ASCII reverse-engineering & color normalization
│   ├── templates.py           # Solid humanoid template generator (0 holes)
│   ├── renderer.py            # Software 3D rasterizer, 2D composite, turntable GIF
│   ├── validator.py           # Quality auditor & layer rule enforcement
│   ├── palettes.py            # Color palettes & 5-step shading ramps
│   ├── presets.py             # Anatomical presets (eyes, drawstrings, cargo pockets)
│   └── sampler.py             # Reference art sampler & dominant palette extractor
├── tests/
│   └── test_mcp_server.py     # Comprehensive unit test suite (16 tests)
├── examples/
│   └── build_syntren.py       # Reference script building the Syntren skin
├── skins/
│   └── skin_syntren.png       # 64x64 RGBA canonical skin
├── previews/
│   ├── 3d_turnaround.png      # 4-angle 3D rasterized turnaround
│   ├── 2d_composite.png       # 2D front/back composite
│   └── turntable_360.gif      # 360-degree turntable animated GIF
└── static/
    └── skinview3d.bundle.js   # Offline Three.js WebGL skinview3d bundle
```

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repo-url>
cd SkinForge

# Install in editable mode
pip install -e .
```

Dependencies: `python>=3.9`, `numpy`, `pillow`, `mcp`.

---

### 2. Using with AI / LLMs (Model Context Protocol)

Add SkinForge to your IDE or agent config (`mcp_config.json` or `.mcp.json`):

```json
{
  "mcpServers": {
    "skinforge": {
      "command": "python3",
      "args": ["-m", "skinforge.mcp_server"],
      "cwd": "/path/to/SkinForge",
      "env": {
        "PYTHONPATH": "/path/to/SkinForge"
      }
    }
  }
}
```

Now any LLM (Claude, Gemini, Antigravity, GPT-4o) can autonomously design, edit, audit, and view skins!

---

### 3. Interactive 3D Web Viewer

```bash
# Launch viewer
python3 viewer.py
# Or via CLI
skinforge view
```
Open **`http://localhost:8080`** in your browser:
- **Left Click Drag**: Orbit rotate around character.
- **Right Click Drag**: Pan camera horizontally and vertically.
- **Scroll Wheel**: Zoom in/out.
- **Animations**: Toggle Idle, Walking, Running, and Auto-Spin.
- **Layer Toggles**: Individually toggle Head, Torso, Arms, Legs, and Outer 3D overlays.
- **Live Sync**: Edits made via MCP server appear instantly in 300ms!

---

### 4. CLI Tools

```bash
# Render 3D turnaround and 2D composite
skinforge render skins/skin_syntren.png --out3d previews/3d.png --out2d previews/2d.png

# Generate 360-degree animated turntable GIF
skinforge gif skins/skin_syntren.png --frames 16 --out previews/turntable.gif

# Run quality audit on a skin PNG
skinforge inspect skins/skin_syntren.png

# Mirror right arm to left arm
skinforge mirror skins/skin_syntren.png --from-limb right_arm --to-limb left_arm
```

---

### 5. Python API Example

```python
from skinforge import (
    SkinCanvas,
    SkinValidator,
    render_3d_turnaround,
    render_composite_2d,
    TECHWEAR_CYBERPUNK,
    apply_outfit,
    draw_symbol,
)

# 1. Initialize canvas and apply full techwear outfit
canvas = SkinCanvas()
apply_outfit(canvas, style="techwear_hoodie", accent_color="#af36f8")

# 2. Add custom cyber emblem to jacket back
draw_symbol(canvas, "jacket_back", "cyber_s", x=1, y=2, color="#af36f8")

# 3. Export to 64x64 PNG
canvas.export_png("my_skin.png")

# 4. Audit quality
validator = SkinValidator("my_skin.png")
valid, report = validator.validate()
print(report)

# 5. Render previews
render_3d_turnaround("my_skin.png", "turnaround.png")
render_composite_2d("my_skin.png", "composite.png")
```

---

## 🧪 Testing

SkinForge includes a comprehensive unit test suite covering session state, ASCII reverse-engineering, multimodal rendering, checkpoints, HSV adjustments, seam healing, typography, outfits, and converter:

```bash
python3 -m unittest tests/test_mcp_server.py
```

```
Ran 16 tests in 1.112s
OK
```

---

## 📜 License
MIT License. Free for personal and commercial use.
