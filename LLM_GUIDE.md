# SkinForge: Developer & LLM Agent Guide
**Autonomous Minecraft 64×64 Skin Authoring, Layer Architecture & 3D/2D Verification**

This guide is specifically tailored for Large Language Models (LLMs) and autonomous AI coding agents operating within this repository. It provides the exact mental model, UV specifications, layer discipline rules, and Python APIs needed to create, edit, audit, and visually verify Minecraft 1.8+ dual-layer skins without human intervention.

---

## 1. Quick Start for LLM Agents

When tasked with creating, editing, or fixing a Minecraft skin:

```python
import os
import sys

# Ensure SkinForge is in sys.path
sys.path.insert(0, "/mnt/storage/My/Projects/SkinForge-MCP")

from skinforge import (
    SkinCanvas,
    Minecraft3DRenderer,
    SkinValidator,
    TECHWEAR_CYBERPUNK as P,
    render_3d_turnaround,
    render_composite_2d,
)

# 1. Initialize canvas (empty or loaded from existing skin)
canvas = SkinCanvas()
canvas.load_png("/mnt/storage/My/Projects/Skin/skin_syntren.png")

# 2. Modify parts using ASCII DSL
canvas.set_ascii("head_front", """
    HH^HH^HH
    H^H^^H^H
    hHH^^HHh
    H^HH^H^H
    HHdHH^HH
    heissieh
    HWIssIWH
    ssssssss
""", P)

# 3. Export to PNG
SKIN_OUT = "/mnt/storage/My/Projects/Skin/skin_syntren.png"
canvas.export_png(SKIN_OUT)

# 4. Audit with validator
validator = SkinValidator(SKIN_OUT)
valid, report = validator.validate()
print(report)
assert valid, "Fix critical issues identified by validator!"

# 5. Render 3D turnaround and 2D composite for self-verification
render_3d_turnaround(SKIN_OUT, "/mnt/storage/My/Projects/Skin/preview_3d_turnaround.png")
render_composite_2d(SKIN_OUT, "/mnt/storage/My/Projects/Skin/preview_2d.png")
```

---

## 2. Minecraft 1.8+ Skin Architecture & UV Specification

A modern Minecraft skin is a single **64×64 pixel RGBA PNG** containing two separate layers:
- **Layer 1 (Base Layer)**: Standard character body. Must be **100% opaque** on all base body parts (except transparent padding areas outside UV islands).
- **Layer 2 (Overlay / Outer Layer)**: Dilation mesh that floats **+0.35 to +0.5 blocks** outside Layer 1 in 3D space. Supports full alpha transparency (`alpha = 0` for cutouts).

### Complete UV Coordinate Matrix (All 72 Faces)

