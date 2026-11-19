"""
Full Outfit & Style Macro Presets for SkinForge (v2.0.0).

Allows LLMs to generate complete, coordinated outfits across torso, limbs, and 3D outer layers
in a single tool call, strictly enforcing Rule 1 (0 holes) and Rule 2 (optimal +0.35 relief),
and automatically adapting to both Classic (4px) and Alex Slim (3px) arm geometries.

Supported Styles (7):
  - 'techwear_hoodie'
  - 'cargo_streetwear'
  - 'casual_tshirt'
  - 'fantasy_knight' (v2.0.0)
  - 'cyber_ninja' (v2.0.0)
  - 'formal_suit' (v2.0.0)
  - 'cozy_sweater' (v2.0.0)
"""

from __future__ import annotations

from typing import Any, Dict, List
from .ascii_codec import normalize_color
from .presets import (
    draw_cargo_pocket,
    draw_hoodie_drawstrings,
    draw_scarf,
    draw_sneakers,
)
from .typography import draw_symbol

OUTFIT_STYLES: List[str] = [
    "techwear_hoodie",
    "cargo_streetwear",
    "casual_tshirt",
    "fantasy_knight",
    "cyber_ninja",
    "formal_suit",
    "cozy_sweater",
]


def _part_w(canvas: Any, part_name: str) -> int:
    return int(canvas.parts[part_name].shape[1])


