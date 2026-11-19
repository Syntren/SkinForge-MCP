# SkinForge MCP Instructions for AI Agents (v2.0.0)

SkinForge MCP is an **AI-first** autonomous toolkit for designing, shading, inspecting, editing, auditing, packing, and visually verifying Minecraft 1.8+ dual-layer 64×64 skins (with automatic legacy 64×32 → 64×64 conversion and Alex Slim 3px / Classic Steve 4px support), 3D depth, and SSE real-time live sync viewer (/api/events).

---

## 1. The 4 Golden Rules of Minecraft Skin Depth (Layer Discipline)

Every agent MUST adhere strictly to these rules to avoid visual bugs in the Minecraft rendering engine:

1. **Rule 1 (Zero Holes on Layer 1 - 100% Solid Base)**:
   - All 36 parts on Layer 1 (Base Body) MUST have `alpha = 255` on every single pixel.
   - *Why*: Transparent pixels on Layer 1 render as black empty voids straight through the character's head or torso.
   - *Enforcement*: Run `skin_critic()` or `skin_validate()`. Use `skin_auto_fix()` if holes exist.

2. **Rule 2 (Layer 2 is +0.35 3D Relief Only)**:
   - Layer 2 (`hat_*`, `jacket_*`, `*_sleeve_*`, `*_pants_*`) renders as a dilated 3D mesh floating +0.35 to +0.5 blocks outside Layer 1 (optimal **12%–45%** coverage, never >65%).
   - NEVER paint a solid duplicate of the entire body on Layer 2 (causes an unnatural "bloated marshmallow" bug).
   - Use Layer 2 ONLY for 3D accents: bangs/hair volume, hood rims, collar, cuffs, pocket flaps, scarves, emblems, straps.

3. **Rule 3 (No Floating Cardboard Planes on `hat_front` Profile)**:
   - On `hat_front`, rows 4 to 7 MUST be **100% transparent** (`.` in ASCII) across all columns.
   - *Why*: Hair bangs and crowns belong only on rows 0–3. Pixels on rows 4–7 float detached in empty air when viewed from a 90° side profile.

4. **Rule 4 (No Floating Crown Planks on `hat_top`)**:
   - `hat_top` must either be solid (`>= 20` pixels, e.g. hood crown or thick headphone band) or 100% transparent (`.`).
   - NEVER leave isolated single pixel stripes (`< 20` pixels) hovering 0.5 blocks above the head.

---

## 2. v2.0.0 AI Superpower Tools (Fastest Path to Top-Tier Skins)

Use these high-level tools instead of hand-coding 72 raw ASCII matrices:

1. **`skin_generate_palette(seed_color, harmony="split_complementary")`**:
   - Generates a complete cohesive character palette (`primary_deep`, `primary_shadow`, `primary`, `primary_highlight`, `secondary`, `accent`, `trim`, `outfit_args`, `ascii_palette`) using HSV color theory (`analogous`, `complementary`, `split_complementary`, `triadic`, `monochromatic`, `cyberpunk`).
2. **`skin_paint_region(region, color, secondary_color=None, pattern="solid", row_start=None, row_end=None)`**:
   - Paints an entire 3D anatomical cuboid (`head`, `hat`, `hair_cap`, `hat_cap`, `torso`, `jacket`, `arms`, `sleeves`, `legs`, `pants`, `right_arm`, `left_arm`, `right_leg`, `left_leg`, `shoes`, `hands`) with 360° wrap-around patterns (`solid`, `vertical_gradient`, `horizontal_stripes`, `vertical_stripes`, `checker`, `cuff`, `belt`, `collar`) in **1 call**.
3. **`skin_auto_shade(target="base", style="directional", strength=0.35, hue_shift_deg=18.0, dither=False)`**:
   - Eliminates flat plastic shading automatically! Applies vectorized **hue-shifted pixel-art lighting** (cooler shadows, warmer highlights) with styles: `directional`, `ambient_occlusion`, `cylindrical`, `fabric_folds`, `hair_strands`, `metallic`, plus optional ordered Bayer 2×2 dithering. Strictly avoids pillow shading and preserves `alpha == 0`.
4. **`skin_draw_primitive(part_name, primitive, ...)`**:
   - Draws crisp 2D pixel primitives on any UV face: `line` (Bresenham), `outline` (1px border), `flood_fill` (4-connected bucket fill), `dither_rect` (2-color Bayer checkerboard), and `mirror_x` (instant left-to-right facial/chest symmetry!).
5. **`skin_inspect_blueprint(include_ascii_region=None, top_colors=8)`**:
   - Replaces 6–8 separate inspection calls with **1 compact JSON snapshot**: model type, Golden Rules status, 6-metric Aesthetic Score, top colors, active Layer 2 parts, seam count, fix recipes, and optional ASCII grids for a chosen region.
6. **`skin_critic(layer_mode="both")`**:
   - **Closed-loop multimodal self-critique**: In ONE call, renders a 3D turnaround image AND returns exact copy-pasteable MCP tool recipes (`skin_auto_fix`, `skin_auto_shade`, `skin_align_seams`, `skin_denoise_palette`) to push the skin to `top_tier` (`>= 0.85`).
7. **`skin_batch_actions(actions=[...], return_preview=True)`**:
   - Bundles up to dozens of edits (`paint_region`, `set_ascii`, `apply_outfit`, `apply_preset`, `draw_primitive`, `auto_shade`, `align_seams`, `auto_fix`, `mirror_limb`, etc.) into **1 atomic undoable call** and optionally returns a 3D turnaround preview image immediately.

