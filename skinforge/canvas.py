"""
Canvas subsystem for SkinForge.
Provides high-level part manipulation, ASCII DSL, procedural texturing, and 64x64 PNG handling.
"""

import os
import numpy as np
from PIL import Image
from .ascii_codec import normalize_color

MINECRAFT_UV_MAP = {
    # Head Base (Layer 1)
    "head_top":    (8, 0, 16, 8),
    "head_bottom": (16, 0, 24, 8),
    "head_right":  (0, 8, 8, 16),
    "head_front":  (8, 8, 16, 16),
    "head_left":   (16, 8, 24, 16),
    "head_back":   (24, 8, 32, 16),
    # Torso Base (Layer 1)
    "body_top":    (20, 16, 28, 20),
    "body_bottom": (28, 16, 36, 20),
    "body_right":  (16, 20, 20, 32),
    "body_front":  (20, 20, 28, 32),
    "body_left":   (28, 20, 32, 32),
    "body_back":   (32, 20, 40, 32),
    # Right Arm Base (Layer 1)
    "right_arm_top":    (44, 16, 48, 20),
    "right_arm_bottom": (48, 16, 52, 20),
    "right_arm_right":  (40, 20, 44, 32),
    "right_arm_front":  (44, 20, 48, 32),
    "right_arm_left":   (48, 20, 52, 32),
    "right_arm_back":   (52, 20, 56, 32),
    # Left Arm Base (Layer 1)
    "left_arm_top":    (36, 48, 40, 52),
    "left_arm_bottom": (40, 48, 44, 52),
    "left_arm_right":  (32, 52, 36, 64),
    "left_arm_front":  (36, 52, 40, 64),
    "left_arm_left":   (40, 52, 44, 64),
    "left_arm_back":   (44, 52, 48, 64),
    # Right Leg Base (Layer 1)
    "right_leg_top":    (4, 16, 8, 20),
    "right_leg_bottom": (8, 16, 12, 20),
    "right_leg_right":  (0, 20, 4, 32),
    "right_leg_front":  (4, 20, 8, 32),
    "right_leg_left":   (8, 20, 12, 32),
    "right_leg_back":   (12, 20, 16, 32),
    # Left Leg Base (Layer 1)
    "left_leg_top":    (20, 48, 24, 52),
    "left_leg_bottom": (24, 48, 28, 52),
    "left_leg_right":  (16, 52, 20, 64),
    "left_leg_front":  (20, 52, 24, 64),
    "left_leg_left":   (24, 52, 28, 64),
    "left_leg_back":   (28, 52, 32, 64),

    # Hat Outer (Layer 2)
    "hat_top":    (40, 0, 48, 8),
    "hat_bottom": (48, 0, 56, 8),
    "hat_right":  (32, 8, 40, 16),
    "hat_front":  (40, 8, 48, 16),
    "hat_left":   (48, 8, 56, 16),
    "hat_back":   (56, 8, 64, 16),
    # Jacket Outer (Layer 2)
    "jacket_top":    (20, 32, 28, 36),
    "jacket_bottom": (28, 32, 36, 36),
    "jacket_right":  (16, 36, 20, 48),
    "jacket_front":  (20, 36, 28, 48),
    "jacket_left":   (28, 36, 32, 48),
    "jacket_back":   (32, 36, 40, 48),
    # Right Sleeve Outer (Layer 2)
    "right_sleeve_top":    (44, 32, 48, 36),
    "right_sleeve_bottom": (48, 32, 52, 36),
    "right_sleeve_right":  (40, 36, 44, 48),
    "right_sleeve_front":  (44, 36, 48, 48),
    "right_sleeve_left":   (48, 36, 52, 48),
    "right_sleeve_back":   (52, 36, 56, 48),
    # Left Sleeve Outer (Layer 2)
    "left_sleeve_top":    (52, 48, 56, 52),
    "left_sleeve_bottom": (56, 48, 60, 52),
    "left_sleeve_right":  (48, 52, 52, 64),
    "left_sleeve_front":  (52, 52, 56, 64),
    "left_sleeve_left":   (56, 52, 60, 64),
    "left_sleeve_back":   (60, 52, 64, 64),
    # Right Pants Outer (Layer 2)
    "right_pants_top":    (4, 32, 8, 36),
    "right_pants_bottom": (8, 32, 12, 36),
    "right_pants_right":  (0, 36, 4, 48),
    "right_pants_front":  (4, 36, 8, 48),
    "right_pants_left":   (8, 36, 12, 48),
    "right_pants_back":   (12, 36, 16, 48),
    # Left Pants Outer (Layer 2)
    "left_pants_top":    (4, 48, 8, 52),
    "left_pants_bottom": (8, 48, 12, 52),
    "left_pants_right":  (0, 52, 4, 64),
    "left_pants_front":  (4, 52, 8, 64),
    "left_pants_left":   (8, 52, 12, 64),
    "left_pants_back":   (12, 52, 16, 64),
}


