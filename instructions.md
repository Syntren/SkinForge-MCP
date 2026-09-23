# SkinForge MCP Instructions for AI Agents

SkinForge MCP is a specialized toolkit for autonomous design, inspection, editing, auditing, and verification of Minecraft 1.8+ dual-layer 64×64 skins with 3D depth and instant live preview.

---

## 1. The 4 Golden Rules of Minecraft Skin Depth (Layer Discipline)

Every agent MUST adhere strictly to these rules to avoid visual bugs in the Minecraft rendering engine:

1. **Rule 1 (Zero Holes on Layer 1 - 100% Solid Base)**:
   - All 36 parts on Layer 1 (Base Body) MUST have `alpha = 255` on every single pixel.
   - *Why*: Transparent pixels on Layer 1 render as black empty voids straight through the character's head or torso.
   - *Enforcement*: Run `skin_validate()`. Use `skin_auto_fix()` if holes exist.

2. **Rule 2 (Layer 2 is +0.35 3D Relief Only)**:
   - Layer 2 (`hat_*`, `jacket_*`, `*_sleeve_*`, `*_pants_*`) renders as a dilated 3D mesh floating +0.35 to +0.5 blocks outside Layer 1.
   - NEVER paint a solid duplicate of the entire body on Layer 2 (causes an unnatural "bloated marshmallow" bug).
   - Use Layer 2 ONLY for 3D accents: bangs/hair volume, hood rims, collar, cuffs, pocket flaps, emblems, straps.

3. **Rule 3 (No Floating Cardboard Planes on hat_front Profile)**:
   - On `hat_front`, rows 4 to 7 MUST be **100% transparent** (`.` in ASCII) across all columns.
   - *Why*: Hair bangs belong only on rows 0–3. Pixels on rows 4–7 float detached in empty air when viewed from a 90° side profile.

4. **Rule 4 (No Floating Crown Planks on hat_top)**:
   - `hat_top` must either be fully solid (e.g. hood crown) or 100% transparent (`.`).
   - NEVER leave isolated single pixel stripes hovering 0.5 blocks above the head.

---

## 2. UV Face Identifier Reference (All 72 Faces & Grid Dimensions)

Always use these exact string identifiers for `part_name` parameters:

| Region | Layer 1 (Base Body - 100% Opaque) | Layer 2 (Outer Overlay - Relief) | Dimensions (W × H) |
|---|---|---|---|
| **Head / Hat** | `head_top`, `head_bottom`<br>`head_front`, `head_back`<br>`head_right`, `head_left` | `hat_top`, `hat_bottom`<br>`hat_front`, `hat_back`<br>`hat_right`, `hat_left` | Top/Bottom: 8×8<br>Sides: 8×8 |
| **Torso / Jacket** | `body_top`, `body_bottom`<br>`body_front`, `body_back`<br>`body_right`, `body_left` | `jacket_top`, `jacket_bottom`<br>`jacket_front`, `jacket_back`<br>`jacket_right`, `jacket_left` | Top/Bottom: 8×4<br>Front/Back: 8×12<br>Flanks: 4×12 |
| **Right Arm / Sleeve** | `right_arm_top`, `right_arm_bottom`<br>`right_arm_front`, `right_arm_back`<br>`right_arm_right`, `right_arm_left` | `right_sleeve_top`, `right_sleeve_bottom`<br>`right_sleeve_front`, `right_sleeve_back`<br>`right_sleeve_right`, `right_sleeve_left` | Caps: 4×4<br>Sides: 4×12 |
| **Left Arm / Sleeve** | `left_arm_top`, `left_arm_bottom`<br>`left_arm_front`, `left_arm_back`<br>`left_arm_right`, `left_arm_left` | `left_sleeve_top`, `left_sleeve_bottom`<br>`left_sleeve_front`, `left_sleeve_back`<br>`left_sleeve_right`, `left_sleeve_left` | Caps: 4×4<br>Sides: 4×12 |
| **Right Leg / Pants** | `right_leg_top`, `right_leg_bottom`<br>`right_leg_front`, `right_leg_back`<br>`right_leg_right`, `right_leg_left` | `right_pants_top`, `right_pants_bottom`<br>`right_pants_front`, `right_pants_back`<br>`right_pants_right`, `right_pants_left` | Caps: 4×4<br>Sides: 4×12 |
| **Left Leg / Pants** | `left_leg_top`, `left_leg_bottom`<br>`left_leg_front`, `left_leg_back`<br>`left_leg_right`, `left_leg_left` | `left_pants_top`, `left_pants_bottom`<br>`left_pants_front`, `left_pants_back`<br>`left_pants_right`, `left_pants_left` | Caps: 4×4<br>Sides: 4×12 |