| Face Identifier | Layer | Texture Box `(u0, v0, u1, v1)` | Dimensions `(W × H)` | Description |
|---|---|---|---|---|
| **Head (Layer 1)** | | | | |
| `head_top` | Base | `(8, 0, 16, 8)` | 8 × 8 | Top of head / crown |
| `head_bottom` | Base | `(16, 0, 24, 8)` | 8 × 8 | Underside of chin / neck |
| `head_right` | Base | `(0, 8, 8, 16)` | 8 × 8 | Character's right side (viewer's left in front) |
| `head_front` | Base | `(8, 8, 16, 16)` | 8 × 8 | Face, eyes, nose, mouth |
| `head_left` | Base | `(16, 8, 24, 16)` | 8 × 8 | Character's left side (viewer's right in front) |
| `head_back` | Base | `(24, 8, 32, 16)` | 8 × 8 | Back of head / nape |
| **Hat / Hood (Layer 2)** | | | | |
| `hat_top` | Outer | `(40, 0, 48, 8)` | 8 × 8 | 3D hood crown |
| `hat_bottom` | Outer | `(48, 0, 56, 8)` | 8 × 8 | 3D hood collar underside |
| `hat_right` | Outer | `(32, 8, 40, 16)` | 8 × 8 | 3D hood right side |
| `hat_front` | Outer | `(40, 8, 48, 16)` | 8 × 8 | 3D bangs / 3D hood opening |
| `hat_left` | Outer | `(48, 8, 56, 16)` | 8 × 8 | 3D hood left side |
| `hat_back` | Outer | `(56, 8, 64, 16)` | 8 × 8 | 3D hood back |
| **Torso (Layer 1)** | | | | |
| `body_top` | Base | `(20, 16, 28, 20)` | 8 × 4 | Shoulder tops |
| `body_bottom` | Base | `(28, 16, 36, 20)` | 8 × 4 | Torso underside / waist |
| `body_right` | Base | `(16, 20, 20, 32)` | 4 × 12 | Right flank / side seam |
| `body_front` | Base | `(20, 20, 28, 32)` | 8 × 12 | Chest, drawstrings, pocket |
| `body_left` | Base | `(28, 20, 32, 32)` | 4 × 12 | Left flank / side seam |
| `body_back` | Base | `(32, 20, 40, 32)` | 8 × 12 | Upper & lower back |
| **Jacket (Layer 2)** | | | | |
| `jacket_top` | Outer | `(20, 32, 28, 36)` | 8 × 4 | 3D shoulder tops |
| `jacket_bottom` | Outer | `(28, 32, 36, 36)` | 8 × 4 | 3D hem underside |
| `jacket_right` | Outer | `(16, 36, 20, 48)` | 4 × 12 | 3D right side seams |
| `jacket_front` | Outer | `(20, 36, 28, 48)` | 8 × 12 | 3D drawstrings, 3D pocket flap |
| `jacket_left` | Outer | `(28, 36, 32, 48)` | 4 × 12 | 3D left side seams |
| `jacket_back` | Outer | `(32, 36, 40, 48)` | 8 × 12 | 3D emblem / back crest |
| **Right Arm (Layer 1)** | | | | |
| `right_arm_top` | Base | `(44, 16, 48, 20)` | 4 × 4 | Shoulder top cap |
| `right_arm_bottom` | Base | `(48, 16, 52, 20)` | 4 × 4 | Hand / palm bottom cap |
| `right_arm_right` | Base | `(40, 20, 44, 32)` | 4 × 12 | Outer arm (shoulder patch) |
| `right_arm_front` | Base | `(44, 20, 48, 32)` | 4 × 12 | Front bicep, forearm, hand |
| `right_arm_left` | Base | `(48, 20, 52, 32)` | 4 × 12 | Inner arm (torso-facing) |
| `right_arm_back` | Base | `(52, 20, 56, 32)` | 4 × 12 | Tricep, elbow, back of hand |
| **Right Sleeve (Layer 2)** | | | | |
| `right_sleeve_top` | Outer | `(44, 32, 48, 36)` | 4 × 4 | 3D shoulder cap |
| `right_sleeve_bottom` | Outer | `(48, 32, 52, 36)` | 4 × 4 | 3D cuff underside |
| `right_sleeve_right` | Outer | `(40, 36, 44, 48)` | 4 × 12 | 3D outer cyber badge |
| `right_sleeve_front` | Outer | `(44, 36, 48, 48)` | 4 × 12 | 3D oversized sleeve front |
| `right_sleeve_left` | Outer | `(48, 36, 52, 48)` | 4 × 12 | 3D inner sleeve |
| `right_sleeve_back` | Outer | `(52, 36, 56, 48)` | 4 × 12 | 3D oversized sleeve back |
| **Left Arm (Layer 1)** | | | | |
| `left_arm_top` | Base | `(36, 48, 40, 52)` | 4 × 4 | Shoulder top cap |
| `left_arm_bottom` | Base | `(40, 48, 44, 52)` | 4 × 4 | Hand / palm bottom cap |
| `left_arm_right` | Base | `(32, 52, 36, 64)` | 4 × 12 | Inner arm (torso-facing) |
| `left_arm_front` | Base | `(36, 52, 40, 64)` | 4 × 12 | Front bicep, forearm, hand |
| `left_arm_left` | Base | `(40, 52, 44, 64)` | 4 × 12 | Outer arm (shoulder patch) |
| `left_arm_back` | Base | `(44, 52, 48, 64)` | 4 × 12 | Tricep, elbow, back of hand |
| **Left Sleeve (Layer 2)** | | | | |
| `left_sleeve_top` | Outer | `(52, 48, 56, 52)` | 4 × 4 | 3D shoulder cap |
| `left_sleeve_bottom` | Outer | `(56, 48, 60, 52)` | 4 × 4 | 3D cuff underside |
| `left_sleeve_right` | Outer | `(48, 52, 52, 64)` | 4 × 12 | 3D inner sleeve |
| `left_sleeve_front` | Outer | `(52, 52, 56, 64)` | 4 × 12 | 3D oversized sleeve front |
| `left_sleeve_left` | Outer | `(56, 52, 60, 64)` | 4 × 12 | 3D outer cyber badge |
| `left_sleeve_back` | Outer | `(60, 52, 64, 64)` | 4 × 12 | 3D oversized sleeve back |
| **Right Leg (Layer 1)** | | | | |
| `right_leg_top` | Base | `(4, 16, 8, 20)` | 4 × 4 | Thigh top / hip connection |
| `right_leg_bottom` | Base | `(8, 16, 12, 20)` | 4 × 4 | Sneaker sole bottom |
| `right_leg_right` | Base | `(0, 20, 4, 32)` | 4 × 12 | Outer thigh / cargo pocket |
| `right_leg_front` | Base | `(4, 20, 8, 32)` | 4 × 12 | Front thigh, knee, shoe |
| `right_leg_left` | Base | `(8, 20, 12, 32)` | 4 × 12 | Inner leg seam |
| `right_leg_back` | Base | `(12, 20, 16, 32)` | 4 × 12 | Back calf, heel |
| **Right Pants (Layer 2)** | | | | |
| `right_pants_top` | Outer | `(4, 32, 8, 36)` | 4 × 4 | 3D waist cap |
| `right_pants_bottom` | Outer | `(8, 32, 12, 36)` | 4 × 4 | 3D cuff underside |
| `right_pants_right` | Outer | `(0, 36, 4, 48)` | 4 × 12 | 3D cargo pocket flap |
| `right_pants_front` | Outer | `(4, 36, 8, 48)` | 4 × 12 | 3D straps |
| `right_pants_left` | Outer | `(8, 36, 12, 48)` | 4 × 12 | 3D inner leg |
| `right_pants_back` | Outer | `(12, 36, 16, 48)` | 4 × 12 | 3D back pocket |
| **Left Leg (Layer 1)** | | | | |
| `left_leg_top` | Base | `(20, 48, 24, 52)` | 4 × 4 | Thigh top / hip connection |
| `left_leg_bottom` | Base | `(24, 48, 28, 52)` | 4 × 4 | Sneaker sole bottom |
| `left_leg_right` | Base | `(16, 52, 20, 64)` | 4 × 12 | Inner leg seam |
| `left_leg_front` | Base | `(20, 52, 24, 64)` | 4 × 12 | Front thigh, chain, shoe |
| `left_leg_left` | Base | `(24, 52, 28, 64)` | 4 × 12 | Outer thigh / cargo pocket |
| `left_leg_back` | Base | `(28, 52, 32, 64)` | 4 × 12 | Back calf, heel |
| **Left Pants (Layer 2)** | | | | |
| `left_pants_top` | Outer | `(4, 48, 8, 52)` | 4 × 4 | 3D waist cap |
| `left_pants_bottom` | Outer | `(8, 48, 12, 52)` | 4 × 4 | 3D cuff underside |
| `left_pants_right` | Outer | `(0, 52, 4, 64)` | 4 × 12 | 3D inner leg |
| `left_pants_front` | Outer | `(4, 52, 8, 64)` | 4 × 12 | 3D chain links |
| `left_pants_left` | Outer | `(8, 52, 12, 64)` | 4 × 12 | 3D cargo pocket flap |
| `left_pants_back` | Outer | `(12, 52, 16, 64)` | 4 × 12 | 3D chain wrap |

