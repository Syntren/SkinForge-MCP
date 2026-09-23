"""
ASCII Codec for SkinForge.
Provides color normalization (hex/RGB/RGBA) and reverse-engineering of part pixels into ASCII grids and palettes.
"""

import re
import numpy as np


def normalize_color(color):
    """
    Normalize any color input (hex string, list, tuple, numpy array) into a standard [R, G, B, A] uint8 list.
    Supports '#RGB', '#RGBA', '#RRGGBB', '#RRGGBBAA', 'transparent', or (r, g, b, [a]).
    """
    if isinstance(color, str):
        col = color.strip()
        if col.lower() in ("transparent", "none", "."):
            return [0, 0, 0, 0]
        if col.startswith("#"):
            col = col[1:]
            if len(col) == 3:  # #RGB
                r = int(col[0] * 2, 16)
                g = int(col[1] * 2, 16)
                b = int(col[2] * 2, 16)
                return [r, g, b, 255]
            elif len(col) == 4:  # #RGBA
                r = int(col[0] * 2, 16)
                g = int(col[1] * 2, 16)
                b = int(col[2] * 2, 16)
                a = int(col[3] * 2, 16)
                return [r, g, b, a]
            elif len(col) == 6:  # #RRGGBB
                r = int(col[0:2], 16)
                g = int(col[2:4], 16)
                b = int(col[4:6], 16)
                return [r, g, b, 255]
            elif len(col) == 8:  # #RRGGBBAA
                r = int(col[0:2], 16)
                g = int(col[2:4], 16)
                b = int(col[4:6], 16)
                a = int(col[6:8], 16)
                return [r, g, b, a]
            else:
                raise ValueError(f"Invalid hex color format: '{color}'")
        raise ValueError(f"Unrecognized color string: '{color}'")

    if isinstance(color, (list, tuple, np.ndarray)):
        arr = list(color)
        if len(arr) == 3:
            return [int(np.clip(arr[0], 0, 255)), int(np.clip(arr[1], 0, 255)), int(np.clip(arr[2], 0, 255)), 255]
        elif len(arr) >= 4:
            return [int(np.clip(arr[0], 0, 255)), int(np.clip(arr[1], 0, 255)), int(np.clip(arr[2], 0, 255)), int(np.clip(arr[3], 0, 255))]
        else:
            raise ValueError(f"Color sequence must have 3 or 4 elements, got {len(arr)}")

    raise TypeError(f"Unsupported color type: {type(color)}")


def rgba_to_hex(rgba):
    """Convert [R, G, B, A] to hex string. If alpha is 255, returns #RRGGBB, otherwise #RRGGBBAA."""
    r, g, b, a = rgba[:4]
    if a == 255:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"#{r:02x}{g:02x}{b:02x}{a:02x}"


# Standard character pool for ASCII generation
ASCII_CHAR_POOL = [
    "#", "=", "+", "~", "*", "o", "x", "s", "m", "d",
    "h", "H", "^", "i", "I", "w", "W", "b", "B", "p",
    "P", "0", "1", "2", "3", "4", "5", "6", "7", "8",
    "9", "A", "C", "D", "E", "F", "G", "J", "K", "L",
    "M", "N", "O", "Q", "R", "S", "T", "U", "V", "X", "Y", "Z"
]