class SkinCanvas:
    """Convenient, layer-aware authoring canvas for 64x64 Minecraft skins."""
    def __init__(self):
        self.parts = {}
        for name, (u0, v0, u1, v1) in MINECRAFT_UV_MAP.items():
            w = u1 - u0
            h = v1 - v0
            self.parts[name] = np.zeros((h, w, 4), dtype=np.uint8)
        self.model = "default"
        self.history = []
        self.future = []
        self.checkpoints = {}

    def load_png(self, path):
        """Load an existing 64x64 skin PNG into parts."""
        im = Image.open(path).convert("RGBA")
        if im.size != (64, 64):
            raise ValueError(f"Skin image must be 64x64, got {im.size}")
        arr = np.array(im)
        for name, (u0, v0, u1, v1) in MINECRAFT_UV_MAP.items():
            self.parts[name] = arr[v0:v1, u0:u1].copy()

    def export_png(self, path):
        """Export all parts into a clean 64x64 RGBA PNG."""
        arr = np.zeros((64, 64, 4), dtype=np.uint8)
        for name, (u0, v0, u1, v1) in MINECRAFT_UV_MAP.items():
            arr[v0:v1, u0:u1] = self.parts[name]
        im = Image.fromarray(arr)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        im.save(path)
        return path

    def get_part(self, name):
        """Get copy of a part's (H, W, 4) numpy array."""
        return self.parts[name].copy()

    def set_part(self, name, array):
        """Set a part directly using a numpy array or nested lists."""
        arr = np.array(array, dtype=np.uint8)
        expected = self.parts[name].shape
        if arr.shape != expected:
            raise ValueError(f"Part '{name}' expects shape {expected}, got {arr.shape}")
        self.parts[name] = arr

    def fill_part(self, name, rgba):
        """Fill an entire part with a single color (hex or RGBA)."""
        self.parts[name][:] = normalize_color(rgba)

    def set_pixel(self, name, x, y, rgba):
        """Set an individual pixel on a part (hex or RGBA)."""
        self.parts[name][y, x] = normalize_color(rgba)

    def get_pixel(self, name, x, y):
        """Get color of an individual pixel."""
        return self.parts[name][y, x].tolist()

    def draw_rect(self, name, x0, y0, w, h, rgba):
        """Fill a rectangle on a part (hex or RGBA)."""
        self.parts[name][y0:y0+h, x0:x0+w] = normalize_color(rgba)

    def set_ascii(self, name, ascii_str, palette):
        """
        Draw a part using an intuitive multiline ASCII grid.
        Leading/trailing whitespace is stripped; characters map to palette entries.
        Automatically scales between 8-row and 12-row/4-row formats when needed.
        Supports palette as a dict or named palette string (e.g. 'TECHWEAR_CYBERPUNK').
        Palette color values can be hex strings or [R, G, B, A] lists.
        """
        if isinstance(palette, str):
            from .palettes import TECHWEAR_CYBERPUNK, ANIME_SKIN
            p_upper = palette.strip().upper()
            if p_upper in ("TECHWEAR", "CYBERPUNK", "TECHWEAR_CYBERPUNK"):
                palette = TECHWEAR_CYBERPUNK
            elif p_upper in ("ANIME", "ANIME_SKIN"):
                palette = ANIME_SKIN
            else:
                raise ValueError(f"Unknown named palette: '{palette}'. Use a palette dict or 'TECHWEAR_CYBERPUNK'.")

        # Normalize palette colors
        norm_palette = {}
        for k, v in palette.items():
            norm_palette[k] = normalize_color(v)

        lines = [line.strip() for line in ascii_str.strip().split("\n") if line.strip()]
        if not lines:
            return
        h, w, _ = self.parts[name].shape
        src_h = len(lines)
        first_line = list(lines[0].replace(" ", ""))
        src_w = len(first_line)

        # Parse ASCII into intermediate array
        parsed = np.zeros((src_h, src_w, 4), dtype=np.uint8)
        for r, line in enumerate(lines):
            chars = list(line.replace(" ", ""))
            if len(chars) != src_w:
                raise ValueError(f"Part '{name}' row {r} expects {src_w} cols, got {len(chars)}: '{line}'")
            for c, ch in enumerate(chars):
                if ch not in norm_palette:
                    raise KeyError(f"Char '{ch}' not in palette")
                parsed[r, c] = norm_palette[ch]

        # Map into target part dimensions (h, w)
        for dy in range(h):
            for dx in range(w):
                src_x = min(src_w - 1, dx * src_w // w)
                src_y = min(src_h - 1, dy * src_h // h)
                self.parts[name][dy, dx] = parsed[src_y, src_x]

    def apply_ascii_skin(self, palette: dict, parts: dict):
        """
        Apply a full skin defined by a global palette and part ASCII grids.
        Any omitted parts remain transparent/empty.
        """
        for name in self.parts:
            if name in parts:
                self.set_ascii(name, parts[name], palette)
            else:
                self.parts[name][:] = 0


    def apply_gradient(self, name, start_color, end_color, direction="vertical"):
        """
        Apply a smooth linear gradient across a part.
        direction: 'vertical' (top to bottom) or 'horizontal' (left to right).
        """
        c0 = np.array(normalize_color(start_color), dtype=float)
        c1 = np.array(normalize_color(end_color), dtype=float)
        h, w, _ = self.parts[name].shape

        if direction == "vertical":
            for y in range(h):
                t = y / max(1, h - 1)
                col = np.round(c0 * (1.0 - t) + c1 * t).astype(np.uint8)
                self.parts[name][y, :] = col
        else:
            for x in range(w):
                t = x / max(1, w - 1)
                col = np.round(c0 * (1.0 - t) + c1 * t).astype(np.uint8)
                self.parts[name][:, x] = col

    def add_noise(self, name, amount=6):
        """Add subtle microtexture / noise to fabric to avoid flat solid look."""
        part = self.parts[name]
        h, w, _ = part.shape
        noise = np.random.randint(-amount, amount + 1, (h, w, 3))
        rgb = part[:, :, :3].astype(np.int16) + noise
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        mask = part[:, :, 3] > 0
        part[:, :, :3] = np.where(mask[:, :, None], rgb, part[:, :, :3])

    def copy_part(self, src_name, dst_name, flip_h=False):
        """Copy pixels from one part to another, with optional horizontal flip."""
        src = self.parts[src_name].copy()
        if flip_h:
            src = np.fliplr(src)
        self.parts[dst_name] = src

    def mirror_limb(self, src_limb="right_arm", dst_limb="left_arm", mirror_layer2=True):
        """
        Mirror an entire limb (arm or leg) to the other side.
        Correctly swaps inner and outer faces (right <-> left) and flips front/back.
        """
        faces = [
            ("top", "top", True),
            ("bottom", "bottom", True),
            ("front", "front", True),
            ("back", "back", True),
            ("right", "left", True),
            ("left", "right", True),
        ]
        for src_f, dst_f, flip in faces:
            src_part = f"{src_limb}_{src_f}"
            dst_part = f"{dst_limb}_{dst_f}"
            if src_part in self.parts and dst_part in self.parts:
                self.copy_part(src_part, dst_part, flip_h=flip)

        if mirror_layer2:
            l2_src = src_limb.replace("arm", "sleeve").replace("leg", "pants")
            l2_dst = dst_limb.replace("arm", "sleeve").replace("leg", "pants")
            for src_f, dst_f, flip in faces:
                src_part = f"{l2_src}_{src_f}"
                dst_part = f"{l2_dst}_{dst_f}"
                if src_part in self.parts and dst_part in self.parts:
                    self.copy_part(src_part, dst_part, flip_h=flip)

    def heal_layer1_holes(self, default_color=None):
        """
        Scan all 36 Base Layer parts (Layer 1) and make all pixels 100% opaque.
        If a pixel has alpha < 255, patches it using nearest non-transparent neighbor or default_color.
        Guarantees Rule 1 compliance (no transparent holes on base layer).
        Returns number of healed pixels.
        """
        base_parts = [k for k in MINECRAFT_UV_MAP.keys() if not any(x in k for x in ['hat', 'jacket', 'sleeve', 'pants'])]
        fallback = normalize_color(default_color) if default_color else [224, 177, 180, 255]
        healed_count = 0

        for name in base_parts:
            part = self.parts[name]
            h, w, _ = part.shape
            for y in range(h):
                for x in range(w):
                    if part[y, x, 3] < 255:
                        healed_count += 1
                        # Try to find neighbor color
                        found_color = None
                        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)):
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < h and 0 <= nx < w and part[ny, nx, 3] == 255:
                                found_color = part[ny, nx].copy()
                                break
                        if found_color is not None:
                            part[y, x] = found_color
                        else:
                            part[y, x] = fallback
        return healed_count

    def sanitize_outer_layer(self):
        """
        Enforce Rule 3 and Rule 4 on Layer 2 to prevent floating profile artifacts:
        1. On hat_front, clears rows 5 to 7 across all columns (must be transparent below brow to avoid cardboard cheek bug).
        2. On hat_top, if pixel count is isolated/sparse (< 20 pixels), clears it to transparent.
        Returns count of pixels cleared.
        """
        cleared_count = 0
        if "hat_front" in self.parts:
            hat_f = self.parts["hat_front"]
            # Rows 5..7 must be transparent
            for r in range(5, hat_f.shape[0]):
                mask = hat_f[r, :, 3] > 0
                cleared_count += int(np.sum(mask))
                hat_f[r, mask] = [0, 0, 0, 0]

        if "hat_top" in self.parts:
            hat_t = self.parts["hat_top"]
            t_alpha = hat_t[:, :, 3] > 0
            if 0 < np.sum(t_alpha) < 20:
                cleared_count += int(np.sum(t_alpha))
                hat_t[t_alpha] = [0, 0, 0, 0]

        return cleared_count

    def clear_layer(self, layer="outer", parts=None):
        """
        Clear an entire layer ('outer' or 'base') or specific parts to transparent [0, 0, 0, 0].
        """
        outer_names = {'hat', 'jacket', 'sleeve', 'pants'}
        target_parts = []
        if parts:
            target_parts = parts
        elif layer == "outer":
            target_parts = [k for k in self.parts.keys() if any(x in k for x in outer_names)]
        elif layer == "base":
            target_parts = [k for k in self.parts.keys() if not any(x in k for x in outer_names)]

        count = 0
        for name in target_parts:
            if name in self.parts:
                self.parts[name][:] = [0, 0, 0, 0]
                count += 1
        return count

    def replace_color(self, old_color, new_color, part_name=None, tolerance=15, layer="both"):
        """
        Replace occurrences of old_color with new_color within RGB tolerance threshold.
        Args:
            old_color: Hex string or RGBA list to match.
            new_color: Hex string or RGBA list to write.
            part_name: Optional target face (e.g. 'head_front') or None/'all' for whole canvas.
            tolerance: Euclidean RGB distance threshold (default 15, 0 for exact match).
            layer: 'both', 'base', or 'outer'.
        Returns:
            Tuple of (total_pixels_replaced, list_of_affected_parts).
        """
        target_rgba = normalize_color(old_color)
        target_rgb = np.array(target_rgba[:3], dtype=float)
        replace_rgba = normalize_color(new_color)

        outer_names = {'hat', 'jacket', 'sleeve', 'pants'}
        if part_name and part_name not in ("all", "*"):
            target_parts = [part_name] if part_name in self.parts else []
        elif layer == "base":
            target_parts = [k for k in self.parts.keys() if not any(x in k for x in outer_names)]
        elif layer == "outer":
            target_parts = [k for k in self.parts.keys() if any(x in k for x in outer_names)]
        else:
            target_parts = list(self.parts.keys())

        total_replaced = 0
        affected_parts = []

        for name in target_parts:
            part = self.parts[name]
            # Match alpha condition: if old_color is transparent, match transparent
            if target_rgba[3] == 0:
                mask = part[:, :, 3] == 0
            else:
                rgb = part[:, :, :3].astype(float)
                dist = np.sqrt(np.sum((rgb - target_rgb)**2, axis=2))
                mask = (dist <= tolerance) & (part[:, :, 3] > 0)

            replaced_in_part = int(np.sum(mask))
            if replaced_in_part > 0:
                part[mask] = replace_rgba
                total_replaced += replaced_in_part
                affected_parts.append(name)

        return total_replaced, affected_parts

    def set_pixels(self, part_name, pixel_list):
        """
        Efficiently set multiple individual pixels on a part without sending full ASCII grid.
        Args:
            part_name: Target part name (e.g. 'head_front').
            pixel_list: List of dicts [{'x': int, 'y': int, 'color': str|list}, ...] or tuples [(x, y, color), ...].
        Returns:
            Number of pixels updated.
        """
        if part_name not in self.parts:
            raise ValueError(f"Unknown part: '{part_name}'")

        part = self.parts[part_name]
        h, w, _ = part.shape
        count = 0

        for item in pixel_list:
            if isinstance(item, dict):
                x, y, col = item.get("x"), item.get("y"), item.get("color")
            elif isinstance(item, (list, tuple)) and len(item) == 3:
                x, y, col = item[0], item[1], item[2]
            else:
                continue

            if x is not None and y is not None and 0 <= x < w and 0 <= y < h:
                rgba = normalize_color(col)
                part[y, x] = rgba
                count += 1

        return count

    def list_colors(self, part_name=None, top_n=16):
        """
        Inspect unique colors and frequency on a part or the entire skin canvas.
        Returns sorted list of [{'hex': str, 'rgb': [r, g, b], 'alpha': int, 'count': int, 'percentage': float}].
        """
        from .ascii_codec import rgba_to_hex

        if part_name and part_name in self.parts:
            pixels = self.parts[part_name].reshape(-1, 4)
        else:
            pixels = np.vstack([p.reshape(-1, 4) for p in self.parts.values()])

        unique_colors, counts = np.unique(pixels, axis=0, return_counts=True)
        total_pixels = len(pixels)

        # Sort descending by count
        sorted_indices = np.argsort(-counts)
        results = []

        for idx in sorted_indices[:top_n]:
            rgba = unique_colors[idx].tolist()
            cnt = int(counts[idx])
            results.append({
                "hex": rgba_to_hex(rgba),
                "rgb": rgba[:3],
                "alpha": rgba[3],
                "count": cnt,
                "percentage": round((cnt / max(1, total_pixels)) * 100, 2)
            })

        return results

    def diff(self, other, part_name=None):
        """
        Compare active canvas against another SkinCanvas or a skin PNG file.
        Returns structured comparison report of differing parts and pixel coordinates.
        """
        if isinstance(other, str):
            other_canvas = SkinCanvas()
            other_canvas.load_png(other)
        elif isinstance(other, SkinCanvas):
            other_canvas = other
        else:
            raise TypeError("other must be a SkinCanvas instance or a file path string.")

        target_parts = [part_name] if part_name and part_name in self.parts else list(MINECRAFT_UV_MAP.keys())
        total_diff_pixels = 0
        differing_parts = []
        identical_parts = []

        for name in target_parts:
            p1 = self.parts[name]
            p2 = other_canvas.parts[name]
            diff_mask = np.any(p1 != p2, axis=2)
            diff_count = int(np.sum(diff_mask))

            if diff_count > 0:
                total_diff_pixels += diff_count
                diff_coords = []
                ys, xs = np.where(diff_mask)
                for y, x in zip(ys[:16], xs[:16]):  # Cap at 16 coords to preserve tokens
                    diff_coords.append({"x": int(x), "y": int(y)})
                differing_parts.append({
                    "part_name": name,
                    "diff_pixels": diff_count,
                    "sample_coords": diff_coords
                })
            else:
                identical_parts.append(name)

        return {
            "status": "identical" if total_diff_pixels == 0 else "different",
            "total_diff_pixels": total_diff_pixels,
            "differing_parts_count": len(differing_parts),
            "identical_parts_count": len(identical_parts),
            "differing_parts": differing_parts
        }

    # ==========================================
    # HISTORY & CHECKPOINTS (UNDO / REDO)
    # ==========================================

    def _snapshot(self):
        """Deep copy of all parts for undo/checkpointing."""
        return {k: v.copy() for k, v in self.parts.items()}

    def push_undo(self):
        """Record current state to undo history before an edit."""
        self.history.append(self._snapshot())
        if len(self.history) > 30:
            self.history.pop(0)
        self.future.clear()

    def undo(self):
        """Revert to previous canvas state. Returns True if undone."""
        if not self.history:
            return False
        self.future.append(self._snapshot())
        self.parts = self.history.pop()
        return True

    def redo(self):
        """Reapply previously undone state. Returns True if redone."""
        if not self.future:
            return False
        self.history.append(self._snapshot())
        self.parts = self.future.pop()
        return True

    def create_checkpoint(self, name):
        """Save a named milestone state for instant restoration."""
        self.checkpoints[name] = self._snapshot()
        return len(self.checkpoints)

    def restore_checkpoint(self, name):
        """Restore canvas to a named checkpoint."""
        if name not in self.checkpoints:
            return False
        self.push_undo()
        self.parts = {k: v.copy() for k, v in self.checkpoints[name].items()}
        return True

    # ==========================================
    # VECTORIZED HSL / HSV MANIPULATIONS
    # ==========================================

    def adjust_hsv(
        self,
        part_name=None,
        hue_shift=0.0,
        sat_mult=1.0,
        val_mult=1.0,
        target_color=None,
        tolerance=30,
        layer="both"
    ):
        """
        Vectorized Hue, Saturation, and Brightness adjustment across part(s) or entire skin.
        Args:
            part_name: Optional target face or None/'all' for whole skin.
            hue_shift: Shift in degrees (-180..+180 or 0..360). E.g. +120 shifts purple -> green/cyan.
            sat_mult: Multiplier for saturation (0.0 = grayscale, >1.0 = more vibrant).
            val_mult: Multiplier for brightness (0.8 = 20% darker, 1.2 = 20% brighter).
            target_color: Optional hex/RGBA color string to filter only matching colors.
            tolerance: Euclidean RGB distance threshold for target_color filter.
            layer: 'both', 'base', or 'outer'.
        Returns:
            Tuple of (pixels_adjusted, list_of_parts).
        """
        outer_names = {'hat', 'jacket', 'sleeve', 'pants'}
        if part_name and part_name not in ("all", "*"):
            target_parts = [part_name] if part_name in self.parts else []
        elif layer == "base":
            target_parts = [k for k in self.parts.keys() if not any(x in k for x in outer_names)]
        elif layer == "outer":
            target_parts = [k for k in self.parts.keys() if any(x in k for x in outer_names)]
        else:
            target_parts = list(self.parts.keys())

        target_rgb = None
        if target_color:
            target_rgb = np.array(normalize_color(target_color)[:3], dtype=float)

        total_adjusted = 0
        affected_parts = []
        norm_hue_shift = (hue_shift % 360.0) / 360.0

        for name in target_parts:
            part = self.parts[name]
            alpha_mask = part[:, :, 3] > 0
            if not np.any(alpha_mask):
                continue

            if target_rgb is not None:
                rgb_f = part[:, :, :3].astype(float)
                dist = np.sqrt(np.sum((rgb_f - target_rgb)**2, axis=2))
                mask = alpha_mask & (dist <= tolerance)
            else:
                mask = alpha_mask

            if not np.any(mask):
                continue

            # Vectorized RGB -> HSV
            rgb_pixels = part[mask, :3].astype(float) / 255.0
            r, g, b = rgb_pixels[:, 0], rgb_pixels[:, 1], rgb_pixels[:, 2]
            maxc = np.maximum(np.maximum(r, g), b)
            minc = np.minimum(np.minimum(r, g), b)
            v = maxc
            deltac = maxc - minc
            s = np.where(maxc != 0, deltac / maxc, 0.0)

            rc = np.where(deltac != 0, (maxc - r) / deltac, 0.0)
            gc = np.where(deltac != 0, (maxc - g) / deltac, 0.0)
            bc = np.where(deltac != 0, (maxc - b) / deltac, 0.0)

            h = np.zeros_like(r)
            mask_r = (r == maxc) & (deltac != 0)
            mask_g = (g == maxc) & (deltac != 0)
            mask_b = (b == maxc) & (deltac != 0)

            h = np.where(mask_r, bc - gc, h)
            h = np.where(mask_g, 2.0 + rc - bc, h)
            h = np.where(mask_b, 4.0 + gc - rc, h)
            h = (h / 6.0) % 1.0

            # Apply shifts
            h = (h + norm_hue_shift) % 1.0
            s = np.clip(s * sat_mult, 0.0, 1.0)
            v = np.clip(v * val_mult, 0.0, 1.0)

            # Vectorized HSV -> RGB
            i = (h * 6.0).astype(int)
            f = (h * 6.0) - i
            p = v * (1.0 - s)
            q = v * (1.0 - s * f)
            t = v * (1.0 - s * (1.0 - f))
            i = i % 6

            out_r = np.choose(i, [v, q, p, p, t, v])
            out_g = np.choose(i, [t, v, v, q, p, p])
            out_b = np.choose(i, [p, p, t, v, v, q])

            out_rgb = np.clip(np.column_stack([out_r, out_g, out_b]) * 255.0, 0, 255).astype(np.uint8)
            part[mask, :3] = out_rgb

            count = int(np.sum(mask))
            total_adjusted += count
            affected_parts.append(name)

        return total_adjusted, affected_parts