---

## 3. The 4 Golden Rules of Minecraft Skin Depth (Layer Discipline)

LLMs frequently generate visual artifacts due to a misunderstanding of how Minecraft renders dual layers in 3D. Strict adherence to these rules is mandatory:

### Rule 1: Layer 1 is 100% Solid (Zero Holes)
- All 36 Base Layer parts MUST have `alpha = 255` on every single pixel.
- **Why**: In Minecraft, if Layer 1 has transparent pixels, the engine renders an empty black void straight through the character's skull or torso.
- **Enforcement**: Run `validator.validate()` — it alerts on any transparent pixels on Layer 1.

### Rule 2: Layer 2 is Exclusively for 3D Relief (+0.35 Blocks)
- Layer 2 is rendered as a dilated 3D box floating outside Layer 1.
- DO NOT replicate the entire skin on Layer 2. If you paint a solid body on Layer 2, the character looks like a bloated marshmallow, and base-layer details are completely occluded.
- Use Layer 2 ONLY for:
  - Bangs of hair hanging over the forehead.
  - The outer hood volume and hood rim.
  - Drawstrings hanging off the chest.
  - The kangaroo pocket lip and waistband hem.
  - 3D cyber-badges on the shoulder.
  - Oversized hoodie cuffs that hang over the wrists.
  - 3D cargo pocket flaps on outer thighs.
  - The raised 3D "S" crest on the back.