*Note: For arms/legs, `_right` is the character's right side, `_left` is character's left side. For the Right Arm, `_right` is outer and `_left` faces torso. For Left Arm, `_left` is outer and `_right` faces torso.*

---

## 3. Recommended Autonomous Workflow (6 Steps)

Follow this lifecycle for predictable, defect-free skin generation:

1. **Initialize or Load**:
   - `skin_new(template='base_body', skin_tone='fair', hair_color='#221c28', eye_color='#9a3cd4')` (populates 100% solid base, 0 holes).
   - Or `skin_load(file_path)` to modify an existing skin.
   - Call `viewer_start(port=8080)` to start the 300ms live Three.js sync viewer if user wants live inspection.

2. **Base Clothing & Outfits**:
   - High-level outfit generation in 1 call: `skin_apply_outfit(style='techwear_hoodie', primary_color='#1a1422', secondary_color='#2d2238', accent_color='#a037e1')` (styles: `techwear_hoodie`, `cargo_streetwear`, `casual_tshirt`).
   - Or paint base parts directly with `skin_fill_part` or `skin_set_part_ascii`.

3. **Detailing & Presets**:
   - Draw facial features, symbols, or text:
     - `skin_apply_preset(preset_name='anime_eyes_2x2', params={'row': 5, 'iris_color': '#9a3cd4', 'style': 'cyber_glow'})`
     - `skin_apply_preset(preset_name='hoodie_drawstrings')`
     - `skin_apply_preset(preset_name='hair_bangs')`
     - `skin_draw_symbol(part_name='jacket_back', symbol_name='cyber_s', color='#c864ff')`
     - `skin_draw_text(part_name='jacket_front', text='SYN', x=1, y=2, color='#ffffff')`
   - Mirror limb details symmetrically without re-drawing: `skin_mirror_limb(src_limb='right_arm', dst_limb='left_arm')`.
   - Add microtexture to remove plastic flat look: `skin_add_noise(part_name='jacket_front', amount=5)`.

4. **3D Seam Auditing & Edge Healing**:
   - Run `skin_check_seams(tolerance=35)` to detect texture tears across 3D cube folds.
   - Run `skin_align_seams(seam_name='all', mode='blend')` to automatically blend wrap-around edges.

5. **Quality Validation & Auto-Fix**:
   - Run `skin_validate()`. Check for Layer 1 holes, Rule 3 profile violations, or Rule 4 crown violations.
   - If any warnings/errors occur, run `skin_auto_fix()`.

6. **Visual Verification & Save**:
   - Run `skin_render_3d(preset='turnaround')` or `skin_render_turntable_gif()` to visually inspect the 3D model.
   - Save skin with `skin_save(file_path=...)` (synchronizes across project paths and regenerates preview images).

---

## 4. Token-Efficient Editing Guide

- **Micro-edits**: Do NOT resend full ASCII matrices for 1–4 pixels. Use `skin_set_pixels(part_name, pixels=[{'x': 2, 'y': 5, 'color': '#ffffff'}])` or `skin_set_pixel`.
- **Recoloring**: Use `skin_adjust_hsv` (hue/saturation/brightness) or `skin_replace_color` (fuzzy color swap).
- **Batching**: Group sequential edits into `skin_batch_actions` to execute in a single round-trip.
- **Reference Sampling**: Extract colors from concept art directly via `skin_sample_reference(image_path, num_colors=8)`.
- **ASCII DSL**: Use `skin_set_part_ascii(part_name, ascii_grid, palette)` where `.` is always transparent, `#` is primary color. Built-in palettes available: `'TECHWEAR_CYBERPUNK'`, `'ANIME_SKIN'`, `'CASUAL_STREETWEAR'`, `'FANTASY_KNIGHT'`.
