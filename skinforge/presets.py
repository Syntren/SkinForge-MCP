"""
Reusable anatomical, facial, and clothing design presets for SkinForge (v2.0.0).

Supports 10 modular presets strictly compliant with the 4 Golden Rules of Minecraft Skin Depth:
  - anime_eyes_2x2
  - hoodie_drawstrings
  - cargo_pocket
  - hair_bangs
  - sneakers
  - headphones
  - visor_glasses (v2.0.0)
  - crown (v2.0.0)
  - scarf (v2.0.0)
  - blush_and_mouth (v2.0.0)
"""

from __future__ import annotations

from typing import Any, Callable, Dict
from .ascii_codec import normalize_color


def draw_anime_eyes_2x2(
    canvas: Any,
    left_col: int = 1,
    right_col: int = 5,
    row: int = 5,
    iris_color: str = "#af36f8",
    highlight_color: str = "#b59ddb",
    shadow_color: str = "#7d0bd2",
    shine_color: str = "#faf8fc",
    style: str = "cyber_glow",
) -> None:
    """
    Draw 2x2 anime eyes on head_front with vibrant iris and specular highlights.
    Styles:
        'cyber_glow' (recommended): 4-quadrant layout with upper shadow, lower neon iris,
                                    upper sclera, and lower specular white shine.
        'classic': Double upper shadow with lower highlight and iris.
    """
    c_iris = normalize_color(iris_color)
    c_hl = normalize_color(highlight_color)
    c_shd = normalize_color(shadow_color)
    c_shine = normalize_color(shine_color)

    if style == "cyber_glow":
        canvas.set_pixel("head_front", left_col, row, c_hl)
        canvas.set_pixel("head_front", left_col + 1, row, c_shd)
        canvas.set_pixel("head_front", left_col, row + 1, c_shine)
        canvas.set_pixel("head_front", left_col + 1, row + 1, c_iris)

        canvas.set_pixel("head_front", right_col, row, c_shd)
        canvas.set_pixel("head_front", right_col + 1, row, c_hl)
        canvas.set_pixel("head_front", right_col, row + 1, c_iris)
        canvas.set_pixel("head_front", right_col + 1, row + 1, c_shine)
    else:
        canvas.set_pixel("head_front", left_col, row, c_shd)
        canvas.set_pixel("head_front", left_col + 1, row, c_shd)
        canvas.set_pixel("head_front", left_col, row + 1, c_hl)
        canvas.set_pixel("head_front", left_col + 1, row + 1, c_iris)

        canvas.set_pixel("head_front", right_col, row, c_shd)
        canvas.set_pixel("head_front", right_col + 1, row, c_shd)
        canvas.set_pixel("head_front", right_col, row + 1, c_iris)
        canvas.set_pixel("head_front", right_col + 1, row + 1, c_hl)


def draw_hoodie_drawstrings(
    canvas: Any,
    col_left: int = 2,
    col_right: int = 5,
    row_start: int = 1,
    len_left: int = 7,
    len_right: int = 4,
    color_bright: str = "#c355ff",
    color_tip: str = "#501278",
) -> None:
    """Draw stylish asymmetrical hoodie drawstrings on body_front and jacket_front."""
    c_bright = normalize_color(color_bright)
    c_tip = normalize_color(color_tip)

    for dy in range(len_left):
        col = c_tip if dy == len_left - 1 else c_bright
        canvas.set_pixel("body_front", col_left, row_start + dy, col)
        canvas.set_pixel("jacket_front", col_left, row_start + dy, col)

    for dy in range(len_right):
        col = c_tip if dy == len_right - 1 else c_bright
        canvas.set_pixel("body_front", col_right, row_start + dy, col)
        canvas.set_pixel("jacket_front", col_right, row_start + dy, col)