### Rule 3: The "Floating Cardboard Plane" Trap (Critical Profile Bug)
- **The Bug**: On `hat_front`, if columns 0 and 7 have pixels all the way down rows 4–7 (cheeks and chin) while the center is transparent, looking at the character in profile view (side 90°) reveals two flat vertical strips of pixels floating in empty space 0.5 blocks in front of the nose!
- **The Rule**: On `hat_front`, rows 4 to 7 MUST be **100% TRANSPARENT across ALL columns** (`.` in ASCII). 3D bangs belong exclusively on rows 0 to 3!

### Rule 4: The "Floating Plank" Trap (Crown Bug)
- **The Bug**: On `hat_top`, if a stripe of pixels is drawn down columns 3–4 while columns 0–2 and 5–7 are transparent, Minecraft renders a floating wooden-style plank hovering 0.5 blocks above the head!
- **The Rule**: `hat_top` must either be **solid** (covering the hood top) or **100% transparent** (`.`). Never leave detached, isolated stripes floating on Layer 2 crowns.

---

## 4. The ASCII Art DSL (`canvas.set_ascii`)

Writing raw numerical matrices like `[[14, 12, 18, 255], ...]` leads to LLM syntax mistakes, index drift, and inability to visualize the design. SkinForge provides `set_ascii(part_name, grid_str, palette)`:

### Palette Syntax
```python
P = {
    ".": [0, 0, 0, 0],            # Always transparent
    "#": [20, 16, 24, 255],        # Primary dark fabric
    "=": [28, 24, 34, 255],        # Secondary fabric / fold
    "P": [160, 55, 225, 255],      # Neon violet core
    "B": [210, 100, 255, 255],     # Bright neon violet
    "L": [245, 185, 255, 255],     # White-violet highlight
    "s": [224, 177, 180, 255],     # Anime peach skin
    "I": [154, 60, 212, 255],      # Glowing eye iris
    "W": [233, 214, 240, 255],     # Eye corner highlight
}
```

