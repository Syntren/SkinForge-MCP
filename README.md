# SkinForge MCP 🎨🔨 (v2.0.0)

**AI-First Model Context Protocol (MCP) Server, Procedural Hue-Shifted Pixel-Art Engine, Semantic Region Painter, Multimodal Self-Critique Loop, Portable RAG Packer & Real-Time SSE 3D WebGL Studio for Minecraft Skins.**

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/Syntren/SkinForge-MCP/releases)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-1.0%20Compliant-purple.svg)](https://modelcontextprotocol.io/)
[![Tools](https://img.shields.io/badge/MCP%20Tools-63%20Native%20Tools-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-100%25%20Passing-success.svg)]()
[![WebGL](https://img.shields.io/badge/Studio-Three.js%20WebGL%20%2B%20SSE-orange.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

SkinForge is built specifically so **autonomous AI/LLM coding agents** (Claude, Gemini, GPT-4o, Cursor, Windsurf, Kilo Code) and **human pixel artists** can design, shade, edit, inspect, audit, and visually verify top-tier Minecraft 64×64 skins (Classic 4px Steve & Slim 3px Alex, plus automatic 64×32 legacy conversion) in minimal tool round-trips.

---

## 🚀 What's New in v2.0.0 (AI-First Architecture & Pixel-Art Craftsmanship)

### 1. Modular MCP Architecture (`skinforge/mcp/`)
The 2,125-line monolithic `mcp_server.py` has been decomposed into a clean, domain-driven package while preserving **100% backward compatibility**:
- `skinforge/mcp/protocol.py` — Unified `MCPServer` (official `mcp` SDK + zero-dependency JSON-RPC 2.0 stdio fallback) + **fuzzy `"Did you mean...?"` error suggestions** (`difflib`) for mistyped UV part names and tool names.
- `skinforge/mcp/schemas.py` — Strict Pydantic v2 validation schemas.
- `skinforge/mcp/tools_session.py`, `tools_editing.py`, `tools_design.py`, `tools_audit.py`, `tools_rag.py`, `resources.py`.

### 2. Procedural Hue-Shifted Auto-Shading Engine (`skinforge/shading.py` → `skin_auto_shade`)
Solves the #1 LLM skin-authoring flaw (flat, plastic solid colors):
- 6 lighting & material styles: `directional`, `ambient_occlusion`, `cylindrical`, `fabric_folds`, `hair_strands`, and `metallic`.
- Real **HSV/temperature hue-shifting** (cooler/richer shadows toward blue-violet, warmer highlights toward yellow-gold) + optional **ordered Bayer 2×2 pixel-art dithering**.
- Strictly ignores transparent pixels (`alpha == 0`) and mathematically avoids beginner pillow-shading.

### 3. Semantic Multi-Face 3D Region Painter & 2D Primitives (`skinforge/regions.py`)
- **`skin_paint_region`**: Paint entire 3D cuboids (`head`, `hat`, `hair_cap`, `torso`, `jacket`, `arms`, `sleeves`, `legs`, `pants`, `shoes`, `hands`) with 360° wrap-around patterns (`solid`, `vertical_gradient`, `horizontal_stripes`, `vertical_stripes`, `checker`, `cuff`, `belt`, `collar`) in **1 call** instead of 6–12.
- **`skin_draw_primitive`**: Crisp Bresenham `line`, 1px `outline`, 4-connected `flood_fill`, 2-color `dither_rect`, and instant horizontal face symmetry (`mirror_x`).

### 4. Closed-Loop Multimodal Critic & Blueprint Inspector (`skin_critic`, `skin_inspect_blueprint`)
- **`skin_critic`**: In **1 call**, renders a 3D turnaround image (`ImageContent`) AND outputs quantitative craftsmanship metrics + exact copy-pasteable MCP tool recipes (`skin_auto_fix`, `skin_auto_shade`, `skin_align_seams`, `skin_denoise_palette`) to reach `top_tier` (`>= 0.85`).
- **`skin_inspect_blueprint`**: Replaces 6–8 separate inspection calls with a single token-efficient JSON overview (model, Golden Rules, 6 metrics, top colors, active Layer 2 parts, seam count, fix recipes, optional region ASCII).

### 5. Expanded Outfits, Presets, Smart Harmonies & Turbo Batching
- **`skin_generate_palette`**: Generates complete character palettes + hue-shifted ASCII dicts from a single seed color (`analogous`, `complementary`, `split_complementary`, `triadic`, `monochromatic`, `cyberpunk`), plus 2 new curated palettes (`CYBER_NINJA`, `COZY_PASTEL`).
- **7 Full-Body Outfits** (`skin_apply_outfit`, Slim 3px & Classic 4px aware): `techwear_hoodie`, `cargo_streetwear`, `casual_tshirt`, `fantasy_knight`, `cyber_ninja`, `formal_suit`, `cozy_sweater`.
- **10 Modular Presets** (`skin_apply_preset`): `anime_eyes_2x2`, `hoodie_drawstrings`, `cargo_pocket`, `hair_bangs`, `sneakers`, `headphones`, `visor_glasses`, `crown`, `scarf`, `blush_and_mouth`.
- **Upgraded `skin_batch_actions`**: Now supports **20 action types** (including `paint_region`, `auto_shade`, `draw_primitive`, `set_ascii`, `apply_outfit`, `align_seams`, `auto_fix`) plus `return_preview=True` for single-round-trip edit + 3D verification.

---

## 🧰 Complete MCP Tool Catalog (63 Native Tools)

| Category | Tools |
|---|---|
| **Session & History (9)** | `skin_new`, `skin_load`, `skin_save`, `skin_get_session_info`, `skin_checkpoint`, `skin_restore_checkpoint`, `skin_undo`, `skin_redo`, `skin_history` |
| **AI Editing, Shading & Primitives (24)** | `skin_auto_shade`, `skin_paint_region`, `skin_draw_primitive`, `skin_batch_actions`, `skin_build`, `skin_get_part_ascii`, `skin_set_part_ascii`, `skin_fill_part`, `skin_draw_rect`, `skin_set_pixel`, `skin_set_pixels`, `skin_get_pixel`, `skin_apply_gradient`, `skin_replace_color`, `skin_adjust_hsv`, `skin_shift_hue`, `skin_list_colors`, `skin_diff`, `skin_denoise_palette`, `skin_import_part`, `skin_convert_model`, `skin_mirror_limb`, `skin_add_noise`, `skin_clear_outer_layer` |
| **Design, Outfits & Palettes (8)** | `skin_generate_palette`, `skin_generate_color_ramp`, `skin_list_palettes`, `skin_apply_outfit`, `skin_apply_preset`, `skin_draw_text`, `skin_draw_symbol`, `skin_sample_reference` |
| **Rendering, Blueprint & Critic (11)** | `skin_critic`, `skin_inspect_blueprint`, `skin_render_3d`, `skin_render_2d`, `skin_render_part`, `skin_render_turntable_gif`, `skin_aesthetic_audit`, `skin_validate`, `skin_auto_fix`, `skin_check_seams`, `skin_align_seams` |
| **RAG & Lego Constructor (8)** | `skin_rag_pack`, `skin_rag_status`, `skin_search`, `skin_part_search`, `skin_search_by_image`, `skin_get_reference`, `skin_remix`, `skin_assemble` |
| **3D WebGL Studio (3)** | `viewer_start`, `viewer_status`, `viewer_stop` |

**MCP Resources (5)**: `skin://uv-map`, `skin://layer-rules`, `skin://palettes`, `skin://session-state`, `skin://regions-and-presets`  
**MCP Prompts (3)**: `create-skin`, `audit-and-fix-skin`, `restyle-skin`

---

## 📁 Repository Layout

```
SkinForge-MCP/
├── instructions.md            # AI agent system instructions (synced with skinforge/instructions.md)
├── pyproject.toml             # Python packaging metadata (v2.0.0)
├── README.md                  # Project overview & MCP documentation
├── cli.py                     # CLI (`render`, `gif`, `inspect`, `shade`, `seams`, `convert`, `rag-pack`, `view`, `mcp`)
├── mcp_server.py              # Stdio MCP server entry point
├── viewer.py                  # Interactive 3D WebGL Studio server with SSE (/api/events)
├── skinforge/                 # Modular library (v2.0.0)
│   ├── __init__.py            # Public exports (v2.0.0)
│   ├── core/                  # UV registry (72 zones), SkinCanvas, atomic PNG I/O, thread-safe SkinSession
│   ├── color/                 # Vectorized RGB/HSV/HSL/CIELAB spaces, curated palettes & harmony generator
│   ├── audit/                 # Aesthetic Engine v2 (6 metrics), 4 Golden Rules validator, 3D seam healer
│   ├── mcp/                   # Modular MCP server (protocol, schemas, session, editing, design, audit, rag, resources)
│   ├── rag/                   # Optional FTS5 BM25 + 299-dim CIELAB float16 search & portable .sfpack packer
│   ├── shading.py             # Procedural hue-shifted pixel-art auto-shading & Bayer 2x2 dithering (NEW)
│   ├── regions.py             # Semantic multi-face 3D region painter & 2D primitives (NEW)
│   ├── outfits.py             # 7 full-body coordinated outfit macros (Classic & Slim)
│   ├── presets.py             # 10 anatomical, facial & accessory presets
│   ├── renderer.py            # Software 3D Z-buffer rasterizer, 2D composite, turntable GIF
│   ├── modular.py             # Lego Constructor assembly & isolated mannequin previews
│   ├── ascii_codec.py         # ASCII DSL codec & color normalizer
│   ├── templates.py           # Solid humanoid base templates (0 holes)
│   ├── typography.py          # 3x5 pixel font & cyber symbol stamps
│   ├── converter.py           # Steve 4px <-> Alex 3px slim model converter
│   ├── sampler.py             # Reference image color & palette sampler
│   └── mcp_server.py          # Slim backward-compatible MCP facade
├── static/                    # SkinForge Studio Three.js WebGL + SSE frontend
├── examples/
│   └── build_syntren.py       # Reference script building the Syntren skin
├── scripts/
│   └── ingest_full_dataset.py # HuggingFace 900k dataset downloader & FTS5/CIELAB indexer
└── tests/                     # Automated unit & integration test suite
    ├── test_mcp_server.py
    ├── test_rag.py
    ├── test_v1.py
    └── test_v2.py             # v2.0.0 AI-first shading, regions, primitives, critic & harmony tests
```

---

## 🛠️ Quick Start

### 1. Installation

```bash
pip install -e .
```

### 2. Connecting to an MCP Client (Claude Desktop, Cursor, Windsurf, Gemini CLI)

Add SkinForge to your `.mcp.json` / MCP client configuration:

```json
{
  "mcpServers": {
    "skinforge": {
      "command": "python3",
      "args": ["/absolute/path/to/SkinForge-MCP/mcp_server.py"]
    }
  }
}
```

### 3. CLI Usage

```bash
# Apply procedural hue-shifted auto-shading to any skin PNG
python3 cli.py shade skins/skin_syntren.png --style directional --strength 0.35 --out skins/shaded.png

# Pack a folder of .png skins or a .zip archive into a portable RAG database
python3 cli.py rag-pack ./skins --out data/skins_rag.sfpack --overwrite

# Launch SkinForge Studio (SSE 3D WebGL Viewer)
python3 cli.py view
```

### 4. Running the Test Suite

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -p "test_*.py" -v
```

---

## 📜 License
MIT License.
