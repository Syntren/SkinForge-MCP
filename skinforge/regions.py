"""
Semantic Multi-Face Region Painter & 2D Pixel Primitives for SkinForge (v2.0.0).

Eliminates tedious face-by-face repetitive MCP calls by letting AI agents paint entire
anatomical 3D cuboids (head, hat, torso, jacket, arms, sleeves, legs, pants, hair_cap,
shoes, hands) with wrap-around patterns in a single call, and draw crisp 2D primitives
(Bresenham lines, outlines, flood fills, Bayer dither rects, and horizontal face symmetry).
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from .ascii_codec import normalize_color

# Semantic anatomical regions mapped to their constituent UV parts
REGION_PARTS: Dict[str, List[str]] = {
    "head": ["head_top", "head_bottom", "head_front", "head_back", "head_right", "head_left"],
    "hat": ["hat_top", "hat_bottom", "hat_front", "hat_back", "hat_right", "hat_left"],
    "hair_cap": ["head_top", "head_back", "head_right", "head_left"],
    "hat_cap": ["hat_top", "hat_back", "hat_right", "hat_left"],
    "torso": ["body_top", "body_bottom", "body_front", "body_back", "body_right", "body_left"],
    "jacket": ["jacket_top", "jacket_bottom", "jacket_front", "jacket_back", "jacket_right", "jacket_left"],
    "right_arm": ["right_arm_top", "right_arm_bottom", "right_arm_front", "right_arm_back", "right_arm_right", "right_arm_left"],
    "left_arm": ["left_arm_top", "left_arm_bottom", "left_arm_front", "left_arm_back", "left_arm_right", "left_arm_left"],
    "arms": [
        "right_arm_top", "right_arm_bottom", "right_arm_front", "right_arm_back", "right_arm_right", "right_arm_left",
        "left_arm_top", "left_arm_bottom", "left_arm_front", "left_arm_back", "left_arm_right", "left_arm_left",
    ],
    "right_sleeve": ["right_sleeve_top", "right_sleeve_bottom", "right_sleeve_front", "right_sleeve_back", "right_sleeve_right", "right_sleeve_left"],
    "left_sleeve": ["left_sleeve_top", "left_sleeve_bottom", "left_sleeve_front", "left_sleeve_back", "left_sleeve_right", "left_sleeve_left"],
    "sleeves": [
        "right_sleeve_top", "right_sleeve_bottom", "right_sleeve_front", "right_sleeve_back", "right_sleeve_right", "right_sleeve_left",
        "left_sleeve_top", "left_sleeve_bottom", "left_sleeve_front", "left_sleeve_back", "left_sleeve_right", "left_sleeve_left",
    ],
    "right_leg": ["right_leg_top", "right_leg_bottom", "right_leg_front", "right_leg_back", "right_leg_right", "right_leg_left"],
    "left_leg": ["left_leg_top", "left_leg_bottom", "left_leg_front", "left_leg_back", "left_leg_right", "left_leg_left"],
    "legs": [
        "right_leg_top", "right_leg_bottom", "right_leg_front", "right_leg_back", "right_leg_right", "right_leg_left",
        "left_leg_top", "left_leg_bottom", "left_leg_front", "left_leg_back", "left_leg_right", "left_leg_left",
    ],
    "right_pants": ["right_pants_top", "right_pants_bottom", "right_pants_front", "right_pants_back", "right_pants_right", "right_pants_left"],
    "left_pants": ["left_pants_top", "left_pants_bottom", "left_pants_front", "left_pants_back", "left_pants_right", "left_pants_left"],
    "pants": [
        "right_pants_top", "right_pants_bottom", "right_pants_front", "right_pants_back", "right_pants_right", "right_pants_left",
        "left_pants_top", "left_pants_bottom", "left_pants_front", "left_pants_back", "left_pants_right", "left_pants_left",
    ],
}

REGION_PATTERNS = (
    "solid",
    "vertical_gradient",
    "horizontal_stripes",
    "vertical_stripes",
    "checker",
    "cuff",
    "belt",
    "collar",
)

PRIMITIVE_TYPES = (
    "line",
    "outline",
    "flood_fill",
    "dither_rect",
    "mirror_x",
)


def _is_side_face(part_name: str) -> bool:
    return part_name.endswith(("_front", "_back", "_left", "_right"))


def paint_region(
    canvas: Any,
    region: str,
    color: Any,
    secondary_color: Optional[Any] = None,
    pattern: str = "solid",
    row_start: Optional[int] = None,
    row_end: Optional[int] = None,
    include_caps: bool = True,
) -> Dict[str, Any]:
    """
    Paint a semantic multi-face anatomical region in a single atomic operation.
    Supports full-region fills, horizontal wrap-around bands (row_start..row_end),
    and procedural patterns ('solid', 'vertical_gradient', 'horizontal_stripes',
    'vertical_stripes', 'checker', 'cuff', 'belt', 'collar').
    """
    reg_key = region.lower().strip()
    pat = pattern.lower().strip()
    if pat not in REGION_PATTERNS:
        raise ValueError(f"Unknown pattern '{pattern}'. Supported: {list(REGION_PATTERNS)}")

    c1 = np.array(normalize_color(color), dtype=np.uint8)
    c2 = np.array(normalize_color(secondary_color), dtype=np.uint8) if secondary_color is not None else c1

    # Virtual convenience regions for shoes & hands
    if reg_key == "shoes":
        target_parts = REGION_PARTS["legs"]
        row_start = 9 if row_start is None else row_start
        row_end = 12 if row_end is None else row_end
    elif reg_key == "hands":
        target_parts = REGION_PARTS["arms"]
        row_start = 9 if row_start is None else row_start
        row_end = 12 if row_end is None else row_end
    elif reg_key in REGION_PARTS:
        target_parts = REGION_PARTS[reg_key]
    else:
        raise ValueError(
            f"Unknown region '{region}'. Supported regions: {sorted(list(REGION_PARTS.keys()) + ['shoes', 'hands'])}"
        )

    modified_parts: List[str] = []
    pixels_painted = 0

    for part_name in target_parts:
        part = canvas.parts[part_name]
        h, w, _ = part.shape
        is_cap = not _is_side_face(part_name)

        # Handle cap inclusion rules
        if is_cap:
            if not include_caps:
                continue
            if reg_key in ("shoes", "hands") and part_name.endswith("_top"):
                continue
            if pat in ("cuff", "belt", "collar"):
                continue
            if row_start is not None or row_end is not None:
                # Only paint bottom cap for shoes/hands, skip caps for arbitrary row bands
                if reg_key in ("shoes", "hands") and part_name.endswith("_bottom"):
                    part[:, :] = c1
                    modified_parts.append(part_name)
                    pixels_painted += h * w
                continue

        # Determine vertical slice
        y0 = 0 if row_start is None else max(0, min(h, int(row_start)))
        y1 = h if row_end is None else max(0, min(h, int(row_end)))

        if pat == "cuff":
            y0, y1 = max(0, h - 3), max(0, h - 1)
        elif pat == "belt":
            y0, y1 = max(0, h - 2), h
        elif pat == "collar":
            y0, y1 = 0, min(h, 2)

        if y1 <= y0:
            continue

        slice_h = y1 - y0
        if pat in ("solid", "cuff", "belt", "collar"):
            part[y0:y1, :] = c1
            if pat in ("cuff", "belt", "collar") and secondary_color is not None and slice_h >= 2:
                part[y0, :] = c2
        elif pat == "vertical_gradient":
            t = np.linspace(0.0, 1.0, max(1, slice_h), dtype=np.float64)[:, None, None]
            grad = np.clip(np.round(c1.astype(np.float64) * (1.0 - t) + c2.astype(np.float64) * t), 0, 255).astype(np.uint8)
            part[y0:y1, :] = grad
        elif pat == "horizontal_stripes":
            for ry in range(y0, y1):
                part[ry, :] = c1 if ((ry - y0) % 2 == 0) else c2
        elif pat == "vertical_stripes":
            for rx in range(w):
                part[y0:y1, rx] = c1 if (rx % 2 == 0) else c2
        elif pat == "checker":
            yy, xx = np.indices((slice_h, w))
            mask = ((yy + xx) % 2) == 0
            block = np.where(mask[:, :, None], c1, c2)
            part[y0:y1, :] = block

        modified_parts.append(part_name)
        pixels_painted += slice_h * w

    return {
        "region": reg_key,
        "pattern": pat,
        "modified_parts": modified_parts,
        "modified_parts_count": len(modified_parts),
        "pixels_painted": pixels_painted,
    }


def draw_primitive(
    canvas: Any,
    part_name: str,
    primitive: str,
    x0: int = 0,
    y0: int = 0,
    x1: Optional[int] = None,
    y1: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    color: Any = "#ffffff",
    secondary_color: Optional[Any] = None,
    tolerance: int = 12,
    direction: str = "left_to_right",
) -> Dict[str, Any]:
    """
    Draw crisp 2D pixel primitives on a UV face:
      - 'line': Integer Bresenham line from (x0, y0) to (x1, y1).
      - 'outline': 1px border frame at (x0, y0) with (width, height).
      - 'flood_fill': 4-connected bucket fill starting at (x0, y0) within RGB tolerance.
      - 'dither_rect': 2-color checkerboard dithered rectangle at (x0, y0, width, height).
      - 'mirror_x': Horizontal symmetry on a face ('left_to_right' or 'right_to_left').
    """
    if part_name not in canvas.parts:
        raise KeyError(f"Unknown UV part: '{part_name}'")

    prim = primitive.lower().strip()
    if prim not in PRIMITIVE_TYPES:
        raise ValueError(f"Unknown primitive '{primitive}'. Supported: {list(PRIMITIVE_TYPES)}")

    part = canvas.parts[part_name]
    h, w, _ = part.shape
    pixels_changed = 0

    if prim == "mirror_x":
        half = w // 2
        if direction == "right_to_left":
            for x in range(half):
                part[:, x] = part[:, w - 1 - x]
                pixels_changed += h
        else:
            for x in range(half):
                part[:, w - 1 - x] = part[:, x]
                pixels_changed += h
        return {
            "part_name": part_name,
            "primitive": prim,
            "direction": direction,
            "pixels_changed": pixels_changed,
        }

    c1 = np.array(normalize_color(color), dtype=np.uint8)

    if prim == "line":
        tx = w - 1 if x1 is None else int(x1)
        ty = h - 1 if y1 is None else int(y1)
        cx, cy = int(x0), int(y0)
        dx = abs(tx - cx)
        dy = -abs(ty - cy)
        sx = 1 if cx < tx else -1
        sy = 1 if cy < ty else -1
        err = dx + dy
        while True:
            if 0 <= cx < w and 0 <= cy < h:
                part[cy, cx] = c1
                pixels_changed += 1
            if cx == tx and cy == ty:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                cx += sx
            if e2 <= dx:
                err += dx
                cy += sy

    elif prim == "outline":
        rw = (w - int(x0)) if width is None else int(width)
        rh = (h - int(y0)) if height is None else int(height)
        rx0, ry0 = int(x0), int(y0)
        rx1, ry1 = rx0 + rw - 1, ry0 + rh - 1
        for x in range(rx0, rx1 + 1):
            for y in (ry0, ry1):
                if 0 <= x < w and 0 <= y < h:
                    part[y, x] = c1
                    pixels_changed += 1
        for y in range(ry0 + 1, ry1):
            for x in (rx0, rx1):
                if 0 <= x < w and 0 <= y < h:
                    part[y, x] = c1
                    pixels_changed += 1

    elif prim == "dither_rect":
        c2 = np.array(normalize_color(secondary_color), dtype=np.uint8) if secondary_color is not None else np.array([0, 0, 0, 0], dtype=np.uint8)
        rw = (w - int(x0)) if width is None else int(width)
        rh = (h - int(y0)) if height is None else int(height)
        rx0 = max(0, min(w, int(x0)))
        ry0 = max(0, min(h, int(y0)))
        rx1 = max(0, min(w, int(x0) + rw))
        ry1 = max(0, min(h, int(y0) + rh))
        for y in range(ry0, ry1):
            for x in range(rx0, rx1):
                part[y, x] = c1 if ((x + y) % 2 == 0) else c2
                pixels_changed += 1

    elif prim == "flood_fill":
        sx, sy = int(x0), int(y0)
        if not (0 <= sx < w and 0 <= sy < h):
            raise ValueError(f"Seed ({sx}, {sy}) out of bounds for '{part_name}' ({w}x{h})")
        seed_rgba = part[sy, sx].astype(np.int16).copy()
        if np.array_equal(part[sy, sx], c1):
            return {"part_name": part_name, "primitive": prim, "pixels_changed": 0}
        visited = np.zeros((h, w), dtype=bool)
        q: deque[Tuple[int, int]] = deque([(sx, sy)])
        visited[sy, sx] = True
        tol = int(max(0, tolerance))
        while q:
            cx, cy = q.popleft()
            part[cy, cx] = c1
            pixels_changed += 1
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx]:
                    px = part[ny, nx].astype(np.int16)
                    # Match alpha presence + RGB distance
                    alpha_ok = (px[3] == 0 and seed_rgba[3] == 0) or (px[3] > 0 and seed_rgba[3] > 0)
                    if alpha_ok and int(np.max(np.abs(px[:3] - seed_rgba[:3]))) <= tol:
                        visited[ny, nx] = True
                        q.append((nx, ny))

    return {
        "part_name": part_name,
        "primitive": prim,
        "pixels_changed": pixels_changed,
    }