### Grid Dimensions & Auto-Resampling
- **8×8 parts** (`head_*`, `hat_*`): Provide 8 lines of 8 characters.
- **8×12 parts** (`body_front`, `jacket_front`, `body_back`, `jacket_back`): Provide 12 lines of 8 characters (or 8 lines, and SkinForge automatically resamples to 12 rows using Minecraft's standard UV algorithm).
- **4×12 parts** (`arm_*`, `sleeve_*`, `leg_*`, `pants_*`): Provide 12 lines (or 8 lines) of 4 characters.
- **4×4 caps** (`*_top`, `*_bottom` for limbs): Provide 4 lines (or 8 lines) of 4 characters.

### Practical Example: Perfect 2×2 Anime Eyes
```python
# head_front: rows 5 and 6 form the 2x2 eyes
canvas.set_ascii("head_front", """
    HH^HH^HH
    H^H^^H^H
    hHH^^HHh
    H^HH^H^H
    HHdHH^HH
    heissieh
    HWIssIWH
    ssssssss
""", P)
```
- **Row 5 (Eye Top)**: `h` (hair), `e` (lash shadow), `i` (upper iris), `s` (skin bridge), `s` (skin bridge), `i` (upper iris), `e` (lash shadow), `h` (hair).
- **Row 6 (Eye Bottom)**: `H` (hair), `W` (lavender highlight), `I` (neon iris), `s` (skin bridge), `s` (skin bridge), `I` (neon iris), `W` (lavender highlight), `H` (hair).

---

## 5. Built-in Presets & Automation API

SkinForge includes specialized helper methods so LLMs don't have to duplicate work:

### 1. Limb Mirroring (`canvas.mirror_limb`)
Minecraft limb UVs require swapping outer and inner faces when mirroring (e.g. Right face of Right Arm is outer, but Left face of Left Arm is outer).
```python
# Automatically mirrors all 6 faces of the arm, including Layer 2 sleeve:
canvas.mirror_limb(src_limb="right_arm", dst_limb="left_arm", mirror_layer2=True)
canvas.mirror_limb(src_limb="right_leg", dst_limb="left_leg", mirror_layer2=True)
```

### 2. Microtexture / Procedural Noise (`canvas.add_noise`)
Prevents flat, plastic-looking blocks by injecting subtle per-pixel fabric variation:
```python
canvas.add_noise("body_front", amount=4)
canvas.add_noise("right_leg_front", amount=4)
```

### 3. Anatomical Helpers (`presets.py`)
```python
from skinforge import draw_anime_eyes_2x2, draw_hoodie_drawstrings, draw_cargo_pocket

# Draw eyes parametrically
draw_anime_eyes_2x2(canvas, left_col=1, right_col=5, row=5)

# Draw asymmetrical drawstrings (Layer 1 + Layer 2)
draw_hoodie_drawstrings(canvas, col_left=2, col_right=5, len_left=7, len_right=4)

# Draw 3D cargo pocket flap on Layer 2
draw_cargo_pocket(canvas, "right_pants_right", y_start=2)
```

---

## 6. The Autonomous Agent Self-Verification Loop

When working independently, an LLM MUST close the feedback loop using visual inspections:

```
[Write / Edit Skin Canvas]
          │
          ▼
   [canvas.export_png()]
          │
          ▼
[SkinValidator.validate()] ──(warnings/holes?)──► [Fix in Canvas]
          │ (pass)
          ▼
[render_3d_turnaround()]
          │
          ▼
[Call 'read' on 3D image]
          │
          ├── Visual Check 1: Side profile view has NO floating cardboard planes
          ├── Visual Check 2: Crown has NO floating detached planks
          ├── Visual Check 3: Back emblem 'S' is high-set, sharp, and readable
          └── Visual Check 4: Eyes are 2x2, symmetrical, with glowing iris
          │ (approved)
          ▼
[Task Complete]
```

### CLI Quick Verification Commands
```bash
# Check audit report
./SkinForge/cli.py inspect skins/skin_syntren.png

# Render 4-angle 3D view
./SkinForge/cli.py render skins/skin_syntren.png --out3d previews/3d_turnaround.png

# Render isolated Layer 1 vs Layer 2
./SkinForge/cli.py render skins/skin_syntren.png --layer base --out3d previews/3d_base.png
./SkinForge/cli.py render skins/skin_syntren.png --layer outer --out3d previews/3d_outer.png
```

---

## 7. Interactive 3D Web Viewer (`SkinForge/viewer.py`)

For human users, SkinForge includes a zero-dependency local 3D viewer with Three.js / WebGL:

```bash
python3 SkinForge/viewer.py
# or from root
python3 viewer.py
# or via CLI
./SkinForge/cli.py view
```
- **URL**: `http://localhost:8080` (auto-opens default browser).
- **Features**:
  - Orbit controls: Left-click drag to rotate, right-click drag to pan (translate in screen space), scroll to zoom.
  - Animation toggles: Walk (🚶), Run (🏃), Turntable Spin (🔄), Idle Pause (⏸️).
  - Angle presets: Front, Back ("S" view), Left profile, Right profile.
  - Layer toggles: Checkbox for Layer 1 (Base) and Layer 2 (Overlay).
  - **Live Auto-Reloader**: Polls `skin_syntren.png` via `/skin-status` and updates the 3D model automatically the moment the file changes on disk!

---

## 8. SkinForge MCP Server (Model Context Protocol)

SkinForge exposes a full-featured **MCP server** allowing any AI agent or LLM (e.g. Gemini, Claude, GPT-4o, Antigravity, Kilo) to author, inspect, edit, audit, and visually verify Minecraft skins via standardized tool calls.

### Starting the MCP Server

```bash
# Direct launcher
python3 SkinForge/mcp_server.py

# Or via CLI
./SkinForge/cli.py mcp

# Or via python module
python3 -m skinforge.mcp_server
```

In `.mcp.json` / `mcp_config.json`:
```json
{
  "mcpServers": {
    "skinforge": {
      "command": "python3",
      "args": ["-m", "skinforge.mcp_server"],
      "cwd": "/mnt/storage/My/Projects/SkinForge-MCP",
      "env": {
        "PYTHONPATH": "/mnt/storage/My/Projects/SkinForge-MCP"
      }
    }
  }
}
```

### Complete MCP Tool Catalog (44 Tools)

| Tool Name | Key Parameters | Description & LLM Value |
|---|---|---|
| **Session & Targets** | | |
| `skin_new` | `template='base_body'`, `skin_tone='fair'`, `hair_color`, `eye_color` | Bootstraps a 100% solid Layer 1 base body (0 holes). Eliminates token waste. |
| `skin_load` | `file_path` | Loads a 64×64 PNG from disk into active session and updates live viewer immediately. |
| `skin_save` | `file_path=None`, `also_export=None`, `update_previews=True` | **Multi-target sync & auto-previews!** Automatically exports to canonical project paths (`skin_syntren.png`, `SkinForge/skins/skin_syntren.png`, `output/skin_final.png`) and regenerates 2D/3D turnaround/bottom-up previews in 1 call. |
| `skin_get_session_info` | (none) | Returns metrics: active file, modified status, player model, undo steps, checkpoints, solid % on Layer 1, relief % on Layer 2, viewer status. |
| **History & Checkpoints** | | |
| `skin_checkpoint` | `name` | Saves named milestone snapshot of canvas state for zero-risk experimentation. |
| `skin_restore_checkpoint` | `name` | Instantly rolls back canvas to a named milestone checkpoint and updates live viewer. |
| `skin_undo` | (none) | Reverts the last canvas modification and syncs live viewer. |
| `skin_redo` | (none) | Reapplies the last undone modification and syncs live viewer. |
| **Color & HSV Vectorization** | | |
| `skin_adjust_hsv` | `part_name=None`, `hue_shift=0.0`, `sat_mult=1.0`, `val_mult=1.0`, `target_color=None`, `tolerance=30`, `layer='both'` | **Vectorized HSL/HSV Adjustments!** Instant (< 1ms) hue rotation, saturation, and brightness tuning across faces or whole skin with optional target color masking. |
| `skin_shift_hue` | `hue_shift`, `part_name=None`, `target_color=None`, `tolerance=30`, `layer='both'` | Convenience tool to rotate color hue (e.g. shift purple accents to cyan or red) without altering saturation or brightness. |
| `skin_sample_reference` | `image_path`, `x=None`, `y=None`, `region=None`, `num_colors=8` | **Direct Concept Art Sampling!** Samples exact colors or extracts dominant palettes with ASCII mappings without external Python scripts. |
| `skin_replace_color` | `old_color`, `new_color`, `part_name=None`, `tolerance=15`, `layer='both'` | **Fuzzy Color Replacement!** Recolors face or entire skin in 1 call without dumping huge grids. |
| `skin_set_pixels` | `part_name`, `pixels=[{'x', 'y', 'color'}, ...]` | **Token-Efficient Micro-Edits!** Updates 2–8 pixels directly (e.g. eyes, buttons) without full ASCII matrices. |
| `skin_list_colors` | `part_name=None`, `top_n=16` | **Color Inspector!** Lists unique colors, hex, RGB, and pixel frequency counts. |
| `skin_diff` | `other_file_path`, `part_name=None` | **Skin Diff Engine!** Compares active canvas against another skin file, returning differing parts and coordinates. |
| `skin_generate_color_ramp` | `base_color`, `steps=5` | Produces 5-step shading ramps (`_`, `#`, `=`, `+`, `~`) from any color. |
| `skin_list_palettes` | (none) | Lists available built-in palettes (`TECHWEAR_CYBERPUNK`, `ANIME_SKIN`, `CASUAL_STREETWEAR`, `FANTASY_KNIGHT`). |
| **Drawing & ASCII DSL** | | |
| `skin_get_part_ascii` | `part_name`, `tolerance=6` | **Reverse-Engineers pixels into ASCII grid + palette dict!** Enables true incremental editing. |
| `skin_set_part_ascii` | `part_name`, `ascii_grid`, `palette`, `palette_name` | Paints part with ASCII grid. Supports hex colors and named palettes. |
| `skin_fill_part` | `part_name`, `color` | Fills face with solid hex / RGBA color. |
| `skin_draw_rect` | `part_name`, `x`, `y`, `width`, `height`, `color` | Fills rectangle on a part. |
| `skin_set_pixel` | `part_name`, `x`, `y`, `color` | Sets single pixel with hex or RGBA. |
| `skin_get_pixel` | `part_name`, `x`, `y` | Reads pixel color in hex and RGBA. |
| `skin_apply_gradient` | `part_name`, `start_color`, `end_color`, `direction` | Smooth color fade (vertical / horizontal). |
| `skin_batch_actions` | `actions=[{'action': '...', ...}, ...]` | **Atomic Pipeline!** Executes multiple edits (`set_pixel`, `draw_rect`, `replace_color`, etc.) in 1 single turn. |
| **High-Level Presets & Outfits** | | |
| `skin_draw_text` | `part_name`, `text`, `x=1`, `y=1`, `color='#ffffff'`, `spacing=1` | **Pixel Typography!** Renders clean 3×5 letters, numbers, and symbols across any face. |
| `skin_draw_symbol` | `part_name`, `symbol_name`, `x=1`, `y=1`, `color='#ffffff'` | **Cyber Symbols & Crests!** Draws `cyber_s` (6×8), `heart`, `star`, `lightning`, `skull`, `cross` without coordinate guessing. |
| `skin_apply_outfit` | `style='techwear_hoodie'`, `primary_color`, `secondary_color`, `accent_color`, `trim_color` | **Full Outfits in 1 Call!** Generates coordinated anatomical outfits (`techwear_hoodie`, `cargo_streetwear`, `casual_tshirt`) adhering to 3D depth rules. |
| `skin_convert_model` | `target_model='slim'` | **Geometry Converter!** Converts between Steve (4px arms) and Alex (3px slim arms) with UV island resampling. |
| `skin_mirror_limb` | `src_limb`, `dst_limb`, `mirror_layer2=True` | Symmetry mirroring with outer/inner face swapping. |
| `skin_add_noise` | `part_name`, `amount=6` | Injects microtexture to eliminate flat plastic look. |
| `skin_apply_preset` | `preset_name`, `params` | Modular presets: `anime_eyes_2x2` (with `cyber_glow` & `classic`), `hoodie_drawstrings`, `cargo_pocket`, `hair_bangs`, `sneakers`, `headphones`. |
| `skin_clear_outer_layer` | `parts=None` | Resets Layer 2 to transparent. |
| **3D Seam Auditing & Quality** | | |
| `skin_check_seams` | `tolerance=35` | **3D Seam Auditor!** Scans all cube wrap-around edges (head ring, crown, torso, jacket) to detect texture tears. |
| `skin_align_seams` | `seam_name='all'`, `mode='blend'` | **Automatic Seam Healer!** Blends and harmonizes adjacent cube edges to eliminate 3D seams. |
| `skin_validate` | (none) | Full audit of 64×64 size, Layer 1 holes, Rule 3 profile bugs, Rule 4 crown bugs. |
| `skin_auto_fix` | `default_skin_color=None` | **One-click autonomous healing**: patches holes on Layer 1 and strips floating profile cardboard. |
| **Visual Rendering & Verification** | | |
| `skin_render_3d` | `preset='turnaround'`, `layer_mode='both'` | **Multimodal image output!** Returns base64 PNG in tool result for instant visual verification. |
| `skin_render_2d` | `layer_mode='both'`, `scale=16` | Returns 2D front/back composite image in tool result. |
| `skin_render_part` | `part_name`, `scale=16`, `show_grid=True` | Returns zoomed-in 16× view of a face with pixel grid overlay. |
| `skin_render_turntable_gif` | `frames=16`, `fps=12`, `layer_mode='both'` | Generates 360° turntable animated GIF. |
| `viewer_start` | `port=8080` | Starts background Three.js WebGL viewer with **300ms real-time auto-synchronization**. |
| `viewer_status` | (none) | Checks viewer health and active URL. |
| `viewer_stop` | (none) | Stops background viewer. |

### MCP Resources & Prompts
- **Resources**:
  - `skin://uv-map`: Full UV coordinate table with dimensions and layers.
  - `skin://layer-rules`: The 4 Golden Rules of Minecraft Skin Depth.
  - `skin://palettes`: JSON catalog of built-in palettes.
  - `skin://session-state`: Real-time session metrics.
- **Prompts**:
  - `create-skin`: Step-by-step authoring workflow.
  - `audit-and-fix-skin`: Step-by-step audit and self-healing workflow.