def part_to_ascii(part_arr, tolerance=6):
    """
    Reverse-engineers an (H, W, 4) numpy array into an ASCII grid string and palette dictionary.
    Groups similar colors within tolerance to create a clean, readable ASCII grid.
    
    Transparent pixels (alpha < 10) are always mapped to '.' -> [0, 0, 0, 0].
    
    Returns:
        (ascii_grid: str, palette: dict[str, list[int]])
    """
    if not isinstance(part_arr, np.ndarray):
        part_arr = np.array(part_arr, dtype=np.uint8)

    h, w, _ = part_arr.shape
    palette = {}
    clusters = []  # list of [representative_rgba, char]

    # Pre-register transparent
    has_transparent = False
    for r in range(h):
        for c in range(w):
            if part_arr[r, c, 3] < 10:
                has_transparent = True
                break
        if has_transparent:
            break

    if has_transparent:
        palette["."] = [0, 0, 0, 0]

    char_idx = 0

    def find_cluster(rgba):
        if rgba[3] < 10:
            return "."
        for rep, char in clusters:
            # Color distance
            dist = np.sqrt(np.sum((np.array(rep[:3], dtype=float) - np.array(rgba[:3], dtype=float)) ** 2))
            alpha_diff = abs(int(rep[3]) - int(rgba[3]))
            if dist <= tolerance and alpha_diff <= tolerance:
                return char
        return None

    # First pass: count color frequencies to assign simpler chars to dominant colors
    color_counts = {}
    for r in range(h):
        for c in range(w):
            rgba = tuple(part_arr[r, c].tolist())
            if rgba[3] < 10:
                continue
            color_counts[rgba] = color_counts.get(rgba, 0) + 1

    sorted_colors = sorted(color_counts.keys(), key=lambda k: color_counts[k], reverse=True)

    for rgba_tuple in sorted_colors:
        rgba = list(rgba_tuple)
        existing_char = find_cluster(rgba)
        if existing_char is None:
            if char_idx < len(ASCII_CHAR_POOL):
                char = ASCII_CHAR_POOL[char_idx]
                char_idx += 1
            else:
                char = chr(ord('a') + (char_idx % 26))
                char_idx += 1
            clusters.append((rgba, char))
            palette[char] = rgba

    # Second pass: construct grid
    lines = []
    for r in range(h):
        line_chars = []
        for c in range(w):
            rgba = part_arr[r, c].tolist()
            if rgba[3] < 10:
                line_chars.append(".")
            else:
                char = find_cluster(rgba)
                if char is None:
                    # Fallback to closest cluster
                    best_char = clusters[0][1] if clusters else "."
                    min_d = 1e9
                    for rep, ch in clusters:
                        d = np.linalg.norm(np.array(rep, dtype=float) - np.array(rgba, dtype=float))
                        if d < min_d:
                            min_d = d
                            best_char = ch
                    char = best_char
                line_chars.append(char)
        lines.append("".join(line_chars))

    grid_str = "\n".join(lines)
    return grid_str, palette


def canvas_to_ascii(canvas_or_path, tolerance=12, max_palette_size=40):
    """
    Reverse-engineers an entire SkinCanvas into a global palette and part-by-part ASCII grids.
    
    Args:
        canvas_or_path: SkinCanvas instance, image file path, or PIL.Image
        tolerance: Color distance threshold for grouping similar colors (default: 12)
        max_palette_size: Maximum number of colors in the global palette
        
    Returns:
        (palette: dict[str, str], parts: dict[str, str])
    """
    if isinstance(canvas_or_path, str):
        from .canvas import SkinCanvas
        canvas = SkinCanvas()
        canvas.load_png(canvas_or_path)
    elif hasattr(canvas_or_path, "parts"):
        canvas = canvas_or_path
    else:
        from .canvas import SkinCanvas
        from PIL import Image
        canvas = SkinCanvas()
        im = canvas_or_path if isinstance(canvas_or_path, Image.Image) else Image.fromarray(canvas_or_path)
        im = im.convert("RGBA")
        arr = np.array(im)
        from .canvas import MINECRAFT_UV_MAP
        for name, (u0, v0, u1, v1) in MINECRAFT_UV_MAP.items():
            canvas.parts[name] = arr[v0:v1, u0:u1].copy()

    all_colors = []
    for name, part in canvas.parts.items():
        h, w, _ = part.shape
        for r in range(h):
            for c in range(w):
                rgba = part[r, c]
                if rgba[3] >= 10:
                    all_colors.append(tuple(rgba.tolist()))

    from collections import Counter
    counts = Counter(all_colors)

    clusters = []
    palette = {".": "transparent"}
    char_idx = 0
    for rgba, count in counts.most_common():
        found = False
        for rep, ch in clusters:
            dist = np.sqrt(np.sum((np.array(rep[:3], dtype=float) - np.array(rgba[:3], dtype=float)) ** 2))
            alpha_diff = abs(int(rep[3]) - int(rgba[3]))
            if dist <= tolerance and alpha_diff <= tolerance:
                found = True
                break
        if not found and char_idx < max_palette_size:
            ch = ASCII_CHAR_POOL[char_idx] if char_idx < len(ASCII_CHAR_POOL) else chr(ord("a") + (char_idx % 26))
            char_idx += 1
            clusters.append((rgba, ch))
            palette[ch] = rgba_to_hex(rgba)

    def get_char(rgba):
        if rgba[3] < 10:
            return "."
        best_ch = "."
        min_dist = 1e9
        for rep, ch in clusters:
            d = np.sqrt(np.sum((np.array(rep[:3], dtype=float) - np.array(rgba[:3], dtype=float)) ** 2))
            if d < min_dist:
                min_dist = d
                best_ch = ch
        return best_ch

    parts_ascii = {}
    for name, part in canvas.parts.items():
        h, w, _ = part.shape
        if np.all(part[:, :, 3] < 10):
            continue
        lines = []
        for r in range(h):
            line = "".join(get_char(part[r, c]) for c in range(w))
            lines.append(line)
        parts_ascii[name] = "\n".join(lines)

    return palette, parts_ascii
