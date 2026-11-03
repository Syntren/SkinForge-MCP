# SkinForge MCP 🎨🔨 (v1.3.0)

**Autonomous Model Context Protocol (MCP) Server, Procedural Pixel-Art Engine, Portable RAG Packer & Real-Time SSE 3D WebGL Studio for Minecraft Skins.**

[![Version](https://img.shields.io/badge/version-1.3.0-blue.svg)](https://github.com/Syntren/SkinForge-MCP/releases)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-1.0%20Compliant-purple.svg)](https://modelcontextprotocol.io/)
[![Tools](https://img.shields.io/badge/MCP%20Tools-37%20Native%20Tools-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-100%25%20Passing-success.svg)]()
[![WebGL](https://img.shields.io/badge/Studio-Three.js%20WebGL%20%2B%20SSE-orange.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

SkinForge is an all-in-one professional architecture designed for both **human skin artists** and **autonomous AI/LLM coding agents** (Gemini, Claude, GPT-4o, Cursor, Windsurf) to create, sample, inspect, edit, audit, pack, search, and visually verify Minecraft skins with true 3D dual-layer depth.

---

## 🚀 What's New in v1.3.0

1. **Core Architectural Refactoring (`skinforge/core/`)**:
   - **Single Source of Truth for UV (`skinforge/core/uv.py`)**: Strictly typed registry of all **72 UV zones** (36 Base Layer + 36 Outer Overlay zones) for both `classic` (Steve 4px) and `slim` (Alex 3px) player models, plus coordinate-to-zone hover lookup (`lookup_uv_coord`).
   - **Automatic Legacy `64x32` → `64x64` Conversion**: Loading any pre-1.8 `64x32` skin automatically converts it to modern `64x64` format with mirrored left limbs and 100% solid Base Layer opacity.
   - **Thread-Safe Session & Atomic PNG I/O (`skinforge/core/session.py`)**: `RLock`-protected session state with 30-step `undo_stack` / `redo_stack`, new `skin_history` MCP tool, and atomic `.tmp` + `os.replace()` PNG writes so `viewer.py` never reads partial textures.

2. **Vectorized Color Engine (`skinforge/color/`)**:
   - Pure NumPy vectorized conversions across `RGB <-> HSV`, `RGB <-> HSL`, and perceptual `RGB <-> CIELAB` (CIE D65).
   - Strict exclusion of transparent pixels (`alpha == 0`) across all palette, shading, coherence, and hue-shift calculations.
   - Zero division-by-zero risks (`np.divide(..., where=...)`) and strict `uint8` overflow clamping (`np.clip(..., 0, 255).astype(np.uint8)`).

3. **Aesthetic Engine v2 & 4 Golden Rules (`skinforge/audit/`)**:
   - Evaluates **6 craftsmanship dimensions**: `3D Relief Depth`, `Palette Harmony`, `Shading Depth`, `Spatial Cluster Coherence`, `Vectorized Hue Shifting`, and `Seam Continuity`.
   - Deterministic self-healing (`skin_auto_fix`) across all **4 Golden Rules**:
     - **Rule 1**: Zero Holes on Base Layer (all 36 base parts 100% opaque).
     - **Rule 2**: +0.35 3D Relief (thins bloated `>65%` marshmallow outer layers and synthesizes relief accents when empty).
     - **Rule 3**: `hat_front` rows `4–7` strictly 100% transparent (eliminates floating profile cardboard planes).
     - **Rule 4**: `hat_top` free of isolated floating crown planks (`<20` px).

4. **Graceful RAG Degradation & Portable Database Packer (`skinforge/rag/`)**:
   - **Zero-Dependency Operation**: Works out-of-the-box without a pre-installed 900k skin database; search tools return structured guidance pointing to `skin_rag_pack`.
   - **Portable `.sfpack` / `.db` Packer (`skin_rag_pack` & `cli.py rag-pack`)**: Ingests any folder of `.png` skins or `.zip` archive (with optional `.json`/`.csv` metadata), validates & converts skins, computes `aesthetic_score`, serializes **299-dimensional CIELAB spatial-color pyramids** as compact `float16` BLOBs (598 bytes/skin), stores compressed PNG BLOBs, and indexes captions/tags in **SQLite FTS5 (BM25)**.

5. **SkinForge Studio v1.3.0 (`viewer.py` + `static/`)**:
   - **Server-Sent Events (`/api/events`)**: Instant push updates of skin texture, model (`classic`/`slim`), and live audit telemetry over `ThreadingHTTPServer`, with `/api/status` retained as fallback.
   - **Studio Controls**: Animations (`Idle`, `Walk`, `Run`, `Wave`, `Fly`, `Pause`), animation speed slider, turntable rotation, and lighting presets (`Studio`, `Daylight`, `Unlit Flat Pixel-Art` with zero face shading).
   - **Layer Toggle Matrix**: Independent Base (L1) and Outer (L2) visibility checkboxes for `Head`, `Torso`, `Arms`, and `Legs`.
   - **Interactive 2D UV Map Preview (64×64)**: Corner pixel-art preview with real-time hover inspector displaying UV part name, layer, `X/Y` coordinates, and `HEX` color.
   - **One-Click Exports**: `Export Skin PNG` and `Screenshot 3D PNG`.

---

## 📁 Repository Layout

```
SkinForge-MCP/
├── instructions.md            # System instructions & architectural guide for AI models / MCP clients
├── pyproject.toml             # Python packaging metadata (v1.3.0)
├── README.md                  # Project overview & documentation
├── cli.py                     # Command-line interface (including `rag-pack`)
├── mcp_server.py              # Stdio MCP server entry point
├── viewer.py                  # Interactive 3D WebGL Studio server with SSE (/api/events)
├── skinforge/                 # Refactored modular library (v1.3.0)
│   ├── __init__.py            # Public exports (v1.3.0)
│   ├── core/                  # Core UV, Canvas & Session architecture
│   │   ├── uv.py              # 72 UV zones (classic & slim) + 64x32 -> 64x64 converter
│   │   ├── canvas.py          # SkinCanvas, atomic PNG I/O, 30-step undo/redo
│   │   └── session.py         # Thread-safe SkinSession manager
│   ├── color/                 # Vectorized Color Engine
│   │   ├── spaces.py          # RGB <-> HSV / HSL / CIELAB (alpha==0 safe)
│   │   └── palettes.py        # Curated palettes & 5-step color ramp generator
│   ├── audit/                 # Aesthetic Engine v2 & 4 Golden Rules
│   │   ├── aesthetic.py       # 6-dimensional craftsmanship scorer & Golden Rules evaluator
│   │   ├── validator.py       # SkinValidator & deterministic auto_fix_skin
│   │   └── seams.py           # 3D cuboid seam continuity checker & blender
│   ├── rag/                   # Optional RAG & Portable Packer
│   │   ├── engine.py          # SkinRAG with graceful degradation, FTS5 BM25 & visual search
│   │   ├── packer.py          # Folder / ZIP -> SQLite .sfpack / .db packer
│   │   └── vision.py          # 299-dim CIELAB spatial pyramid (float16 BLOB codec)
│   ├── mcp_server.py          # MCPServer with Pydantic schemas & unified error handling
│   ├── modular.py             # Lego Constructor: assembly & isolated mannequin previews
│   ├── renderer.py            # Software 3D Z-buffer rasterizer, 2D composite, turntable GIF
│   ├── ascii_codec.py         # ASCII DSL codec & color normalizer
│   ├── templates.py           # Solid humanoid base templates (0 holes)
│   ├── presets.py             # Anatomical & clothing presets
│   ├── typography.py          # 3x5 pixel font & cyber symbol stamps
│   ├── outfits.py             # Full-body coordinated outfit macros
│   ├── converter.py           # Steve 4px <-> Alex 3px slim model converter
│   └── sampler.py             # Reference image color & palette sampler
├── static/                    # SkinForge Studio WebGL Frontend
│   ├── index.html             # Studio UI markup
│   ├── style.css              # Dark premium glassmorphic theme
│   ├── app.js                 # SSE client, Layer Matrix, 2D UV Inspector & 3D controls
│   └── skinview3d.bundle.js   # Offline Three.js WebGL skinview3d bundle
├── examples/
│   └── build_syntren.py       # Reference script building the Syntren skin
├── scripts/
│   └── ingest_full_dataset.py # HuggingFace 900k dataset downloader & v1.3.0 FTS5/CIELAB indexer
├── skins/
│   └── skin_syntren.png       # 64x64 RGBA canonical skin
└── tests/                     # Automated unit & integration test suite (100% passing)
    ├── test_mcp_server.py
    ├── test_rag.py
    └── test_v1.py
```

---

## 🛠️ Quick Start

### 1. Installation

```bash
pip install -e .
```

### 2. Packing a Custom RAG Skin Database (`rag-pack` / `skin_rag_pack`)

```bash
# Pack a folder of .png skins (or a .zip archive) + optional .json/.csv metadata into a single portable file:
python3 cli.py rag-pack ./skins --out data/skins_rag.sfpack --overwrite
```

### 3. Launching SkinForge Studio (SSE 3D WebGL Viewer)

```bash
python3 viewer.py
# Or via CLI:
python3 cli.py view
```

### 4. Running the Test Suite

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -p "test_*.py" -v
```

---

## 📜 License
MIT License.
