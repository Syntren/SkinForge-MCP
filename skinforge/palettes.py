"""
Predefined color palettes and procedural color ramp utilities for SkinForge.
Useful for common styles like Techwear, Cyberpunk, Anime, Casual, and Fantasy.
"""

import numpy as np
from .ascii_codec import normalize_color, rgba_to_hex

# Techwear Cyberpunk (Syntren Theme)
TECHWEAR_CYBERPUNK = {
    ".": [0, 0, 0, 0],              # Transparent
    # Hoodie & Fabric darks
    "_": [14, 12, 18, 255],          # Deep shadow / border
    "#": [20, 16, 24, 255],          # Base dark black/charcoal
    "=": [28, 24, 34, 255],          # Mid dark fabric / fold
    "+": [38, 34, 46, 255],          # Fabric highlight / seam
    "~": [50, 44, 60, 255],          # Pale rim highlight
    # Neon Purples
    "D": [80, 18, 120, 255],         # Deep purple glow shadow
    "P": [160, 55, 225, 255],        # Vivid neon violet (#A037E1)
    "M": [154, 50, 220, 255],        # Neon violet mid
    "B": [210, 100, 255, 255],       # Bright neon violet (#D264FF)
    "L": [245, 185, 255, 255],       # White-violet highlight (#F5B9FF)
    # Hair
    "h": [14, 12, 17, 255],          # Deep hair shadow
    "H": [22, 20, 26, 255],          # Base black hair
    "^": [32, 28, 36, 255],          # Hair highlight strand
    # Face skin
    "s": [224, 177, 180, 255],       # Fair anime skin
    "m": [212, 163, 172, 255],       # Skin midtone
    "d": [189, 144, 158, 255],       # Skin shadow gap
    # Eyes
    "e": [92, 80, 102, 255],         # Eye shadow lash
    "E": [117, 107, 133, 255],       # Eye shadow right
    "i": [95, 41, 135, 255],         # Iris top (deep violet)
    "I": [154, 60, 212, 255],        # Iris bottom (glowing violet)
    "W": [233, 214, 240, 255],       # Eye lavender / white highlight
    # Silver Metallic Chain
    "c": [250, 250, 255, 255],       # Chain specular
    "C": [180, 170, 195, 255],       # Chain light silver
    "k": [130, 120, 145, 255],       # Chain mid silver
    "x": [80, 70, 95, 255],          # Chain dark silver
    # Cargo Pants
    "0": [15, 13, 19, 255],          # Pants deep shadow
    "1": [22, 19, 27, 255],          # Base cargo fabric
    "2": [30, 26, 36, 255],          # Cargo fold
    "3": [42, 38, 50, 255],          # Pocket flap highlight
    # Sneakers
    "u": [154, 50, 220, 255],        # Sneaker purple collar
    "b": [18, 16, 22, 255],          # Sneaker dark body
    "w": [250, 250, 255, 255],       # White sole
    "g": [205, 205, 218, 255],       # Sole shadow
}

# Standard Anime Skin Tones
ANIME_SKIN = {
    "light":   [240, 195, 178, 255],
    "base":    [224, 177, 160, 255],
    "midtone": [210, 160, 142, 255],
    "shadow":  [185, 135, 118, 255],
    "deep":    [155, 110, 95, 255],
}

# Casual Streetwear Palette
CASUAL_STREETWEAR = {
    ".": [0, 0, 0, 0],
    # Denim
    "D": [34, 46, 74, 255],
    "d": [46, 62, 98, 255],
    "b": [62, 84, 132, 255],
    # Cream / White hoodie
    "w": [245, 242, 238, 255],
    "W": [225, 220, 212, 255],
    "g": [190, 184, 175, 255],
    # Leather brown
    "l": [88, 54, 38, 255],
    "L": [118, 74, 52, 255],
    "h": [148, 96, 68, 255],
}

# Fantasy / Knight Steel Palette
FANTASY_KNIGHT = {
    ".": [0, 0, 0, 0],
    # Steel armor
    "s": [48, 52, 60, 255],
    "S": [82, 88, 100, 255],
    "a": [128, 136, 152, 255],
    "A": [180, 188, 204, 255],
    "*": [240, 245, 255, 255],
    # Gold trim
    "o": [140, 95, 20, 255],
    "O": [205, 150, 40, 255],
    "g": [250, 205, 75, 255],
}


def generate_color_ramp(base_color, steps=5):
    """
    Generate a harmonious 5-step shading ramp from a single base color.
    Steps:
      0: deep shadow (60% brightness, cool tinted)
      1: shadow (80% brightness)
      2: base (100% original)
      3: highlight (120% brightness)
      4: rim highlight (140% brightness, slightly warm specular)
    
    Returns a dictionary mapping standard ASCII shading chars ('_', '#', '=', '+', '~')
    to normalized [R, G, B, 255] color values, along with hex representations.
    """
    base_rgba = normalize_color(base_color)
    r, g, b = [float(x) for x in base_rgba[:3]]

    factors = [
        (0.55, -8, -8, 8),    # deep shadow (cooler)
        (0.78, -4, -4, 4),    # shadow
        (1.00,  0,  0, 0),    # base
        (1.22,  6,  6, 2),    # highlight
        (1.42, 14, 14, 8),    # rim specular
    ]
    chars = ["_", "#", "=", "+", "~"]

    ramp_palette = {}
    ramp_details = []

    for i in range(min(steps, len(factors))):
        mult, dr, dg, db = factors[i]
        nr = int(np.clip(r * mult + dr, 0, 255))
        ng = int(np.clip(g * mult + dg, 0, 255))
        nb = int(np.clip(b * mult + db, 0, 255))
        rgba = [nr, ng, nb, 255]
        char = chars[i]
        ramp_palette[char] = rgba
        ramp_details.append({
            "char": char,
            "rgba": rgba,
            "hex": rgba_to_hex(rgba),
            "step": i,
        })

    return {
        "palette": ramp_palette,
        "details": ramp_details,
        "base_hex": rgba_to_hex(base_rgba),
    }