def draw_cargo_pocket(
    canvas: Any,
    part_name: str = "right_pants_right",
    y_start: int = 2,
    flap_color: str = "#26222e",
    pouch_color: str = "#1e1a24",
    buckle_color: str = "#9a32dc",
) -> None:
    """Draw a 3D cargo utility pocket flap on outer leg (Layer 2)."""
    c_flap = normalize_color(flap_color)
    c_pouch = normalize_color(pouch_color)
    c_buckle = normalize_color(buckle_color)

    canvas.draw_rect(part_name, 0, y_start, 4, 1, c_flap)
    canvas.draw_rect(part_name, 0, y_start + 1, 4, 2, c_pouch)
    canvas.set_pixel(part_name, 1, y_start + 2, c_buckle)
    canvas.set_pixel(part_name, 2, y_start + 2, c_buckle)


def draw_hair_bangs(
    canvas: Any,
    style: str = "cyberpunk",
    hair_color: str = "#1e1824",
    highlight_color: str = "#9a3cd4",
) -> None:
    """
    Draw stylish 3D hair bangs on hat_front and head_front.
    Strictly complies with Rule 3: ONLY rows 0..3 are drawn on hat_front! Rows 4..7 remain 100% transparent.
    """
    c_hair = normalize_color(hair_color)
    c_hl = normalize_color(highlight_color)

    canvas.draw_rect("head_front", 0, 0, 8, 2, c_hair)
    canvas.draw_rect("head_front", 1, 2, 2, 1, c_hair)
    canvas.draw_rect("head_front", 5, 2, 2, 1, c_hair)
    canvas.set_pixel("head_front", 3, 1, c_hl)
    canvas.set_pixel("head_front", 4, 1, c_hl)

    canvas.draw_rect("hat_front", 0, 0, 8, 1, c_hair)
    canvas.draw_rect("hat_front", 0, 1, 3, 2, c_hair)
    canvas.draw_rect("hat_front", 5, 1, 3, 2, c_hair)
    canvas.set_pixel("hat_front", 1, 3, c_hair)
    canvas.set_pixel("hat_front", 6, 3, c_hair)
    canvas.set_pixel("hat_front", 2, 2, c_hl)
    canvas.set_pixel("hat_front", 5, 2, c_hl)


def draw_sneakers(
    canvas: Any,
    limb: str = "right_leg",
    sole_color: str = "#ffffff",
    body_color: str = "#16141e",
    accent_color: str = "#9a32dc",
) -> None:
    """Draw stylish sneakers with colored collar, dark body, and white sole on a leg."""
    c_sole = normalize_color(sole_color)
    c_body = normalize_color(body_color)
    c_accent = normalize_color(accent_color)

    canvas.fill_part(f"{limb}_bottom", c_sole)

    for face in ("front", "back", "right", "left"):
        part = f"{limb}_{face}"
        canvas.draw_rect(part, 0, 11, 4, 1, c_sole)
        canvas.draw_rect(part, 0, 9, 4, 2, c_body)

    canvas.draw_rect(f"{limb}_front", 1, 9, 2, 1, c_accent)


def draw_headphones(
    canvas: Any,
    earcup_color: str = "#9a32dc",
    band_color: str = "#221c2c",
    glow_color: str = "#d264ff",
) -> None:
    """Draw 3D gaming/cyberpunk headphones on Layer 2 (hat_top, hat_right, hat_left)."""
    c_ear = normalize_color(earcup_color)
    c_band = normalize_color(band_color)
    c_glow = normalize_color(glow_color)

    # Headband on hat_top (>= 20 pixels to comply with Rule 4)
    canvas.draw_rect("hat_top", 0, 2, 8, 3, c_band)
    canvas.draw_rect("hat_top", 2, 3, 4, 1, c_glow)

    for side in ("hat_right", "hat_left"):
        canvas.draw_rect(side, 3, 0, 2, 3, c_band)
        canvas.draw_rect(side, 2, 3, 4, 4, c_ear)
        canvas.draw_rect(side, 3, 4, 2, 2, c_glow)


