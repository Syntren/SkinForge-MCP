"""
Refactored Canvas Subsystem for SkinForge (v1.3.0).

Provides thread-safe, layer-aware authoring for 64x64 Minecraft skins with automatic
64x32 legacy conversion, vectorized color operations, atomic PNG I/O, and 30-state undo/redo stacks.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from PIL import Image

from ..ascii_codec import normalize_color, rgba_to_hex
from ..color.spaces import adjust_rgba_hsv, adjust_rgba_hsl, extract_opaque_mask
from .uv import (
    ALL_PARTS,
    BASE_PARTS,
    BASE_TO_OUTER_MAP,
    MINECRAFT_UV_MAP,
    MINECRAFT_UV_MAP_CLASSIC,
    MINECRAFT_UV_MAP_SLIM,
    MINECRAFT_UV_MAP_STEVE,
    OUTER_PARTS,
    OUTER_TO_BASE_MAP,
    UVBox,
    detect_skin_model_from_array,
    get_uv_map,
    is_base_part,
    is_outer_part,
    is_slim_model,
    load_skin_array,
    normalize_model_name,
)

MAX_HISTORY_STATES: int = 30


def atomic_save_png(image_or_arr: Union[Image.Image, np.ndarray], path: str) -> str:
    """
    Atomically write a PIL Image or RGBA numpy array to disk as PNG
    using a temporary file (.tmp) + os.replace() to prevent partial/corrupted reads.
    """
    target = os.path.abspath(os.path.expanduser(str(path)))
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)

    if isinstance(image_or_arr, Image.Image):
        im = image_or_arr.convert("RGBA")
    else:
        arr = np.clip(np.asarray(image_or_arr), 0, 255).astype(np.uint8)
        im = Image.fromarray(arr, mode="RGBA")

    tmp_path = f"{target}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        im.save(tmp_path, format="PNG")
        os.replace(tmp_path, target)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    return target


class CanvasSnapshot(dict):
    """
    Dictionary mapping part_name -> RGBA ndarray copy, enriched with history metadata
    (action label, timestamp, model) for undo/redo stack inspection.
    """
    def __init__(self, parts_dict: Dict[str, np.ndarray], action: str = "edit", model: str = "default", timestamp: Optional[float] = None):
        super().__init__({k: v.copy() for k, v in parts_dict.items()})
        self.action: str = action
        self.model: str = model
        self.timestamp: float = timestamp if timestamp is not None else time.time()

    def copy_parts(self) -> Dict[str, np.ndarray]:
        return {k: v.copy() for k, v in self.items()}


class SkinCanvas:
    """Layer-aware authoring canvas for 64x64 Minecraft skins with 30-step undo/redo history."""

    def __init__(self, model: str = "default"):
        self.model: str = "slim" if is_slim_model(model) else "default"
        self.parts: Dict[str, np.ndarray] = {}
        self.was_converted_from_legacy: bool = False
        uv_map = self.get_uv_map()
        for name, (u0, v0, u1, v1) in uv_map.items():
            w = u1 - u0
            h = v1 - v0
            self.parts[name] = np.zeros((h, w, 4), dtype=np.uint8)
        self.undo_stack: List[CanvasSnapshot] = []
        self.redo_stack: List[CanvasSnapshot] = []
        self.checkpoints: Dict[str, CanvasSnapshot] = {}

    @property
    def history(self) -> List[CanvasSnapshot]:
        """Backward-compatible alias for undo_stack."""
        return self.undo_stack

    @history.setter
    def history(self, value: List[CanvasSnapshot]) -> None:
        self.undo_stack = value

    @property
    def future(self) -> List[CanvasSnapshot]:
        """Backward-compatible alias for redo_stack."""
        return self.redo_stack

    @future.setter
    def future(self, value: List[CanvasSnapshot]) -> None:
        self.redo_stack = value

    def get_uv_map(self) -> Dict[str, UVBox]:
        """Return UV coordinate mapping corresponding to this canvas's current model."""
        return get_uv_map(self.model)

    def set_model(self, model: str) -> Dict[str, Any]:
        """Set model geometry ('default'/'classic' or 'slim') and adapt part dimensions."""
        from ..converter import convert_skin_model
        return convert_skin_model(self, target_model=model)

    def load_png(self, path_or_file: Any, model: Optional[str] = None) -> bool:
        """
        Load an existing 64x64 (or legacy 64x32, auto-converted to 64x64) skin PNG into parts.
        Returns True if the input was automatically converted from a legacy 64x32 skin.
        """
        arr, was_legacy = load_skin_array(path_or_file)
        self.was_converted_from_legacy = was_legacy

        if model is not None:
            self.model = "slim" if is_slim_model(model) else "default"
        elif np.any(arr[:, :, 3] > 0):
            self.model = detect_skin_model_from_array(arr)

        uv_map = self.get_uv_map()
        for name, (u0, v0, u1, v1) in uv_map.items():
            self.parts[name] = arr[v0:v1, u0:u1].copy()

        return was_legacy

    def to_array(self) -> np.ndarray:
        """Assemble all 72 parts into a 64x64x4 RGBA uint8 numpy array."""
        arr = np.zeros((64, 64, 4), dtype=np.uint8)
        uv_map = self.get_uv_map()
        for name, (u0, v0, u1, v1) in uv_map.items():
            if name in self.parts:
                part = self.parts[name]
                expected_shape = (v1 - v0, u1 - u0, 4)
                if part.shape == expected_shape:
                    arr[v0:v1, u0:u1] = np.clip(part, 0, 255).astype(np.uint8)
                else:
                    im_part = Image.fromarray(np.clip(part, 0, 255).astype(np.uint8), mode="RGBA")
                    im_resized = im_part.resize((u1 - u0, v1 - v0), Image.Resampling.NEAREST)
                    arr[v0:v1, u0:u1] = np.array(im_resized, dtype=np.uint8)
        return arr

    def to_image(self) -> Image.Image:
        """Assemble all parts into a 64x64 RGBA PIL Image."""
        return Image.fromarray(self.to_array(), "RGBA")

    def export_png(self, path: str) -> str:
        """Atomically export all parts into a clean 64x64 RGBA PNG."""
        return atomic_save_png(self.to_image(), path)

    def get_part(self, name: str) -> np.ndarray:
        """Get a copy of a part's (H, W, 4) numpy array."""
        if name not in self.parts:
            raise KeyError(f"Unknown UV part: '{name}'")
        return self.parts[name].copy()

    def set_part(self, name: str, array: Union[np.ndarray, list]) -> None:
        """Set a part directly using a numpy array or nested lists."""
        if name not in self.parts:
            raise KeyError(f"Unknown UV part: '{name}'")
        arr = np.clip(np.asarray(array), 0, 255).astype(np.uint8)
        expected = self.parts[name].shape
        if arr.shape != expected:
            if arr.ndim == 3 and arr.shape[2] == 4:
                im_part = Image.fromarray(arr, mode="RGBA")
                im_resized = im_part.resize((expected[1], expected[0]), Image.Resampling.NEAREST)
                arr = np.array(im_resized, dtype=np.uint8)
            else:
                raise ValueError(f"Part '{name}' expects shape {expected}, got {arr.shape}")
        self.parts[name] = arr

    def fill_part(self, name: str, rgba: Any) -> None:
        """Fill an entire part with a single color (hex or RGBA)."""
        if name not in self.parts:
            raise KeyError(f"Unknown UV part: '{name}'")
        self.parts[name][:] = normalize_color(rgba)

    def set_pixel(self, name: str, x: int, y: int, rgba: Any) -> None:
        """Set an individual pixel on a part (hex or RGBA)."""
        if name not in self.parts:
            raise KeyError(f"Unknown UV part: '{name}'")
        self.parts[name][int(y), int(x)] = normalize_color(rgba)

    def get_pixel(self, name: str, x: int, y: int) -> List[int]:
        """Get color of an individual pixel as [R, G, B, A]."""
        if name not in self.parts:
            raise KeyError(f"Unknown UV part: '{name}'")
        return [int(v) for v in self.parts[name][int(y), int(x)].tolist()]

    def draw_rect(self, name: str, x0: int, y0: int, w: int, h: int, rgba: Any) -> None:
        """Fill a rectangle on a part (hex or RGBA)."""
        if name not in self.parts:
            raise KeyError(f"Unknown UV part: '{name}'")
        part = self.parts[name]
        ph, pw, _ = part.shape
        rx0 = max(0, min(pw, int(x0)))
        ry0 = max(0, min(ph, int(y0)))
        rx1 = max(0, min(pw, int(x0 + w)))
        ry1 = max(0, min(ph, int(y0 + h)))
        if rx1 > rx0 and ry1 > ry0:
            part[ry0:ry1, rx0:rx1] = normalize_color(rgba)

    def set_ascii(self, name: str, ascii_str: str, palette: Union[Dict[str, Any], str]) -> None:
        """Draw a part using a multiline ASCII grid and palette."""
        if name not in self.parts:
            raise KeyError(f"Unknown UV part: '{name}'")

        if isinstance(palette, str):
            from ..color.palettes import TECHWEAR_CYBERPUNK, ANIME_SKIN, CASUAL_STREETWEAR, FANTASY_KNIGHT
            p_upper = palette.strip().upper()
            if p_upper in ("TECHWEAR", "CYBERPUNK", "TECHWEAR_CYBERPUNK"):
                palette = TECHWEAR_CYBERPUNK
            elif p_upper in ("ANIME", "ANIME_SKIN"):
                palette = ANIME_SKIN
            elif p_upper in ("CASUAL", "CASUAL_STREETWEAR", "STREETWEAR"):
                palette = CASUAL_STREETWEAR
            elif p_upper in ("FANTASY", "FANTASY_KNIGHT", "KNIGHT"):
                palette = FANTASY_KNIGHT
            else:
                try:
                    palette = json.loads(palette)
                except Exception as exc:
                    raise ValueError(f"Unknown named palette: '{palette}'.") from exc

        norm_palette: Dict[str, np.ndarray] = {}
        if isinstance(palette, dict):
            for k, v in palette.items():
                norm_palette[k] = np.array(normalize_color(v), dtype=np.uint8)

        for tok in (".", " ", "_"):
            if tok not in norm_palette:
                norm_palette[tok] = np.array([0, 0, 0, 0], dtype=np.uint8)

        lines = [line.strip() for line in ascii_str.strip().split("\n") if line.strip()]
        if not lines:
            return
        h, w, _ = self.parts[name].shape
        src_h = len(lines)
        first_line = list(lines[0].replace(" ", ""))
        src_w = len(first_line)

        parsed = np.zeros((src_h, src_w, 4), dtype=np.uint8)
        for r, line in enumerate(lines):
            chars = list(line.replace(" ", ""))
            if len(chars) != src_w:
                raise ValueError(f"Part '{name}' row {r} expects {src_w} cols, got {len(chars)}: '{line}'")
            for c, ch in enumerate(chars):
                if ch not in norm_palette:
                    raise KeyError(f"Char '{ch}' not in palette")
                parsed[r, c] = norm_palette[ch]

        for dy in range(h):
            for dx in range(w):
                src_x = min(src_w - 1, dx * src_w // w)
                src_y = min(src_h - 1, dy * src_h // h)
                self.parts[name][dy, dx] = parsed[src_y, src_x]

    def apply_ascii_skin(self, palette: Dict[str, Any], parts: Dict[str, str]) -> None:
        """Apply a full skin defined by a global palette and part ASCII grids."""
        for name in self.parts:
            if name in parts:
                self.set_ascii(name, parts[name], palette)
            else:
                self.parts[name][:] = 0

    def apply_gradient(self, name: str, start_color: Any, end_color: Any, direction: str = "vertical") -> None:
        """Apply a smooth linear gradient across a part with safe uint8 clipping."""
        if name not in self.parts:
            raise KeyError(f"Unknown UV part: '{name}'")
        c0 = np.array(normalize_color(start_color), dtype=np.float64)
        c1 = np.array(normalize_color(end_color), dtype=np.float64)
        h, w, _ = self.parts[name].shape

        if direction == "vertical":
            for y in range(h):
                t = y / max(1, h - 1)
                col = np.clip(np.round(c0 * (1.0 - t) + c1 * t), 0, 255).astype(np.uint8)
                self.parts[name][y, :] = col
        else:
            for x in range(w):
                t = x / max(1, w - 1)
                col = np.clip(np.round(c0 * (1.0 - t) + c1 * t), 0, 255).astype(np.uint8)
                self.parts[name][:, x] = col

    def add_noise(self, name: str, amount: int = 6) -> None:
        """Add subtle microtexture to non-transparent pixels (strictly ignores alpha == 0)."""
        if name not in self.parts:
            raise KeyError(f"Unknown UV part: '{name}'")
        part = self.parts[name]
        h, w, _ = part.shape
        noise = np.random.randint(-int(amount), int(amount) + 1, (h, w, 3))
        rgb = np.clip(part[:, :, :3].astype(np.int16) + noise, 0, 255).astype(np.uint8)
        mask = extract_opaque_mask(part, min_alpha=1)
        part[:, :, :3] = np.where(mask[:, :, None], rgb, part[:, :, :3])

    def copy_part(self, src_name: str, dst_name: str, flip_h: bool = False) -> None:
        """Copy pixels from one part to another, with optional horizontal flip."""
        src = self.parts[src_name].copy()
        if flip_h:
            src = np.fliplr(src)
        self.set_part(dst_name, src)

    def mirror_limb(self, src_limb: str = "right_arm", dst_limb: str = "left_arm", mirror_layer2: bool = True) -> None:
        """Mirror an entire limb (arm or leg) to the other side, swapping inner/outer faces."""
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

    def heal_layer1_holes(self, default_color: Any = None) -> int:
        """
        Scan all 36 Base Layer parts (Layer 1) and make all pixels 100% opaque (Rule 1).
        If a pixel has alpha < 255, patches it using nearest opaque neighbor or default_color.
        """
        fallback = np.array(normalize_color(default_color) if default_color else [224, 177, 180, 255], dtype=np.uint8)
        fallback[3] = 255
        healed_count = 0

        for name in BASE_PARTS:
            part = self.parts[name]
            h, w, _ = part.shape
            for y in range(h):
                for x in range(w):
                    if part[y, x, 3] < 255:
                        healed_count += 1
                        if part[y, x, 3] > 0:
                            part[y, x, 3] = 255
                            continue
                        found_color = None
                        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < h and 0 <= nx < w and part[ny, nx, 3] == 255:
                                found_color = part[ny, nx].copy()
                                break
                        if found_color is not None:
                            part[y, x] = found_color
                        else:
                            part[y, x] = fallback
        return healed_count

    def sanitize_outer_layer(self, ensure_relief: bool = False) -> int:
        """
        Enforce Golden Rules 2, 3, and 4 on Layer 2 (Outer Overlay):
          - Rule 3: On 'hat_front', rows 4..7 MUST be 100% transparent across all columns.
          - Rule 4: On 'hat_top', isolated floating crown planks (0 < pixels < 20) are cleared to transparent.
          - Rule 2: Prevents bloated marshmallow Layer 2 (>65% coverage or full duplicate outer faces)
                    by carving bloated faces down to 3D relief cuffs/hems/collars; if ensure_relief=True
                    and Layer 2 is under-dense (<12%), synthesizes clean 3D relief accents from Layer 1.
        Returns total number of outer layer pixels modified/sanitized.
        """
        modified_count = 0

        # Rule 3: hat_front rows 4..7 MUST be 100% transparent
        if "hat_front" in self.parts:
            hat_f = self.parts["hat_front"]
            for r in range(4, hat_f.shape[0]):
                mask = hat_f[r, :, 3] > 0
                cnt = int(np.sum(mask))
                if cnt > 0:
                    modified_count += cnt
                    hat_f[r, mask] = [0, 0, 0, 0]

        # Rule 4: hat_top isolated floating crown planks (< 20 pixels)
        if "hat_top" in self.parts:
            hat_t = self.parts["hat_top"]
            t_alpha = hat_t[:, :, 3] > 0
            t_cnt = int(np.sum(t_alpha))
            if 0 < t_cnt < 20:
                modified_count += t_cnt
                hat_t[t_alpha] = [0, 0, 0, 0]

        # Clear solid white artifact blocks on left_pants_front if present (> 6 pixels)
        if "left_pants_front" in self.parts:
            p_crop = self.parts["left_pants_front"]
            white_mask = (
                (p_crop[:, :, 0] > 240)
                & (p_crop[:, :, 1] > 240)
                & (p_crop[:, :, 2] > 240)
                & (p_crop[:, :, 3] > 0)
            )
            w_cnt = int(np.sum(white_mask))
            if w_cnt > 6:
                modified_count += w_cnt
                p_crop[white_mask] = [0, 0, 0, 0]

        # Rule 2 check: compute current Layer 2 density
        l2_pixels = sum(int(np.sum(self.parts[p][:, :, 3] > 0)) for p in OUTER_PARTS)
        l2_total = sum(self.parts[p].shape[0] * self.parts[p].shape[1] for p in OUTER_PARTS)
        l2_ratio = l2_pixels / max(1, l2_total)

        # If Layer 2 is bloated (> 65% filled), carve interiors of torso/limb outer faces into relief bands
        if l2_ratio > 0.65:
            for outer_name in OUTER_PARTS:
                if outer_name.startswith("hat_"):
                    continue
                part = self.parts[outer_name]
                h, w, _ = part.shape
                if outer_name.endswith("_top") or outer_name.endswith("_bottom"):
                    cnt = int(np.sum(part[:, :, 3] > 0))
                    if cnt > 0:
                        modified_count += cnt
                        part[:] = [0, 0, 0, 0]
                elif h >= 8:
                    # Keep collar/cuff/hem rows (row 0..1 and row h-3..h-2), clear middle bulk
                    mid_mask = part[2:h - 2, :, 3] > 0
                    cnt = int(np.sum(mid_mask))
                    if cnt > 0:
                        modified_count += cnt
                        part[2:h - 2, :] = [0, 0, 0, 0]

        # If ensure_relief=True and Layer 2 is too sparse (< 12%), add clean 3D relief accents from Base Layer
        if ensure_relief:
            l2_pixels = sum(int(np.sum(self.parts[p][:, :, 3] > 0)) for p in OUTER_PARTS)
            l2_ratio = l2_pixels / max(1, l2_total)
            if l2_ratio < 0.12:
                # 1. Hair bangs on hat_front rows 0..2 derived from head_front / head_top
                hf_base = self.parts["head_front"]
                hat_f = self.parts["hat_front"]
                for r in range(0, 3):
                    for c in range(hat_f.shape[1]):
                        if r < 2 or c in (0, 1, 6, 7):
                            if hat_f[r, c, 3] == 0:
                                px = hf_base[r, c].copy()
                                px[:3] = np.clip(px[:3].astype(np.int16) + 12, 0, 255).astype(np.uint8)
                                px[3] = 255
                                hat_f[r, c] = px
                                modified_count += 1

                # 2. Jacket collar & hem relief on jacket_front and jacket_back
                for b_name, o_name in (("body_front", "jacket_front"), ("body_back", "jacket_back")):
                    b_part = self.parts[b_name]
                    o_part = self.parts[o_name]
                    for r in (1, 2, 9, 10):
                        for c in range(o_part.shape[1]):
                            if o_part[r, c, 3] == 0:
                                px = b_part[r, c].copy()
                                px[:3] = np.clip(px[:3].astype(np.int16) + 10, 0, 255).astype(np.uint8)
                                px[3] = 255
                                o_part[r, c] = px
                                modified_count += 1

                # 3. Sleeve cuffs on rows 2..3 and Pants cuffs on rows 8..9
                for limb_base, limb_outer, target_rows in (
                    ("right_arm", "right_sleeve", (2, 3)),
                    ("left_arm", "left_sleeve", (2, 3)),
                    ("right_leg", "right_pants", (8, 9)),
                    ("left_leg", "left_pants", (8, 9)),
                ):
                    for face in ("front", "back", "right", "left"):
                        b_part = self.parts[f"{limb_base}_{face}"]
                        o_part = self.parts[f"{limb_outer}_{face}"]
                        for r in target_rows:
                            for c in range(o_part.shape[1]):
                                if o_part[r, c, 3] == 0:
                                    px = b_part[r, c].copy()
                                    px[:3] = np.clip(px[:3].astype(np.int16) + 10, 0, 255).astype(np.uint8)
                                    px[3] = 255
                                    o_part[r, c] = px
                                    modified_count += 1

        return modified_count

    def clear_layer(self, layer: str = "outer", parts: Optional[List[str]] = None) -> int:
        """Clear an entire layer ('outer' or 'base') or specific parts to transparent [0, 0, 0, 0]."""
        if parts:
            target_parts = list(parts)
        elif layer == "outer":
            target_parts = list(OUTER_PARTS)
        elif layer == "base":
            target_parts = list(BASE_PARTS)
        else:
            target_parts = []

        count = 0
        for name in target_parts:
            if name in self.parts:
                self.parts[name][:] = [0, 0, 0, 0]
                count += 1
        return count

    def denoise_palette(self, min_pixel_count: int = 3, part_name: Optional[str] = None) -> int:
        """
        Denoise / quantize palette by replacing rare, isolated color pixels
        with their closest dominant palette neighbor. Strictly ignores alpha == 0 pixels.
        """
        self.push_undo("denoise_palette")
        parts_to_scan = [part_name] if (part_name and part_name in self.parts) else list(self.parts.keys())

        all_pixels = []
        for p in parts_to_scan:
            arr = self.parts[p]
            mask = arr[:, :, 3] > 0
            if np.any(mask):
                all_pixels.append(arr[mask][:, :3])

        if not all_pixels:
            return 0

        stacked = np.vstack(all_pixels)
        unique, counts = np.unique(stacked, axis=0, return_counts=True)
        dominant_palette = unique[counts >= min_pixel_count]

        if len(dominant_palette) == 0:
            return 0

        dom_f = dominant_palette.astype(np.int32)
        modified_count = 0
        for p in parts_to_scan:
            arr = self.parts[p]
            for y in range(arr.shape[0]):
                for x in range(arr.shape[1]):
                    if arr[y, x, 3] > 0:
                        rgb = arr[y, x, :3]
                        color_idx = np.where((unique == rgb).all(axis=1))[0]
                        if len(color_idx) > 0 and counts[color_idx[0]] < min_pixel_count:
                            dists = np.sum((dom_f - rgb.astype(np.int32)) ** 2, axis=1)
                            closest = dominant_palette[np.argmin(dists)]
                            arr[y, x, :3] = np.clip(closest, 0, 255).astype(np.uint8)
                            modified_count += 1
        return modified_count

    def replace_color(
        self,
        old_color: Any,
        new_color: Any,
        part_name: Optional[str] = None,
        tolerance: int = 15,
        layer: str = "both"
    ) -> Tuple[int, List[str]]:
        """Replace occurrences of old_color with new_color within RGB tolerance threshold."""
        target_rgba = normalize_color(old_color)
        target_rgb = np.array(target_rgba[:3], dtype=np.float64)
        replace_rgba = np.array(normalize_color(new_color), dtype=np.uint8)

        if part_name and part_name not in ("all", "*"):
            target_parts = [part_name] if part_name in self.parts else []
        elif layer == "base":
            target_parts = list(BASE_PARTS)
        elif layer == "outer":
            target_parts = list(OUTER_PARTS)
        else:
            target_parts = list(self.parts.keys())

        total_replaced = 0
        affected_parts: List[str] = []

        for name in target_parts:
            part = self.parts[name]
            if target_rgba[3] == 0:
                mask = part[:, :, 3] == 0
            else:
                rgb = part[:, :, :3].astype(np.float64)
                dist = np.sqrt(np.sum((rgb - target_rgb) ** 2, axis=2))
                mask = (dist <= float(tolerance)) & (part[:, :, 3] > 0)

            replaced_in_part = int(np.sum(mask))
            if replaced_in_part > 0:
                part[mask] = replace_rgba
                total_replaced += replaced_in_part
                affected_parts.append(name)

        return total_replaced, affected_parts

    def set_pixels(self, part_name: str, pixel_list: List[Any]) -> int:
        """Efficiently set multiple individual pixels on a part."""
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

            if x is not None and y is not None and 0 <= int(x) < w and 0 <= int(y) < h:
                part[int(y), int(x)] = normalize_color(col)
                count += 1

        return count

    def list_colors(self, part_name: Optional[str] = None, top_n: int = 16, ignore_transparent: bool = False) -> List[Dict[str, Any]]:
        """Inspect unique colors and frequency on a part or the entire skin canvas."""
        if part_name and part_name in self.parts:
            pixels = self.parts[part_name].reshape(-1, 4)
        else:
            pixels = np.vstack([p.reshape(-1, 4) for p in self.parts.values()])

        if ignore_transparent:
            pixels = pixels[pixels[:, 3] > 0]
            if len(pixels) == 0:
                return []

        unique_colors, counts = np.unique(pixels, axis=0, return_counts=True)
        total_pixels = max(1, len(pixels))
        sorted_indices = np.argsort(-counts)
        results: List[Dict[str, Any]] = []

        for idx in sorted_indices[:top_n]:
            rgba = [int(v) for v in unique_colors[idx].tolist()]
            cnt = int(counts[idx])
            results.append({
                "hex": rgba_to_hex(rgba),
                "rgb": rgba[:3],
                "alpha": rgba[3],
                "count": cnt,
                "percentage": round((cnt / total_pixels) * 100, 2),
            })

        return results

    def diff(self, other: Union[str, "SkinCanvas"], part_name: Optional[str] = None) -> Dict[str, Any]:
        """Compare active canvas against another SkinCanvas or a skin PNG file."""
        if isinstance(other, str):
            other_canvas = SkinCanvas(model=self.model)
            other_canvas.load_png(other)
        elif isinstance(other, SkinCanvas):
            other_canvas = other
        else:
            raise TypeError("other must be a SkinCanvas instance or a file path string.")

        target_parts = [part_name] if (part_name and part_name in self.parts) else list(ALL_PARTS)
        total_diff_pixels = 0
        differing_parts: List[Dict[str, Any]] = []
        identical_parts: List[str] = []

        for name in target_parts:
            p1 = self.parts[name]
            p2 = other_canvas.parts[name]
            if p1.shape != p2.shape:
                im2 = Image.fromarray(p2, mode="RGBA").resize((p1.shape[1], p1.shape[0]), Image.Resampling.NEAREST)
                p2 = np.array(im2, dtype=np.uint8)
            diff_mask = np.any(p1 != p2, axis=2)
            diff_count = int(np.sum(diff_mask))

            if diff_count > 0:
                total_diff_pixels += diff_count
                ys, xs = np.where(diff_mask)
                diff_coords = [{"x": int(x), "y": int(y)} for y, x in zip(ys[:16], xs[:16])]
                differing_parts.append({
                    "part_name": name,
                    "diff_pixels": diff_count,
                    "sample_coords": diff_coords,
                })
            else:
                identical_parts.append(name)

        return {
            "status": "identical" if total_diff_pixels == 0 else "different",
            "total_diff_pixels": total_diff_pixels,
            "differing_parts_count": len(differing_parts),
            "identical_parts_count": len(identical_parts),
            "differing_parts": differing_parts,
        }

    # ==========================================
    # HISTORY & CHECKPOINTS (UNDO / REDO)
    # ==========================================

    def _snapshot(self, action: str = "edit") -> CanvasSnapshot:
        """Create a deep-copied CanvasSnapshot with metadata."""
        return CanvasSnapshot(self.parts, action=action, model=self.model)

    def push_undo(self, action: str = "edit") -> None:
        """Record current state to undo_stack (capped at 30 states) and clear redo_stack."""
        self.undo_stack.append(self._snapshot(action=action))
        if len(self.undo_stack) > MAX_HISTORY_STATES:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> bool:
        """Revert to previous canvas state from undo_stack. Returns True if undone."""
        if not self.undo_stack:
            return False
        prev = self.undo_stack.pop()
        self.redo_stack.append(self._snapshot(action=prev.action))
        if len(self.redo_stack) > MAX_HISTORY_STATES:
            self.redo_stack.pop(0)
        self.model = prev.model
        self.parts = prev.copy_parts()
        return True

    def redo(self) -> bool:
        """Reapply previously undone state from redo_stack. Returns True if redone."""
        if not self.redo_stack:
            return False
        nxt = self.redo_stack.pop()
        self.undo_stack.append(self._snapshot(action=nxt.action))
        if len(self.undo_stack) > MAX_HISTORY_STATES:
            self.undo_stack.pop(0)
        self.model = nxt.model
        self.parts = nxt.copy_parts()
        return True

    def create_checkpoint(self, name: str) -> int:
        """Save a named milestone state for instant restoration."""
        self.checkpoints[name] = self._snapshot(action=f"checkpoint:{name}")
        return len(self.checkpoints)

    def restore_checkpoint(self, name: str) -> bool:
        """Restore canvas to a named checkpoint."""
        if name not in self.checkpoints:
            return False
        self.push_undo(action=f"restore_checkpoint:{name}")
        snap = self.checkpoints[name]
        self.model = snap.model
        self.parts = snap.copy_parts()
        return True

    def get_history_summary(self) -> Dict[str, Any]:
        """Return structured summary of undo_stack, redo_stack, and checkpoints."""
        return {
            "max_states": MAX_HISTORY_STATES,
            "undo_count": len(self.undo_stack),
            "redo_count": len(self.redo_stack),
            "undo_stack": [
                {
                    "index": idx,
                    "action": snap.action,
                    "model": snap.model,
                    "timestamp": round(snap.timestamp, 3),
                }
                for idx, snap in enumerate(self.undo_stack)
            ],
            "redo_stack": [
                {
                    "index": idx,
                    "action": snap.action,
                    "model": snap.model,
                    "timestamp": round(snap.timestamp, 3),
                }
                for idx, snap in enumerate(self.redo_stack)
            ],
            "checkpoints": list(self.checkpoints.keys()),
        }

    # ==========================================
    # VECTORIZED HSL / HSV MANIPULATIONS
    # ==========================================

    def adjust_hsv(
        self,
        part_name: Optional[str] = None,
        hue_shift: float = 0.0,
        sat_mult: float = 1.0,
        val_mult: float = 1.0,
        target_color: Optional[Any] = None,
        tolerance: int = 30,
        layer: str = "both"
    ) -> Tuple[int, List[str]]:
        """
        Vectorized Hue, Saturation, and Brightness adjustment across part(s) or entire skin.
        Strictly ignores transparent pixels (alpha == 0).
        """
        if part_name and part_name not in ("all", "*"):
            target_parts = [part_name] if part_name in self.parts else []
        elif layer == "base":
            target_parts = list(BASE_PARTS)
        elif layer == "outer":
            target_parts = list(OUTER_PARTS)
        else:
            target_parts = list(self.parts.keys())

        total_adjusted = 0
        affected_parts: List[str] = []

        for name in target_parts:
            updated, count = adjust_rgba_hsv(
                self.parts[name],
                hue_shift=hue_shift,
                sat_mult=sat_mult,
                val_mult=val_mult,
                target_color=target_color,
                tolerance=float(tolerance),
            )
            if count > 0:
                self.parts[name] = updated
                total_adjusted += count
                affected_parts.append(name)

        return total_adjusted, affected_parts

    def adjust_hsl(
        self,
        part_name: Optional[str] = None,
        hue_shift: float = 0.0,
        sat_mult: float = 1.0,
        light_mult: float = 1.0,
        target_color: Optional[Any] = None,
        tolerance: int = 30,
        layer: str = "both"
    ) -> Tuple[int, List[str]]:
        """
        Vectorized Hue, Saturation, and Lightness (HSL) adjustment across part(s) or entire skin.
        Strictly ignores transparent pixels (alpha == 0).
        """
        if part_name and part_name not in ("all", "*"):
            target_parts = [part_name] if part_name in self.parts else []
        elif layer == "base":
            target_parts = list(BASE_PARTS)
        elif layer == "outer":
            target_parts = list(OUTER_PARTS)
        else:
            target_parts = list(self.parts.keys())

        total_adjusted = 0
        affected_parts: List[str] = []

        for name in target_parts:
            updated, count = adjust_rgba_hsl(
                self.parts[name],
                hue_shift=hue_shift,
                sat_mult=sat_mult,
                light_mult=light_mult,
                target_color=target_color,
                tolerance=float(tolerance),
            )
            if count > 0:
                self.parts[name] = updated
                total_adjusted += count
                affected_parts.append(name)

        return total_adjusted, affected_parts
