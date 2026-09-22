"""
Pixel Typography and Symbol Rendering Subsystem for SkinForge.
Enables LLMs to render crisp 3x5/4x5 pixel text and cyber symbols/emblems on Minecraft UV parts.
Eliminates coordinate guesswork for back emblems, chest badges, and gamer tags.
"""

from typing import Dict, Any, List
import numpy as np
from .ascii_codec import normalize_color

# 3x5 pixel font bitmap (1 = pixel, 0 = blank)
FONT_3X5: Dict[str, List[str]] = {
    "A": ["010", "101", "111", "101", "101"],
    "B": ["110", "101", "110", "101", "110"],
    "C": ["011", "100", "100", "100", "011"],
    "D": ["110", "101", "101", "101", "110"],
    "E": ["111", "100", "110", "100", "111"],
    "F": ["111", "100", "110", "100", "100"],
    "G": ["011", "100", "101", "101", "011"],
    "H": ["101", "101", "111", "101", "101"],
    "I": ["111", "010", "010", "010", "111"],
    "J": ["001", "001", "001", "101", "010"],
    "K": ["101", "110", "100", "110", "101"],
    "L": ["100", "100", "100", "100", "111"],
    "M": ["101", "111", "101", "101", "101"],
    "N": ["101", "111", "111", "101", "101"],
    "O": ["010", "101", "101", "101", "010"],
    "P": ["110", "101", "110", "100", "100"],
    "Q": ["010", "101", "101", "110", "011"],
    "R": ["110", "101", "110", "110", "101"],
    "S": ["011", "100", "010", "001", "110"],
    "T": ["111", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "010"],
    "V": ["101", "101", "101", "101", "010"],
    "W": ["101", "101", "101", "111", "101"],
    "X": ["101", "101", "010", "101", "101"],
    "Y": ["101", "101", "010", "010", "010"],
    "Z": ["111", "001", "010", "100", "111"],
    "0": ["010", "101", "101", "101", "010"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["110", "001", "010", "100", "111"],
    "3": ["110", "001", "010", "001", "110"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "110", "001", "110"],
    "6": ["011", "100", "110", "101", "010"],
    "7": ["111", "001", "010", "010", "010"],
    "8": ["010", "101", "010", "101", "010"],
    "9": ["010", "101", "011", "001", "110"],
    "-": ["000", "000", "111", "000", "000"],
    "!": ["010", "010", "010", "000", "010"],
    "?": ["110", "001", "010", "000", "010"],
    ":": ["000", "010", "000", "010", "000"],
    ".": ["000", "000", "000", "000", "010"],
    " ": ["000", "000", "000", "000", "000"],
}

# Standard cyber symbols & emblems
SYMBOLS: Dict[str, List[str]] = {
    # 6x8 iconic cyber "S" crest (like on Syntren jacket)
    "cyber_s": [
        ".####.",
        "##..##",
        "##....",
        ".####.",
        "....##",
        "##..##",
        ".####.",
        "......",
    ],
    # 5x5 heart
    "heart": [
        ".#.#.",
        "#####",
        "#####",
        ".###.",
        "..#..",
    ],
    # 5x5 star
    "star": [
        "..#..",
        "#####",
        ".###.",
        "#.#.#",
        ".#.#.",
    ],
    # 3x6 lightning bolt
    "lightning": [
        "..#",
        ".#.",
        "###",
        ".#.",
        "#..",
        "#..",
    ],
    # 5x5 cross
    "cross": [
        "..#..",
        "..#..",
        "#####",
        "..#..",
        "..#..",
    ],
    # 5x5 skull
    "skull": [
        ".###.",
        "#.#.#",
        "#####",
        ".#.#.",
        ".###.",
    ]
}


def draw_text(
    canvas,
    part_name: str,
    text: str,
    x: int = 1,
    y: int = 1,
    color: str = "#ffffff",
    spacing: int = 1
) -> int:
    """
    Render pixel text across a UV part using a crisp 3x5 font.
    Args:
        canvas: SkinCanvas instance.
        part_name: Target UV face.
        text: Uppercase string to write.
        x: Starting column coordinate (0-indexed).
        y: Starting row coordinate (0-indexed).
        color: Hex or RGBA color string.
        spacing: Blank column gap between letters (default 1).
    Returns:
        Total number of pixels drawn.
    """
    if part_name not in canvas.parts:
        raise ValueError(f"Unknown part: '{part_name}'")

    rgba = normalize_color(color)
    part = canvas.parts[part_name]
    h, w, _ = part.shape
    text = text.upper()

    cur_x = x
    pixels_drawn = 0

    for ch in text:
        bitmap = FONT_3X5.get(ch, FONT_3X5[" "])
        for r_idx, row_str in enumerate(bitmap):
            py = y + r_idx
            if 0 <= py < h:
                for c_idx, val in enumerate(row_str):
                    px = cur_x + c_idx
                    if 0 <= px < w and val == "1":
                        part[py, px] = rgba
                        pixels_drawn += 1
        cur_x += len(bitmap[0]) + spacing

    return pixels_drawn


def draw_symbol(
    canvas,
    part_name: str,
    symbol_name: str,
    x: int = 1,
    y: int = 1,
    color: str = "#ffffff"
) -> int:
    """
    Render a pixel symbol/emblem ('cyber_s', 'heart', 'star', 'lightning', 'skull', 'cross').
    Args:
        canvas: SkinCanvas instance.
        part_name: Target face name (e.g. 'jacket_back').
        symbol_name: Name of symbol from library.
        x: Top-left X coordinate.
        y: Top-left Y coordinate.
        color: Hex or RGBA color.
    Returns:
        Count of pixels drawn.
    """
    if part_name not in canvas.parts:
        raise ValueError(f"Unknown part: '{part_name}'")

    sym = SYMBOLS.get(symbol_name.lower())
    if not sym:
        raise ValueError(f"Unknown symbol '{symbol_name}'. Available: {list(SYMBOLS.keys())}")

    rgba = normalize_color(color)
    part = canvas.parts[part_name]
    h, w, _ = part.shape
    pixels_drawn = 0

    for r_idx, row_str in enumerate(sym):
        py = y + r_idx
        if 0 <= py < h:
            for c_idx, val in enumerate(row_str):
                px = x + c_idx
                if 0 <= px < w and val == "#":
                    part[py, px] = rgba
                    pixels_drawn += 1

    return pixels_drawn