def draw_visor_glasses(
    canvas: Any,
    lens_color: str = "#00e5ff",
    frame_color: str = "#1a1c28",
    glint_color: str = "#e8ffff",
    row: int = 4,
) -> None:
    """
    Draw sleek cyber visor / sunglasses across head_front (and side temples on hat_left/hat_right).
    Draws front lenses on head_front so Rule 3 (hat_front rows 4..7 transparent) is strictly respected.
    """
    c_lens = normalize_color(lens_color)
    c_frame = normalize_color(frame_color)
    c_glint = normalize_color(glint_color)

    r = max(2, min(5, int(row)))
    # Frame bridge & lenses on head_front
    canvas.draw_rect("head_front", 0, r, 8, 2, c_frame)
    canvas.draw_rect("head_front", 1, r, 2, 2, c_lens)
    canvas.draw_rect("head_front", 5, r, 2, 2, c_lens)
    canvas.set_pixel("head_front", 1, r, c_glint)
    canvas.set_pixel("head_front", 5, r, c_glint)

    # Side temple arms on Layer 2 (hat_left & hat_right)
    for side in ("hat_left", "hat_right"):
        canvas.draw_rect(side, 0, r, 6, 1, c_frame)


def draw_crown(
    canvas: Any,
    gold_color: str = "#f5c542",
    shadow_color: str = "#c28b1a",
    gem_color: str = "#e63946",
) -> None:
    """
    Draw a regal 3D pixel crown wrapping around Layer 2 (hat_front rows 0..2, hat_left, hat_right, hat_back).
    Strictly complies with Rule 3 (hat_front rows 4..7 remain transparent).
    """
    c_gold = normalize_color(gold_color)
    c_shd = normalize_color(shadow_color)
    c_gem = normalize_color(gem_color)

    for face in ("hat_front", "hat_back", "hat_left", "hat_right"):
        # Crown band on row 1..2
        canvas.draw_rect(face, 0, 1, 8, 1, c_gold)
        canvas.draw_rect(face, 0, 2, 8, 1, c_shd)
        # Spires on row 0
        for col in (0, 2, 5, 7):
            canvas.set_pixel(face, col, 0, c_gold)
        # Center gem
        canvas.set_pixel(face, 3, 1, c_gem)
        canvas.set_pixel(face, 4, 1, c_gem)


def draw_scarf(
    canvas: Any,
    scarf_color: str = "#c92a42",
    shadow_color: str = "#8a182c",
    stripe_color: str = "#f4e8c1",
) -> None:
    """Draw a 3D wrapped neck scarf across Layer 2 torso collar with a hanging front tail."""
    c_main = normalize_color(scarf_color)
    c_shd = normalize_color(shadow_color)
    c_str = normalize_color(stripe_color)

    for face in ("jacket_front", "jacket_back", "jacket_left", "jacket_right"):
        w = canvas.parts[face].shape[1]
        canvas.draw_rect(face, 0, 0, w, 2, c_main)
        canvas.draw_rect(face, 0, 2, w, 1, c_shd)

    # Hanging scarf tail on jacket_front
    canvas.draw_rect("jacket_front", 1, 2, 2, 4, c_main)
    canvas.draw_rect("jacket_front", 1, 4, 2, 1, c_str)
    canvas.draw_rect("jacket_front", 1, 6, 2, 1, c_shd)


def draw_blush_and_mouth(
    canvas: Any,
    blush_color: str = "#e898a8",
    mouth_color: str = "#b87a82",
) -> None:
    """Draw subtle anime cheek blush and minimal 2px mouth on head_front."""
    c_blush = normalize_color(blush_color)
    c_mouth = normalize_color(mouth_color)

    canvas.set_pixel("head_front", 1, 6, c_blush)
    canvas.set_pixel("head_front", 6, 6, c_blush)
    canvas.set_pixel("head_front", 3, 7, c_mouth)
    canvas.set_pixel("head_front", 4, 7, c_mouth)


PRESET_REGISTRY: Dict[str, Callable[..., None]] = {
    "anime_eyes_2x2": draw_anime_eyes_2x2,
    "hoodie_drawstrings": draw_hoodie_drawstrings,
    "cargo_pocket": draw_cargo_pocket,
    "hair_bangs": draw_hair_bangs,
    "sneakers": draw_sneakers,
    "headphones": draw_headphones,
    "visor_glasses": draw_visor_glasses,
    "crown": draw_crown,
    "scarf": draw_scarf,
    "blush_and_mouth": draw_blush_and_mouth,
}
