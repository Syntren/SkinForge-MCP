# SkinForge MCP 🎨🔨

**Autonomous Model Context Protocol (MCP) Server & Procedural Engine for Minecraft Skins.**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/Syntren/SkinForge-MCP/releases)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-1.0%20Compliant-purple.svg)](https://modelcontextprotocol.io/)
[![Tools](https://img.shields.io/badge/MCP%20Tools-52%20Native%20Tools-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-30%2F30%20Passed-success.svg)]()
[![WebGL](https://img.shields.io/badge/Viewer-Three.js%20WebGL-orange.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

SkinForge is an all-in-one professional toolkit designed for both **human skin artists** and **autonomous AI/LLM coding agents** (Antigravity, Gemini, Claude, GPT-4o, Cursor, Kilo) to create, sample, inspect, edit, audit, search, and visually verify Minecraft skins with true 3D dual-layer depth — **without requiring ad-hoc Python scripts**.

---

## 🌟 Key Features

### 1. 52 Native MCP Tools for AI Agents
- **Model Context Protocol (MCP) Compliant**: Enables LLMs to design, recolor, audit, assemble, and verify skins directly over stdio or SSE.
- **Full Skin Assembly & VLM Fine-Tuning (`skin_build`)**: Assembles complete 64×64 dual-layer skins in a single atomic call using a global palette and ASCII matrices (~1,200 tokens vs 20,000 for raw pixels), purpose-built for Vision-Language model fine-tuning.
- **Direct Reference Sampling (`skin_sample_reference`)**: Samples exact colors or extracts dominant palettes from concept art and screenshots without writing Python scripts.
- **Multimodal Visual Feedback (`skin_render_3d`, `skin_render_2d`)**: Generates and returns base64 PNG turnaround images directly inside tool results for autonomous visual verification.

### 2. Modular "Lego Constructor" Engine (`skin_assemble`, `skin_part_search`)
- **Component-Level Search (`skin_part_search`)**: Search for individual anatomical components across 900,000+ skins (`hair`, `face`, `torso`, `arms`, `legs`, `outfit`).
- **Isolated Component 3D Mannequins**: Renders the queried module on a neutral dark mannequin so multimodal models can evaluate hairstyles or jacket folds in isolation.
- **Automated Seam Harmonization (`skin_assemble`)**: Merges modules from different skins into a cohesive character while automatically blending neck, shoulder, and waist seams and healing 3D geometry rules.

### 3. Aesthetic Quality Curation & Denoising Filter
- **Algorithmic Craftsmanship Scorer (`compute_aesthetic_score`)**: Scores skins (0.0 to 1.0) and categorizes them into quality tiers (`low`, `medium`, `high`, `top_tier`).
  - Evaluates Layer 2 relief density (optimal 15–40% 3D accents).
  - Evaluates color entropy and shading depth (detects rich ramps vs flat flood fills).
  - Evaluates surface texture variance across major anatomical facets.
- **Search Quality Filtering (`skin_search(..., min_quality="medium")`)**: Automatically discards low-effort flat fills, messy noise artifacts, and hollow textures from search results.

### 4. Visual Concept & Image Search (`skin_search_by_image`)
- **Spatial-Color Pyramid Matching**: Converts reference images into a 299-dimensional perceptual pyramid in LAB color space.
- **Perceptual Style Similarity**: Matches concept art, anime references, or photo textures directly against indexed skins based on global palette, spatial color layout, and contrast.

### 5. Built-in 900,000+ Skin RAG Search Engine
- **Instant Sub-Millisecond Search (`skin_search`)**: Queries across 900k+ human-crafted Minecraft skins using SQLite FTS5 (BM25 ranking) in <1ms.
- **Visual Reference Generation**: Automatically renders 3D turnaround and 2D composite previews for retrieved skins so multimodal LLMs can inspect the design visually.
- **Reference Extraction (`skin_get_reference`)**: Retrieves full color palettes and ASCII matrices, or loads candidate skins directly into the active editing session.
- **Intelligent Remixing (`skin_remix`)**: Seamlessly transfers outer layers (jackets, scarves, hoods) and accessories from one reference skin onto another with automatic geometry healing.

### 6. Real-Time 3D WebGL Viewer with Live Sync (`viewer.py`)
- **Interactive Three.js Player**: Orbit rotate (Left Click drag), pan (Right Click drag), zoom (Scroll), and preview walk/run animations.
- **Instant Reactive Updates (300ms)**: The moment an AI agent or developer calls an editing tool, the 3D model in the browser automatically updates its texture with zero lag, preserving camera angles and animation state.
- **Live Status Indicator**: Header dot pulses violet when updates arrive and returns to emerald green.

### 7. Dual-Layer 3D Depth Discipline (The 4 Golden Rules)
- **Rule 1 (Zero Holes)**: Strictly enforces 100% opacity on all 36 Base Layer parts (prevents the hollow black skull/torso bug).
- **Rule 2 (+0.35 Relief)**: Restricts Layer 2 exclusively to 3D relief accents (bangs, hood rims, cuffs, pockets, emblems).
- **Rule 3 (No Floating Profile Cardboard)**: `hat_front` rows 4–7 are kept transparent to prevent detached cardboard planes in 90° profile view.
- **Rule 4 (No Floating Crown Planks)**: `hat_top` is either solid or transparent, eliminating single detached hovering stripes.
- **Autonomous Self-Healing (`skin_auto_fix`)**: One-click autonomous healing that plugs holes and strips illegal floating planes.

### 8. Vectorized HSL / HSV Color Engine
- Pure-NumPy color manipulation running in **< 1 millisecond**.
- Rotate hue, boost saturation, or adjust brightness across specific parts or the entire skin with optional target color filtering (`skin_adjust_hsv`, `skin_shift_hue`).

### 9. 3D Seam Continuity Auditor & Edge Healer
- **3D Edge Connectivity Matrix**: Scans cube fold boundaries (head vertical ring, top crown fold, torso flanks, jacket) to detect texture tears or color misalignments.
- **Auto-Healing (`skin_align_seams`)**: Harmonizes and blends color jumps along adjacent 3D cube edges.

### 10. Pixel Typography & Cyber Symbols
- **3×5 Pixel Font Matrix (`skin_draw_text`)**: Writes crisp letters (A–Z), numbers (0–9), and punctuation (!, ?, -, :, .) on any face.
- **Emblem Library (`skin_draw_symbol`)**: Instantly stamps cyber emblems (`cyber_s` 6×8 crest, `heart`, `star`, `lightning`, `skull`, `cross`) without coordinate guesswork.

### 11. Full Outfits Macro & Model Converter
- **Coordinated Outfits (`skin_apply_outfit`)**: Applies full-body anatomical outfits (`techwear_hoodie`, `cargo_streetwear`, `casual_tshirt`) across Layer 1 and Layer 2 in a single call.
- **Geometry Converter (`skin_convert_model`)**: Seamlessly converts between classic Steve (4px arms) and Alex Slim (3px arms) with UV island resampling.

### 12. Multi-Target Synchronization & Auto-Previews (`skin_save`)
- Automatically saves to primary destination, synchronizes across canonical project paths, and regenerates 2D composite, 3D turnaround, and bottom-up previews in one atomic tool call.

### 13. Canvas History, Undo/Redo & Named Checkpoints
- Full undo/redo stack (`skin_undo`, `skin_redo`).
- Save milestone snapshots (`skin_checkpoint`) and instantly roll back (`skin_restore_checkpoint`).

---

## 📁 Repository Layout

```
SkinForge/
├── instructions.md            # System instructions & architectural guide for AI models / MCP clients
├── pyproject.toml             # Standard Python packaging metadata (v1.0.0)
├── README.md                  # Project overview & documentation
├── cli.py                     # Command-line interface
├── mcp_server.py              # Stdio MCP server entry point
├── viewer.py                  # Interactive 3D WebGL viewer server (port 8080)
├── skinforge/                 # Core library
│   ├── __init__.py            # Public exports (v1.0.0)
│   ├── mcp_server.py          # MCPServer implementation (52 tools, 4 resources, 2 prompts)
│   ├── canvas.py              # SkinCanvas, 72 UV parts, undo/redo, HSV adjustments
│   ├── modular.py             # Lego Constructor: assembly & isolated module mannequin preview
│   ├── vision.py              # Spatial-color pyramid visual concept & image search
│   ├── validator.py           # Quality auditor & aesthetic craftsmanship scorer
│   ├── rag.py                 # 900k+ skin FTS5 search engine, part search & remix
│   ├── seams.py               # 3D wrap-around seam auditing and edge blending
│   ├── typography.py          # 3x5 pixel font matrix & cyber symbols
│   ├── outfits.py             # Full anatomical outfit macros
│   ├── converter.py           # Steve 4px <-> Alex 3px slim model converter
│   ├── ascii_codec.py         # ASCII reverse-engineering & vectorized color normalization
│   ├── templates.py           # Solid humanoid template generator (0 holes)
│   ├── renderer.py            # Software 3D rasterizer, 2D composite, turntable GIF
│   ├── palettes.py            # Color palettes & 5-step shading ramps
│   ├── presets.py             # Anatomical presets (eyes, drawstrings, cargo pockets)
│   └── sampler.py             # Reference art sampler & dominant palette extractor
├── tests/
│   ├── test_mcp_server.py     # Base MCP unit tests
│   ├── test_rag.py            # RAG engine and FTS5 search tests
│   └── test_v1.py             # v1.0.0 Lego constructor, aesthetic scoring & vision tests
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
git clone https://github.com/Syntren/SkinForge-MCP.git
cd SkinForge-MCP

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
      "cwd": "/path/to/SkinForge-MCP",
      "env": {
        "PYTHONPATH": "/path/to/SkinForge-MCP"
      }
    }
  }
}
```

Now any LLM (Claude, Gemini, Antigravity, GPT-4o) can autonomously design, assemble, edit, audit, and view skins!

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

### 5. Python API Examples

#### A. Modular Lego Assembly with Automatic Seam Blending
```python
from skinforge import SkinCanvas, assemble_skin, render_3d_turnaround

# Assemble modular parts from different skin files
target_canvas, summary = assemble_skin(
    sources={
        "hair": "skins/hair_reference.png",
        "torso": "skins/tuxedo_torso.png",
        "legs": "skins/tailored_pants.png"
    },
    auto_blend_seams=True,
    auto_fix=True
)

print(f"Aesthetic score: {summary['aesthetic_score']} ({summary['aesthetic_tier']})")
target_canvas.export_png("assembled_character.png")
render_3d_turnaround("assembled_character.png", "preview_assembled.png")
```

#### B. Quality Auditing & Aesthetic Scoring
```python
from skinforge import SkinValidator, compute_aesthetic_score

# 1. Audit Minecraft rules (holes, floating cardboard planes)
validator = SkinValidator("skin_syntren.png")
valid, report = validator.validate()
print(report)

# 2. Compute aesthetic craftsmanship metrics
score_info = compute_aesthetic_score("skin_syntren.png")
print(f"Quality Tier: {score_info['tier']} (Score: {score_info['score']})")
print(f"Layer 2 Relief Ratio: {score_info['layer2_ratio']}")
print(f"Unique Colors: {score_info['unique_colors']}")
print(f"Shading Variance: {score_info['shading_variance']}")
```

---

## 🧪 Testing

SkinForge includes a comprehensive unit test suite covering session state, ASCII reverse-engineering, multimodal rendering, checkpoints, HSV adjustments, seam healing, modular assembly, aesthetic scoring, vision vectors, typography, outfits, and converter:

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -p "test_*.py"
```

```
..............................
----------------------------------------------------------------------
Ran 30 tests in 9.348s

OK
```

---

## 📜 License
MIT License. Free for personal and commercial use.