---

## 3. UV Face Identifier Reference (All 72 Faces & Grid Dimensions)

Always use these exact string identifiers for `part_name` parameters (mistyped names automatically return fuzzy `"Did you mean...?"` suggestions):

| Region | Layer 1 (Base Body - 100% Opaque) | Layer 2 (Outer Overlay - Relief) | Dimensions (W × H) |
|---|---|---|---|
| **Head / Hat** | `head_top`, `head_bottom`, `head_front`, `head_back`, `head_right`, `head_left` | `hat_top`, `hat_bottom`, `hat_front`, `hat_back`, `hat_right`, `hat_left` | Top/Bottom: 8×8, Sides: 8×8 |
| **Torso / Jacket** | `body_top`, `body_bottom`, `body_front`, `body_back`, `body_right`, `body_left` | `jacket_top`, `jacket_bottom`, `jacket_front`, `jacket_back`, `jacket_right`, `jacket_left` | Top/Bottom: 8×4, Front/Back: 8×12, Flanks: 4×12 |
| **Right Arm / Sleeve** | `right_arm_top`, `right_arm_bottom`, `right_arm_front`, `right_arm_back`, `right_arm_right`, `right_arm_left` | `right_sleeve_top`, `right_sleeve_bottom`, `right_sleeve_front`, `right_sleeve_back`, `right_sleeve_right`, `right_sleeve_left` | Classic: 4×4 caps, 4×12 sides<br>Slim: 3×4 caps, 3×12 front/back, 4×12 flanks |
| **Left Arm / Sleeve** | `left_arm_top`, `left_arm_bottom`, `left_arm_front`, `left_arm_back`, `left_arm_right`, `left_arm_left` | `left_sleeve_top`, `left_sleeve_bottom`, `left_sleeve_front`, `left_sleeve_back`, `left_sleeve_right`, `left_sleeve_left` | Same as Right Arm |
| **Right Leg / Pants** | `right_leg_top`, `right_leg_bottom`, `right_leg_front`, `right_leg_back`, `right_leg_right`, `right_leg_left` | `right_pants_top`, `right_pants_bottom`, `right_pants_front`, `right_pants_back`, `right_pants_right`, `right_pants_left` | Caps: 4×4, Sides: 4×12 |
| **Left Leg / Pants** | `left_leg_top`, `left_leg_bottom`, `left_leg_front`, `left_leg_back`, `left_leg_right`, `left_leg_left` | `left_pants_top`, `left_pants_bottom`, `left_pants_front`, `left_pants_back`, `left_pants_right`, `left_pants_left` | Caps: 4×4, Sides: 4×12 |

---

## 4. Recommended Autonomous Workflow (5-Step High-Craft Loop)

1. **Plan & Initialize**:
   - Call `skin_generate_palette(seed_color="#...", harmony="split_complementary")` to establish harmonious colors.
   - Call `skin_new(template="base_body", skin_tone="fair", hair_color=..., eye_color=...)` (or `skin_load(file_path)` to edit an existing skin; save a backup with `skin_checkpoint("original")`).
2. **Macro Composition (1–2 calls)**:
   - Call `skin_apply_outfit(style=..., ...)` (7 styles: `techwear_hoodie`, `cargo_streetwear`, `casual_tshirt`, `fantasy_knight`, `cyber_ninja`, `formal_suit`, `cozy_sweater`) OR `skin_paint_region(...)` to block in hair, clothing, cuffs, belts, and shoes.
3. **Detailing & Procedural Shading (1 atomic batch call)**:
   - Use `skin_batch_actions(..., return_preview=True)` to apply presets (`anime_eyes_2x2`, `hair_bangs`, `visor_glasses`, `crown`, `scarf`, `headphones`, `blush_and_mouth`, `hoodie_drawstrings`, `cargo_pocket`, `sneakers`), custom ASCII grids, `draw_primitive` (`mirror_x`, `line`, `outline`), `mirror_limb`, and `auto_shade` (`directional`, `hair_strands`, `fabric_folds`, `metallic`, `ambient_occlusion`).
4. **Closed-Loop Critique & Polish**:
   - Call `skin_critic()` to inspect the 3D turnaround image alongside exact fix recipes.
   - Apply any suggested `skin_align_seams()`, `skin_auto_fix()`, or targeted `skin_set_pixels()` micro-edits.
5. **Atomic Save**:
   - Call `skin_save(file_path=...)` to atomically write the 64×64 PNG and previews.

---

## 5. RAG, Modular Lego Constructor & History

- **RAG Packing & Search** (optional, graceful degradation): `skin_rag_pack(source_path, output_path=None, metadata_path=None, min_score=0.0, overwrite=False)`, `skin_rag_status()`, `skin_search(query, limit=5, min_quality="medium", render_previews=True)`, `skin_part_search(category, query, limit=5, min_quality="medium", render_previews=True)`, `skin_search_by_image`, `skin_get_reference`, `skin_remix`, `skin_assemble(components={"hair": "...", "torso": "..."}, auto_blend_seams=True, auto_fix=True)`, `skin_import_part`.
- **History & Undo/Redo**: 30-step thread-safe `skin_undo()`, `skin_redo()`, `skin_history()`, plus named `skin_checkpoint(name)` / `skin_restore_checkpoint(name)`.
- **MCP Resources**: `skin://uv-map`, `skin://layer-rules`, `skin://palettes`, `skin://session-state`, `skin://regions-and-presets`.
- **MCP Prompts**: `create-skin`, `audit-and-fix-skin`, `restyle-skin`.
