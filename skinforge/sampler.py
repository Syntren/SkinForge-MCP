"""
Reference image sampling and palette extraction subsystem for SkinForge.
Allows LLMs and agents to extract exact pixel colors and dominant palettes from
concept art, screenshots, and reference skins without writing ad-hoc Python scripts.
"""

import os
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image
import numpy as np

from .ascii_codec import rgba_to_hex, normalize_color


def _luminance(rgb: List[int]) -> float:
    """Calculate perceived luminance (Rec. 709)."""
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def sample_image(
    image_path: str,
    x: Optional[float | int] = None,
    y: Optional[float | int] = None,
    region: Optional[List[float | int]] = None,
    num_colors: int = 8
) -> Dict[str, Any]:
    """
    Sample colors from an image file (PNG, JPEG, WebP).
    Args:
        image_path: Path to image on disk.
        x: X coordinate (int pixel or float 0.0-1.0 percentage).
        y: Y coordinate (int pixel or float 0.0-1.0 percentage).
        region: Bounding box [x0, y0, x1, y1] (int pixels or float 0.0-1.0 percentages).
        num_colors: Number of dominant colors to extract if region or full image sampled.
    Returns:
        Structured dictionary with sampled colors, hex strings, luminance, and suggested roles.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at path: {image_path}")

    img = Image.open(image_path).convert("RGBA")
    w, h = img.size

    # Case 1: Single point sample
    if x is not None and y is not None:
        px_x = int(x * w) if isinstance(x, float) and 0.0 <= x <= 1.0 else int(x)
        px_y = int(y * h) if isinstance(y, float) and 0.0 <= y <= 1.0 else int(y)
        px_x = max(0, min(w - 1, px_x))
        px_y = max(0, min(h - 1, px_y))

        rgba = list(img.getpixel((px_x, px_y)))
        rgb = rgba[:3]
        hex_code = rgba_to_hex(rgba)
        lum = _luminance(rgb)

        return {
            "mode": "point",
            "image_size": [w, h],
            "sample_coord": [px_x, px_y],
            "rgba": rgba,
            "rgb": rgb,
            "hex": hex_code,
            "luminance": round(lum, 1),
        }

    # Case 2: Region crop or Full Image
    if region is not None and len(region) == 4:
        r_x0, r_y0, r_x1, r_y1 = region
        bx0 = int(r_x0 * w) if isinstance(r_x0, float) and 0.0 <= r_x0 <= 1.0 else int(r_x0)
        by0 = int(r_y0 * h) if isinstance(r_y0, float) and 0.0 <= r_y0 <= 1.0 else int(r_y0)
        bx1 = int(r_x1 * w) if isinstance(r_x1, float) and 0.0 <= r_x1 <= 1.0 else int(r_x1)
        by1 = int(r_y1 * h) if isinstance(r_y1, float) and 0.0 <= r_y1 <= 1.0 else int(r_y1)

        bx0, bx1 = max(0, min(w, bx0)), max(0, min(w, bx1))
        by0, by1 = max(0, min(h, by0)), max(0, min(h, by1))
        if bx1 <= bx0:
            bx1 = min(w, bx0 + 1)
        if by1 <= by0:
            by1 = min(h, by0 + 1)
        cropped = img.crop((bx0, by0, bx1, by1))
        crop_box = [bx0, by0, bx1, by1]
    else:
        cropped = img
        crop_box = [0, 0, w, h]

    # Convert to RGB array for dominant color extraction
    crop_rgb = cropped.convert("RGB")
    crop_small = crop_rgb.resize((min(128, cropped.width), min(128, cropped.height)), Image.Resampling.BOX)

    # Quantize using median-cut
    quantized = crop_small.quantize(colors=max(2, min(32, num_colors)), method=Image.Quantize.MEDIANCUT)
    palette_data = quantized.getpalette()[:num_colors * 3]
    color_counts = quantized.getcolors()

    sorted_colors = []
    if color_counts:
        color_counts.sort(key=lambda x: x[0], reverse=True)
        total_px = sum(c[0] for c in color_counts)
        for count, idx in color_counts[:num_colors]:
            r = palette_data[idx * 3]
            g = palette_data[idx * 3 + 1]
            b = palette_data[idx * 3 + 2]
            sorted_colors.append(([r, g, b], count / total_px))
    else:
        for i in range(min(num_colors, len(palette_data) // 3)):
            r = palette_data[i * 3]
            g = palette_data[i * 3 + 1]
            b = palette_data[i * 3 + 2]
            sorted_colors.append(([r, g, b], 1.0 / num_colors))

    ascii_chars = ["#", "=", "+", "*", "o", "x", "~", "^", "I", "W", "s", "d", "m", "B", "H"]
    palette_dict: Dict[str, str] = {}
    dominant_list = []

    for i, (rgb, pct) in enumerate(sorted_colors):
        hex_code = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        lum = _luminance(rgb)
        
        max_c = max(rgb)
        min_c = min(rgb)
        sat = (max_c - min_c) / max(1, max_c)

        if lum > 220:
            role = "specular_shine"
        elif lum > 170:
            role = "highlight" if sat > 0.3 else "skin_or_light"
        elif sat > 0.4:
            role = "vibrant_accent"
        elif lum < 50:
            role = "deep_shadow"
        else:
            role = "midtone"

        char = ascii_chars[i % len(ascii_chars)]
        palette_dict[char] = hex_code

        dominant_list.append({
            "char": char,
            "hex": hex_code,
            "rgb": rgb,
            "percentage": round(pct * 100, 1),
            "luminance": round(lum, 1),
            "suggested_role": role
        })

    return {
        "mode": "palette",
        "image_size": [w, h],
        "crop_box": crop_box,
        "colors": dominant_list,
        "ascii_palette": palette_dict
    }
