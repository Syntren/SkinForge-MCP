"""
Reusable anatomical and clothing design presets for SkinForge.
Allows rapid modular composition of hoodies, eyes, cargo pants, chains, hair bangs, headphones, and sneakers.
"""

from .ascii_codec import normalize_color


def draw_anime_eyes_2x2(
    canvas,
    left_col=1,
    right_col=5,
    row=5,
    iris_color="#af36f8",
    highlight_color="#b59ddb",
    shadow_color="#7d0bd2",
    shine_color="#faf8fc",
    style="cyber_glow"
):
    """
    Draw 2x2 anime eyes on head_front with vibrant iris and specular highlights.
    Styles:
        'cyber_glow' (recommended): 4-quadrant layout matching reference.jpeg with upper shadow,
                                     lower electric neon iris, upper sclera, and lower specular white shine.
        'classic': Double upper shadow with lower highlight and iris.
    """
    c_iris = normalize_color(iris_color)
    c_hl = normalize_color(highlight_color)
    c_shd = normalize_color(shadow_color)
    c_shine = normalize_color(shine_color)

    if style == "cyber_glow":
        # Left eye: (outer=left_col, inner=left_col+1)
        canvas.set_pixel("head_front", left_col, row, c_hl)          # TL: sclera / lavender
        canvas.set_pixel("head_front", left_col + 1, row, c_shd)      # TR: upper iris shadow
        canvas.set_pixel("head_front", left_col, row + 1, c_shine)   # BL: white specular shine
        canvas.set_pixel("head_front", left_col + 1, row + 1, c_iris) # BR: electric neon iris

        # Right eye: (inner=right_col, outer=right_col+1)
        canvas.set_pixel("head_front", right_col, row, c_shd)         # TL: upper iris shadow
        canvas.set_pixel("head_front", right_col + 1, row, c_hl)      # TR: sclera / lavender
        canvas.set_pixel("head_front", right_col, row + 1, c_iris)    # BL: electric neon iris
        canvas.set_pixel("head_front", right_col + 1, row + 1, c_shine)# BR: white specular shine
    else:
        # Classic style
        canvas.set_pixel("head_front", left_col, row, c_shd)
        canvas.set_pixel("head_front", left_col + 1, row, c_shd)
        canvas.set_pixel("head_front", left_col, row + 1, c_hl)
        canvas.set_pixel("head_front", left_col + 1, row + 1, c_iris)

        canvas.set_pixel("head_front", right_col, row, c_shd)
        canvas.set_pixel("head_front", right_col + 1, row, c_shd)
        canvas.set_pixel("head_front", right_col, row + 1, c_iris)
        canvas.set_pixel("head_front", right_col + 1, row + 1, c_hl)


def draw_hoodie_drawstrings(
    canvas,
    col_left=2,
    col_right=5,
    row_start=1,
    len_left=7,
    len_right=4,
    color_bright="#c355ff",
    color_tip="#501278"
):
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
    canvas,
    part_name="right_pants_right",
    y_start=2,
    flap_color="#26222e",
    pouch_color="#1e1a24",
    buckle_color="#9a32dc"
):
    """Draw a 3D cargo utility pocket flap on outer leg (Layer 2)."""
    c_flap = normalize_color(flap_color)
    c_pouch = normalize_color(pouch_color)
    c_buckle = normalize_color(buckle_color)

    # Flap
    canvas.draw_rect(part_name, 0, y_start, 4, 1, c_flap)
    # Pouch
    canvas.draw_rect(part_name, 0, y_start + 1, 4, 2, c_pouch)
    # Center buckle strap
    canvas.set_pixel(part_name, 1, y_start + 2, c_buckle)
    canvas.set_pixel(part_name, 2, y_start + 2, c_buckle)


def draw_hair_bangs(
    canvas,
    style="cyberpunk",
    hair_color="#1e1824",
    highlight_color="#9a3cd4"
):
    """
    Draw stylish 3D hair bangs on hat_front and head_front.
    Strictly complies with Rule 3: ONLY rows 0..3 are drawn on hat_front! Rows 4..7 remain 100% transparent.
    """
    c_hair = normalize_color(hair_color)
    c_hl = normalize_color(highlight_color)

    # Base bangs on head_front
    canvas.draw_rect("head_front", 0, 0, 8, 2, c_hair)
    canvas.draw_rect("head_front", 1, 2, 2, 1, c_hair)
    canvas.draw_rect("head_front", 5, 2, 2, 1, c_hair)
    canvas.set_pixel("head_front", 3, 1, c_hl)
    canvas.set_pixel("head_front", 4, 1, c_hl)

    # 3D Outer Bangs on hat_front (rows 0..3 only!)
    canvas.draw_rect("hat_front", 0, 0, 8, 1, c_hair)
    canvas.draw_rect("hat_front", 0, 1, 3, 2, c_hair)
    canvas.draw_rect("hat_front", 5, 1, 3, 2, c_hair)
    canvas.set_pixel("hat_front", 1, 3, c_hair)
    canvas.set_pixel("hat_front", 6, 3, c_hair)
    canvas.set_pixel("hat_front", 2, 2, c_hl)
    canvas.set_pixel("hat_front", 5, 2, c_hl)


def draw_sneakers(
    canvas,
    limb="right_leg",
    sole_color="#ffffff",
    body_color="#16141e",
    accent_color="#9a32dc"
):
    """Draw stylish sneakers with colored collar, dark body, and white sole on a leg."""
    c_sole = normalize_color(sole_color)
    c_body = normalize_color(body_color)
    c_accent = normalize_color(accent_color)

    # Sole underside
    canvas.fill_part(f"{limb}_bottom", c_sole)

    for face in ("front", "back", "right", "left"):
        part = f"{limb}_{face}"
        # Sole bottom row (row 11)
        canvas.draw_rect(part, 0, 11, 4, 1, c_sole)
        # Sneaker body (rows 9..10)
        canvas.draw_rect(part, 0, 9, 4, 2, c_body)

    # Accent tongue / collar on front
    canvas.draw_rect(f"{limb}_front", 1, 9, 2, 1, c_accent)


def draw_headphones(
    canvas,
    earcup_color="#9a32dc",
    band_color="#221c2c",
    glow_color="#d264ff"
):
    """Draw 3D gaming/cyberpunk headphones on Layer 2 (hat_top, hat_right, hat_left)."""
    c_ear = normalize_color(earcup_color)
    c_band = normalize_color(band_color)
    c_glow = normalize_color(glow_color)

    # Headband on hat_top (col 3..4 running across)
    canvas.draw_rect("hat_top", 0, 3, 8, 2, c_band)
    canvas.set_pixel("hat_top", 3, 3, c_glow)
    canvas.set_pixel("hat_top", 4, 3, c_glow)

    # Earcups on hat_right and hat_left
    for side in ("hat_right", "hat_left"):
        # Band connection row 0..2
        canvas.draw_rect(side, 3, 0, 2, 3, c_band)
        # Earcup circle (rows 3..6, cols 2..5)
        canvas.draw_rect(side, 2, 3, 4, 4, c_ear)
        canvas.draw_rect(side, 3, 4, 2, 2, c_glow)