def apply_outfit(
    canvas: Any,
    style: str = "techwear_hoodie",
    primary_color: str = "#141018",
    secondary_color: str = "#1c1822",
    accent_color: str = "#af36f8",
    trim_color: str = "#faf8fc",
) -> Dict[str, Any]:
    """Apply a complete coordinated anatomical outfit across Layer 1 and Layer 2."""
    c_prim = normalize_color(primary_color)
    c_sec = normalize_color(secondary_color)
    c_acc = normalize_color(accent_color)
    c_trim = normalize_color(trim_color)

    style = style.lower().strip()
    if style not in OUTFIT_STYLES:
        raise ValueError(f"Unknown outfit style '{style}'. Supported styles: {OUTFIT_STYLES}")

    parts_modified: List[str] = []

    if style in ("techwear_hoodie", "cargo_streetwear"):
        for part in ("body_front", "body_back", "body_left", "body_right", "body_top", "body_bottom"):
            canvas.fill_part(part, c_prim)
            parts_modified.append(part)

        canvas.draw_rect("body_left", 1, 4, 2, 6, c_sec)
        canvas.draw_rect("body_right", 1, 4, 2, 6, c_sec)

        for part in ("jacket_left", "jacket_right", "jacket_top", "jacket_bottom"):
            canvas.fill_part(part, c_sec)
            parts_modified.append(part)

        draw_hoodie_drawstrings(
            canvas,
            col_left=2,
            col_right=5,
            row_start=1,
            len_left=7,
            len_right=4,
            color_bright=accent_color,
            color_tip=primary_color,
        )
        parts_modified.extend(["body_front", "jacket_front"])

        canvas.draw_rect("jacket_front", 1, 8, 6, 3, c_sec)
        canvas.draw_rect("jacket_front", 0, 9, 8, 1, c_prim)

        try:
            draw_symbol(canvas, "jacket_back", "cyber_s", x=1, y=2, color=accent_color)
            canvas.set_pixel("jacket_back", 6, 3, c_trim)
            parts_modified.append("jacket_back")
        except Exception:
            pass

        for limb in ("right_arm", "left_arm"):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{limb}_{f}"
                canvas.draw_rect(p_name, 0, 0, _part_w(canvas, p_name), 8, c_prim)
                parts_modified.append(p_name)

        for sleeve in ("right_sleeve", "left_sleeve"):
            for f in ("front", "back", "left", "right"):
                p_name = f"{sleeve}_{f}"
                w = _part_w(canvas, p_name)
                canvas.draw_rect(p_name, 0, 6, w, 3, c_sec)
                canvas.set_pixel(p_name, min(1, w - 1), 7, c_acc)
                parts_modified.append(p_name)

        for leg in ("right_leg", "left_leg"):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{leg}_{f}"
                canvas.draw_rect(p_name, 0, 0, 4, 9, c_prim)
                parts_modified.append(p_name)

        draw_cargo_pocket(canvas, "right_pants_right", y_start=2, flap_color=secondary_color, pouch_color=primary_color, buckle_color=accent_color)
        draw_cargo_pocket(canvas, "left_pants_left", y_start=2, flap_color=secondary_color, pouch_color=primary_color, buckle_color=accent_color)
        parts_modified.extend(["right_pants_right", "left_pants_left"])

        draw_sneakers(canvas, limb="right_leg", sole_color=trim_color, body_color=primary_color, accent_color=accent_color)
        draw_sneakers(canvas, limb="left_leg", sole_color=trim_color, body_color=primary_color, accent_color=accent_color)
        parts_modified.extend(["right_leg_front", "left_leg_front", "right_leg_bottom", "left_leg_bottom"])

    elif style == "casual_tshirt":
        for part in ("body_front", "body_back", "body_left", "body_right", "body_top"):
            canvas.fill_part(part, c_prim)
            parts_modified.append(part)

        canvas.draw_rect("body_front", 2, 0, 4, 1, c_trim)
        canvas.draw_rect("body_front", 0, 11, 8, 1, "#261e1a")
        canvas.set_pixel("body_front", 3, 11, c_acc)

        # Short sleeves
        for limb in ("right_arm", "left_arm"):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{limb}_{f}"
                canvas.draw_rect(p_name, 0, 0, _part_w(canvas, p_name), 4, c_prim)
                parts_modified.append(p_name)

        jeans_blue = "#1e2a3a"
        jeans_dark = "#151e2a"
        for leg in ("right_leg", "left_leg"):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{leg}_{f}"
                canvas.draw_rect(p_name, 0, 0, 4, 9, jeans_blue)
                canvas.draw_rect(p_name, 0, 4, 4, 2, jeans_dark)
                parts_modified.append(p_name)

        draw_sneakers(canvas, limb="right_leg", sole_color=trim_color, body_color=secondary_color, accent_color=accent_color)
        draw_sneakers(canvas, limb="left_leg", sole_color=trim_color, body_color=secondary_color, accent_color=accent_color)

    elif style == "fantasy_knight":
        # Steel cuirass + gold/accent trim + 3D pauldrons & greaves
        for part in ("body_front", "body_back", "body_left", "body_right", "body_top", "body_bottom"):
            canvas.fill_part(part, c_prim)
            parts_modified.append(part)

        # Chestplate emblem & belt
        canvas.draw_rect("body_front", 2, 2, 4, 5, c_sec)
        canvas.draw_rect("body_front", 3, 3, 2, 3, c_acc)
        canvas.draw_rect("body_front", 0, 10, 8, 2, c_sec)
        canvas.draw_rect("body_front", 3, 10, 2, 2, c_trim)

        # 3D breastplate rim & back cape clasp on Layer 2
        canvas.draw_rect("jacket_front", 1, 1, 6, 1, c_trim)
        canvas.draw_rect("jacket_front", 0, 10, 8, 1, c_acc)
        canvas.draw_rect("jacket_back", 1, 0, 6, 10, c_acc)
        canvas.draw_rect("jacket_back", 1, 9, 6, 1, c_trim)
        parts_modified.extend(["jacket_front", "jacket_back"])

        # Armored arms + 3D pauldrons & gauntlets
        for limb, sleeve in (("right_arm", "right_sleeve"), ("left_arm", "left_sleeve")):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{limb}_{f}"
                canvas.draw_rect(p_name, 0, 0, _part_w(canvas, p_name), 12, c_prim)
                parts_modified.append(p_name)
            for f in ("front", "back", "left", "right"):
                s_name = f"{sleeve}_{f}"
                w = _part_w(canvas, s_name)
                canvas.draw_rect(s_name, 0, 0, w, 3, c_sec)
                canvas.draw_rect(s_name, 0, 2, w, 1, c_trim)
                canvas.draw_rect(s_name, 0, 8, w, 3, c_sec)
                parts_modified.append(s_name)

        # Armored greaves & boots
        for leg, pants in (("right_leg", "right_pants"), ("left_leg", "left_pants")):
            for f in ("front", "back", "left", "right", "top", "bottom"):
                p_name = f"{leg}_{f}"
                canvas.fill_part(p_name, c_sec)
                parts_modified.append(p_name)
            for f in ("front", "back", "left", "right"):
                o_name = f"{pants}_{f}"
                canvas.draw_rect(o_name, 0, 6, 4, 4, c_prim)
                canvas.draw_rect(o_name, 0, 6, 4, 1, c_trim)
                parts_modified.append(o_name)

    elif style == "cyber_ninja":
        # Sleek dark shinobi bodysuit + neon chest harness + 3D scarf + leg wraps
        for part in ("body_front", "body_back", "body_left", "body_right", "body_top", "body_bottom"):
            canvas.fill_part(part, c_prim)
            parts_modified.append(part)

        # Diagonal neon chest strap on Layer 2
        for i in range(6):
            canvas.set_pixel("jacket_front", 1 + i, 2 + i, c_acc)
            canvas.set_pixel("jacket_back", 6 - i, 2 + i, c_acc)
        draw_scarf(canvas, scarf_color=accent_color, shadow_color=secondary_color, stripe_color=trim_color)
        parts_modified.extend(["jacket_front", "jacket_back", "jacket_left", "jacket_right"])

        # Forearm wraps & glowing wrist bands
        for limb, sleeve in (("right_arm", "right_sleeve"), ("left_arm", "left_sleeve")):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{limb}_{f}"
                canvas.draw_rect(p_name, 0, 0, _part_w(canvas, p_name), 10, c_prim)
                parts_modified.append(p_name)
            for f in ("front", "back", "left", "right"):
                s_name = f"{sleeve}_{f}"
                w = _part_w(canvas, s_name)
                canvas.draw_rect(s_name, 0, 6, w, 3, c_sec)
                canvas.draw_rect(s_name, 0, 7, w, 1, c_acc)
                parts_modified.append(s_name)

        # Shinobi trousers & ankle wraps
        for leg, pants in (("right_leg", "right_pants"), ("left_leg", "left_pants")):
            for f in ("front", "back", "left", "right", "top", "bottom"):
                p_name = f"{leg}_{f}"
                canvas.fill_part(p_name, c_prim)
                parts_modified.append(p_name)
            for f in ("front", "back", "left", "right"):
                o_name = f"{pants}_{f}"
                canvas.draw_rect(o_name, 0, 7, 4, 3, c_sec)
                canvas.draw_rect(o_name, 0, 8, 4, 1, c_acc)
                parts_modified.append(o_name)

    elif style == "formal_suit":
        # Tailored suit jacket, crisp white shirt V, tie, cuffs, dress shoes
        for part in ("body_front", "body_back", "body_left", "body_right", "body_top", "body_bottom"):
            canvas.fill_part(part, c_prim)
            parts_modified.append(part)

        # White dress shirt & tie on body_front
        canvas.draw_rect("body_front", 2, 0, 4, 4, c_trim)
        canvas.draw_rect("body_front", 3, 0, 2, 7, c_acc)
        # 3D Lapels on jacket_front
        canvas.draw_rect("jacket_front", 1, 0, 1, 5, c_sec)
        canvas.draw_rect("jacket_front", 6, 0, 1, 5, c_sec)
        canvas.draw_rect("jacket_front", 2, 4, 1, 3, c_sec)
        canvas.draw_rect("jacket_front", 5, 4, 1, 3, c_sec)
        canvas.set_pixel("jacket_front", 3, 8, c_trim)
        canvas.set_pixel("jacket_front", 4, 8, c_trim)
        parts_modified.append("jacket_front")

        # Suit sleeves with white cuffs
        for limb, sleeve in (("right_arm", "right_sleeve"), ("left_arm", "left_sleeve")):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{limb}_{f}"
                w = _part_w(canvas, p_name)
                canvas.draw_rect(p_name, 0, 0, w, 9, c_prim)
                canvas.draw_rect(p_name, 0, 9, w, 1, c_trim)
                parts_modified.append(p_name)
            for f in ("front", "back", "left", "right"):
                s_name = f"{sleeve}_{f}"
                canvas.draw_rect(s_name, 0, 7, _part_w(canvas, s_name), 2, c_sec)
                parts_modified.append(s_name)

        # Slacks & dress shoes
        for leg in ("right_leg", "left_leg"):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{leg}_{f}"
                canvas.draw_rect(p_name, 0, 0, 4, 10, c_sec)
                canvas.draw_rect(p_name, 0, 10, 4, 2, c_prim)
                parts_modified.append(p_name)
            canvas.fill_part(f"{leg}_bottom", c_prim)

    elif style == "cozy_sweater":
        # Knit sweater with horizontal accent band, collar, cuffed pants & sneakers
        for part in ("body_front", "body_back", "body_left", "body_right", "body_top", "body_bottom"):
            canvas.fill_part(part, c_prim)
            parts_modified.append(part)

        for face in ("body_front", "body_back", "body_left", "body_right"):
            w = _part_w(canvas, face)
            canvas.draw_rect(face, 0, 3, w, 2, c_acc)
            canvas.draw_rect(face, 0, 10, w, 2, c_sec)

        # Cozy knit collar & hem on Layer 2
        for face in ("jacket_front", "jacket_back", "jacket_left", "jacket_right"):
            w = _part_w(canvas, face)
            canvas.draw_rect(face, 0, 0, w, 2, c_trim)
            canvas.draw_rect(face, 0, 10, w, 2, c_sec)
            parts_modified.append(face)

        for limb, sleeve in (("right_arm", "right_sleeve"), ("left_arm", "left_sleeve")):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{limb}_{f}"
                w = _part_w(canvas, p_name)
                canvas.draw_rect(p_name, 0, 0, w, 9, c_prim)
                canvas.draw_rect(p_name, 0, 3, w, 2, c_acc)
                parts_modified.append(p_name)
            for f in ("front", "back", "left", "right"):
                s_name = f"{sleeve}_{f}"
                canvas.draw_rect(s_name, 0, 7, _part_w(canvas, s_name), 2, c_sec)
                parts_modified.append(s_name)

        for leg, pants in (("right_leg", "right_pants"), ("left_leg", "left_pants")):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{leg}_{f}"
                canvas.draw_rect(p_name, 0, 0, 4, 9, c_sec)
                parts_modified.append(p_name)
            for f in ("front", "back", "left", "right"):
                o_name = f"{pants}_{f}"
                canvas.draw_rect(o_name, 0, 7, 4, 2, c_trim)
                parts_modified.append(o_name)

        draw_sneakers(canvas, limb="right_leg", sole_color=trim_color, body_color=secondary_color, accent_color=accent_color)
        draw_sneakers(canvas, limb="left_leg", sole_color=trim_color, body_color=secondary_color, accent_color=accent_color)

    return {
        "style": style,
        "parts_modified_count": len(set(parts_modified)),
        "colors_used": {
            "primary": primary_color,
            "secondary": secondary_color,
            "accent": accent_color,
            "trim": trim_color,
        },
    }
