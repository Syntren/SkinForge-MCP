"""
Rendering subsystem for SkinForge.
Includes Z-buffered 3D Minecraft player rasterizer and 2D composite tools.
"""

import numpy as np
from PIL import Image

class Minecraft3DRenderer:
    """True 3D Z-buffered software rasterizer simulating in-game Minecraft player rendering."""
    def __init__(self, width=800, height=600):
        self.w = width
        self.h = height
        self.color_buf = np.zeros((height, width, 4), dtype=np.uint8)
        self.depth_buf = np.full((height, width), 1e9, dtype=np.float32)

    def clear(self, bg=(18, 16, 24, 255)):
        self.color_buf[:] = bg
        self.depth_buf[:] = 1e9

    def render_model(self, skin_arr, yaw_deg=-25, pitch_deg=15, ox=400, oy=320, scale=12, outer_dilation=0.35, layer_mode="both", model="default"):
        """
        Render player model with given camera angles into internal buffer.
        layer_mode: 'both' (default), 'base' (Layer 1 only), or 'outer' (Layer 2 only).
        model: 'default' (Steve 4px arms) or 'slim' (Alex 3px arms).
        """
        rad_yaw = np.radians(yaw_deg)
        rad_pitch = np.radians(pitch_deg)

        cos_y, sin_y = np.cos(rad_yaw), np.sin(rad_yaw)
        cos_p, sin_p = np.cos(rad_pitch), np.sin(rad_pitch)

        def transform(v):
            x, y, z = v
            # Yaw
            x1 = x * cos_y + z * sin_y
            y1 = y
            z1 = -x * sin_y + z * cos_y
            # Pitch
            x2 = x1
            y2 = y1 * cos_p - z1 * sin_p
            z2 = y1 * sin_p + z1 * cos_p
            # Screen projection
            sx = x2 * scale + ox
            sy = -y2 * scale + oy
            return (sx, sy, -z2)

        def draw_box(x0, y0, z0, sx, sy, sz, faces):
            for face_name, (u0, v0, u1, v1) in faces.items():
                fw = u1 - u0
                fh = v1 - v0
                crop = skin_arr[v0:v1, u0:u1]

                if face_name == 'top':
                    shade = 1.0
                elif face_name == 'bottom':
                    shade = 0.55
                elif face_name == 'front':
                    shade = 0.88
                elif face_name == 'back':
                    shade = 0.82
                elif face_name == 'left':
                    shade = 0.72
                elif face_name == 'right':
                    shade = 0.76

                for r in range(fh):
                    for c in range(fw):
                        rgba = crop[r, c]
                        if rgba[3] < 10:
                            continue

                        col = (int(rgba[0]*shade), int(rgba[1]*shade), int(rgba[2]*shade), rgba[3])

                        if face_name == 'front':
                            px0 = x0 + c * sx / fw
                            px1 = x0 + (c + 1) * sx / fw
                            py0 = y0 + (fh - 1 - r) * sy / fh
                            py1 = y0 + (fh - r) * sy / fh
                            pz = z0 + sz
                            p1, p2, p3, p4 = (px0, py0, pz), (px1, py0, pz), (px1, py1, pz), (px0, py1, pz)
                        elif face_name == 'back':
                            px0 = x0 + (fw - 1 - c) * sx / fw
                            px1 = x0 + (fw - c) * sx / fw
                            py0 = y0 + (fh - 1 - r) * sy / fh
                            py1 = y0 + (fh - r) * sy / fh
                            pz = z0
                            p1, p2, p3, p4 = (px1, py0, pz), (px0, py0, pz), (px0, py1, pz), (px1, py1, pz)
                        elif face_name == 'top':
                            px0 = x0 + c * sx / fw
                            px1 = x0 + (c + 1) * sx / fw
                            pz0 = z0 + (fh - 1 - r) * sz / fh
                            pz1 = z0 + (fh - r) * sz / fh
                            py = y0 + sy
                            p1, p2, p3, p4 = (px0, py, pz0), (px1, py, pz0), (px1, py, pz1), (px0, py, pz1)
                        elif face_name == 'bottom':
                            px0 = x0 + c * sx / fw
                            px1 = x0 + (c + 1) * sx / fw
                            pz0 = z0 + r * sz / fh
                            pz1 = z0 + (r + 1) * sz / fh
                            py = y0
                            p1, p2, p3, p4 = (px0, py, pz0), (px1, py, pz0), (px1, py, pz1), (px0, py, pz1)
                        elif face_name == 'right':
                            pz0 = z0 + c * sz / fw
                            pz1 = z0 + (c + 1) * sz / fw
                            py0 = y0 + (fh - 1 - r) * sy / fh
                            py1 = y0 + (fh - r) * sy / fh
                            px = x0
                            p1, p2, p3, p4 = (px, py0, pz1), (px, py0, pz0), (px, py1, pz0), (px, py1, pz1)
                        elif face_name == 'left':
                            pz0 = z0 + (fw - 1 - c) * sz / fw
                            pz1 = z0 + (fw - c) * sz / fw
                            py0 = y0 + (fh - 1 - r) * sy / fh
                            py1 = y0 + (fh - r) * sy / fh
                            px = x0 + sx
                            p1, p2, p3, p4 = (px, py0, pz0), (px, py0, pz1), (px, py1, pz1), (px, py1, pz0)

                        v1, v2, v3, v4 = transform(p1), transform(p2), transform(p3), transform(p4)
                        self.draw_quad(v1, v2, v3, v4, col)

        # UV Boxes mapping
        head_f = {'top': (8, 0, 16, 8), 'bottom': (16, 0, 24, 8), 'right': (0, 8, 8, 16), 'front': (8, 8, 16, 16), 'left': (16, 8, 24, 16), 'back': (24, 8, 32, 16)}
        hat_f  = {'top': (40, 0, 48, 8), 'bottom': (48, 0, 56, 8), 'right': (32, 8, 40, 16), 'front': (40, 8, 48, 16), 'left': (48, 8, 56, 16), 'back': (56, 8, 64, 16)}
        body_f = {'top': (20, 16, 28, 20), 'bottom': (28, 16, 36, 20), 'right': (16, 20, 20, 32), 'front': (20, 20, 28, 32), 'left': (28, 20, 32, 32), 'back': (32, 20, 40, 32)}
        jack_f = {'top': (20, 32, 28, 36), 'bottom': (28, 32, 36, 36), 'right': (16, 36, 20, 48), 'front': (20, 36, 28, 48), 'left': (28, 36, 32, 48), 'back': (32, 36, 40, 48)}
        r_leg_f = {'top': (4, 16, 8, 20), 'bottom': (8, 16, 12, 20), 'right': (0, 20, 4, 32), 'front': (4, 20, 8, 32), 'left': (8, 20, 12, 32), 'back': (12, 20, 16, 32)}
        r_pnt_f = {'top': (4, 32, 8, 36), 'bottom': (8, 32, 12, 36), 'right': (0, 36, 4, 48), 'front': (4, 36, 8, 48), 'left': (8, 36, 12, 48), 'back': (12, 36, 16, 48)}
        l_leg_f = {'top': (20, 48, 24, 52), 'bottom': (24, 48, 28, 52), 'right': (16, 52, 20, 64), 'front': (20, 52, 24, 64), 'left': (24, 52, 28, 64), 'back': (28, 52, 32, 64)}
        l_pnt_f = {'top': (4, 48, 8, 52), 'bottom': (8, 48, 12, 52), 'right': (0, 52, 4, 64), 'front': (4, 52, 8, 64), 'left': (8, 52, 12, 64), 'back': (12, 52, 16, 64)}

        is_slim = bool(model and model.lower() == "slim")
        if is_slim:
            r_arm_f = {'top': (44, 16, 47, 20), 'bottom': (47, 16, 50, 20), 'right': (40, 20, 44, 32), 'front': (44, 20, 47, 32), 'left': (47, 20, 51, 32), 'back': (51, 20, 54, 32)}
            r_slv_f = {'top': (44, 32, 47, 36), 'bottom': (47, 32, 50, 36), 'right': (40, 36, 44, 48), 'front': (44, 36, 47, 48), 'left': (47, 36, 51, 48), 'back': (51, 36, 54, 48)}
            l_arm_f = {'top': (36, 48, 39, 52), 'bottom': (39, 48, 42, 52), 'right': (32, 52, 36, 64), 'front': (36, 52, 39, 64), 'left': (39, 52, 43, 64), 'back': (43, 52, 46, 64)}
            l_slv_f = {'top': (52, 48, 55, 52), 'bottom': (55, 48, 58, 52), 'right': (48, 52, 52, 64), 'front': (52, 52, 55, 64), 'left': (55, 52, 59, 64), 'back': (59, 52, 62, 64)}
            arm_w = 3
            r_arm_x = -7
        else:
            r_arm_f = {'top': (44, 16, 48, 20), 'bottom': (48, 16, 52, 20), 'right': (40, 20, 44, 32), 'front': (44, 20, 48, 32), 'left': (48, 20, 52, 32), 'back': (52, 20, 56, 32)}
            r_slv_f = {'top': (44, 32, 48, 36), 'bottom': (48, 32, 52, 36), 'right': (40, 36, 44, 48), 'front': (44, 36, 48, 48), 'left': (48, 36, 52, 48), 'back': (52, 36, 56, 48)}
            l_arm_f = {'top': (36, 48, 40, 52), 'bottom': (40, 48, 44, 52), 'right': (32, 52, 36, 64), 'front': (36, 52, 40, 64), 'left': (40, 52, 44, 64), 'back': (44, 52, 48, 64)}
            l_slv_f = {'top': (52, 48, 56, 52), 'bottom': (56, 48, 60, 52), 'right': (48, 52, 52, 64), 'front': (52, 52, 56, 64), 'left': (56, 52, 60, 64), 'back': (60, 52, 64, 64)}
            arm_w = 4
            r_arm_x = -8

        # Render Base Layer (Layer 1)
        if layer_mode in ('both', 'base'):
            draw_box(-4, 24, -4, 8, 8, 8, head_f)
            draw_box(-4, 12, -2, 8, 12, 4, body_f)
            draw_box(r_arm_x, 12, -2, arm_w, 12, 4, r_arm_f)
            draw_box(4, 12, -2, arm_w, 12, 4, l_arm_f)
            draw_box(-4, 0, -2, 4, 12, 4, r_leg_f)
            draw_box(0, 0, -2, 4, 12, 4, l_leg_f)

        # Render Outer Layer (Layer 2)
        if layer_mode in ('both', 'outer'):
            o = outer_dilation
            draw_box(-4-o, 24-o, -4-o, 8+2*o, 8+2*o, 8+2*o, hat_f)
            draw_box(-4-o, 12-o, -2-o, 8+2*o, 12+2*o, 4+2*o, jack_f)
            draw_box(r_arm_x-o, 12-o, -2-o, arm_w+2*o, 12+2*o, 4+2*o, r_slv_f)
            draw_box(4-o, 12-o, -2-o, arm_w+2*o, 12+2*o, 4+2*o, l_slv_f)
            draw_box(-4-o, 0-o, -2-o, 4+2*o, 12+2*o, 4+2*o, r_pnt_f)
            draw_box(0-o, 0-o, -2-o, 4+2*o, 12+2*o, 4+2*o, l_pnt_f)

    def draw_quad(self, v0, v1, v2, v3, rgba):
        self.draw_triangle(v0, v1, v2, rgba)
        self.draw_triangle(v0, v2, v3, rgba)

    def draw_triangle(self, v0, v1, v2, rgba):
        if rgba[3] < 10:
            return

        min_x = max(0, int(min(v0[0], v1[0], v2[0])))
        max_x = min(self.w - 1, int(max(v0[0], v1[0], v2[0])))
        min_y = max(0, int(min(v0[1], v1[1], v2[1])))
        max_y = min(self.h - 1, int(max(v0[1], v1[1], v2[1])))

        if min_x > max_x or min_y > max_y:
            return

        x0, y0, z0 = v0
        x1, y1, z1 = v1
        x2, y2, z2 = v2

        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denom) < 1e-6:
            return

        inv_denom = 1.0 / denom
        xs = np.arange(min_x, max_x + 1)
        ys = np.arange(min_y, max_y + 1)
        grid_x, grid_y = np.meshgrid(xs, ys)

        w0 = ((y1 - y2) * (grid_x - x2) + (x2 - x1) * (grid_y - y2)) * inv_denom
        w1 = ((y2 - y0) * (grid_x - x2) + (x0 - x2) * (grid_y - y2)) * inv_denom
        w2 = 1.0 - w0 - w1

        mask = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not np.any(mask):
            return

        interp_z = w0 * z0 + w1 * z1 + w2 * z2
        y_coords, x_coords = np.where(mask)

        for yr, xr in zip(y_coords, x_coords):
            x = xs[xr]
            y = ys[yr]
            z = interp_z[yr, xr]
            if z < self.depth_buf[y, x]:
                if rgba[3] == 255:
                    self.depth_buf[y, x] = z
                    self.color_buf[y, x] = rgba
                else:
                    bg = self.color_buf[y, x]
                    alpha = rgba[3] / 255.0
                    out_rgb = (np.array(rgba[:3]) * alpha + bg[:3] * (1.0 - alpha)).astype(np.uint8)
                    self.color_buf[y, x] = [out_rgb[0], out_rgb[1], out_rgb[2], 255]
                    self.depth_buf[y, x] = z


def _extract_skin_arr(skin_source):
    """Extract (64, 64, 4) numpy array from file path, SkinCanvas, PIL Image, or numpy array."""
    if isinstance(skin_source, str):
        im = Image.open(skin_source).convert("RGBA")
        return np.array(im)
    elif hasattr(skin_source, "to_array"):
        return skin_source.to_array()
    elif hasattr(skin_source, "parts"):
        from .canvas import get_uv_map
        model = getattr(skin_source, "model", "default")
        uv_map = get_uv_map(model)
        arr = np.zeros((64, 64, 4), dtype=np.uint8)
        for name, (u0, v0, u1, v1) in uv_map.items():
            if name in skin_source.parts:
                part = skin_source.parts[name]
                if part.shape == (v1 - v0, u1 - u0, 4):
                    arr[v0:v1, u0:u1] = part
        return arr
    elif isinstance(skin_source, Image.Image):
        return np.array(skin_source.convert("RGBA"))
    elif isinstance(skin_source, np.ndarray):
        return skin_source
    raise TypeError(f"Unsupported skin source: {type(skin_source)}")


def render_composite_2d(skin_source, out_path=None, scale=16):
    """Render front and back 2D composite view with Layer 2 overlaid."""
    skin_arr = _extract_skin_arr(skin_source)
    skin = Image.fromarray(skin_arr)

    # Front parts
    head_f   = skin.crop((8, 8, 16, 16))
    body_f   = skin.crop((20, 20, 28, 32))
    r_arm_f  = skin.crop((44, 20, 48, 32))
    l_arm_f  = skin.crop((36, 52, 40, 64))
    r_leg_f  = skin.crop((4, 20, 8, 32))
    l_leg_f  = skin.crop((20, 52, 24, 64))

    hat_f      = skin.crop((40, 8, 48, 16))
    jacket_f   = skin.crop((20, 36, 28, 48))
    r_sleeve_f = skin.crop((44, 36, 48, 48))
    l_sleeve_f = skin.crop((52, 52, 56, 64))
    r_pants_f  = skin.crop((4, 36, 8, 48))
    l_pants_f  = skin.crop((4, 52, 8, 64))

    front = Image.new("RGBA", (16, 32), (0, 0, 0, 0))
    front.paste(head_f, (4, 0))
    front.paste(body_f, (4, 8))
    front.paste(r_arm_f, (0, 8))
    front.paste(l_arm_f, (12, 8))
    front.paste(r_leg_f, (4, 20))
    front.paste(l_leg_f, (8, 20))

    front.paste(hat_f, (4, 0), hat_f)
    front.paste(jacket_f, (4, 8), jacket_f)
    front.paste(r_sleeve_f, (0, 8), r_sleeve_f)
    front.paste(l_sleeve_f, (12, 8), l_sleeve_f)
    front.paste(r_pants_f, (4, 20), r_pants_f)
    front.paste(l_pants_f, (8, 20), l_pants_f)

    # Back parts
    head_b   = skin.crop((24, 8, 32, 16))
    body_b   = skin.crop((32, 20, 40, 32))
    l_arm_b  = skin.crop((44, 52, 48, 64))
    r_arm_b  = skin.crop((52, 20, 56, 32))
    l_leg_b  = skin.crop((28, 52, 32, 64))
    r_leg_b  = skin.crop((12, 20, 16, 32))

    hat_b      = skin.crop((56, 8, 64, 16))
    jacket_b   = skin.crop((32, 36, 40, 48))
    l_sleeve_b = skin.crop((60, 52, 64, 64))
    r_sleeve_b = skin.crop((52, 36, 56, 48))
    l_pants_b  = skin.crop((12, 52, 16, 64))
    r_pants_b  = skin.crop((12, 36, 16, 48))

    back = Image.new("RGBA", (16, 32), (0, 0, 0, 0))
    back.paste(head_b, (4, 0))
    back.paste(body_b, (4, 8))
    back.paste(l_arm_b, (0, 8))
    back.paste(r_arm_b, (12, 8))
    back.paste(l_leg_b, (4, 20))
    back.paste(r_leg_b, (8, 20))

    back.paste(hat_b, (4, 0), hat_b)
    back.paste(jacket_b, (4, 8), jacket_b)
    back.paste(l_sleeve_b, (0, 8), l_sleeve_b)
    back.paste(r_sleeve_b, (12, 8), r_sleeve_b)
    back.paste(l_pants_b, (4, 20), l_pants_b)
    back.paste(r_pants_b, (8, 20), r_pants_b)

    canvas = Image.new("RGBA", (36, 36), (18, 16, 24, 255))
    canvas.paste(front, (2, 2), front)
    canvas.paste(back, (18, 2), back)

    res = canvas.resize((36 * scale, 36 * scale), Image.Resampling.NEAREST)
    if out_path:
        res.save(out_path)
        return out_path
    return res


def render_3d_single(skin_source, yaw_deg=-30, pitch_deg=15, width=400, height=480, scale=9, ox=200, oy=320, layer_mode="both", model=None, out_path=None):
    """Render a single 3D camera angle of the player model."""
    skin_arr = _extract_skin_arr(skin_source)
    if model is None:
        model = getattr(skin_source, "model", "default")
    renderer = Minecraft3DRenderer(width, height)
    renderer.clear((18, 16, 24, 255))
    renderer.render_model(skin_arr, yaw_deg=yaw_deg, pitch_deg=pitch_deg, ox=ox, oy=oy, scale=scale, layer_mode=layer_mode, model=model)
    out = Image.fromarray(renderer.color_buf)
    if out_path:
        out.save(out_path)
        return out_path
    return out


def render_3d_turnaround(skin_source, out_path=None, layer_mode="both", model=None):
    """Render complete 4-angle 3D view (Front 3/4, Left profile, Back 3/4, Back straight)."""
    skin_arr = _extract_skin_arr(skin_source)
    if model is None:
        model = getattr(skin_source, "model", "default")
    renderer = Minecraft3DRenderer(1000, 480)
    renderer.clear((18, 16, 24, 255))

    # Angle 1: Front 3/4
    renderer.render_model(skin_arr, yaw_deg=-30, pitch_deg=15, ox=140, oy=320, scale=9, layer_mode=layer_mode, model=model)
    # Angle 2: Side Left profile
    renderer.render_model(skin_arr, yaw_deg=75, pitch_deg=8, ox=380, oy=320, scale=9, layer_mode=layer_mode, model=model)
    # Angle 3: Back 3/4
    renderer.render_model(skin_arr, yaw_deg=150, pitch_deg=15, ox=620, oy=320, scale=9, layer_mode=layer_mode, model=model)
    # Angle 4: Back straight
    renderer.render_model(skin_arr, yaw_deg=180, pitch_deg=10, ox=860, oy=320, scale=9, layer_mode=layer_mode, model=model)

    out = Image.fromarray(renderer.color_buf)
    if out_path:
        out.save(out_path)
        return out_path
    return out


def render_part_zoomed(skin_source, part_name, scale=16, show_grid=True, out_path=None):
    """
    Render a single UV part enlarged with an optional pixel grid for LLM inspection.
    """
    from .canvas import MINECRAFT_UV_MAP
    if part_name not in MINECRAFT_UV_MAP:
        raise KeyError(f"Unknown part '{part_name}'. Valid parts: {list(MINECRAFT_UV_MAP.keys())}")

    skin_arr = _extract_skin_arr(skin_source)
    u0, v0, u1, v1 = MINECRAFT_UV_MAP[part_name]
    crop = skin_arr[v0:v1, u0:u1]
    h, w, _ = crop.shape

    # Upscale
    img = Image.fromarray(crop).resize((w * scale, h * scale), Image.Resampling.NEAREST)

    if show_grid and scale >= 8:
        # Draw pixel grid overlay
        grid_arr = np.array(img)
        # Vertical grid lines
        for x in range(0, w * scale, scale):
            grid_arr[:, x, :3] = (grid_arr[:, x, :3].astype(int) + 40).clip(0, 255).astype(np.uint8)
        # Horizontal grid lines
        for y in range(0, h * scale, scale):
            grid_arr[y, :, :3] = (grid_arr[y, :, :3].astype(int) + 40).clip(0, 255).astype(np.uint8)
        img = Image.fromarray(grid_arr)

    if out_path:
        img.save(out_path)
        return out_path
    return img


def render_turntable_gif(skin_source, out_path, frames=16, fps=12, layer_mode="both", model=None):
    """Render an animated 360-degree turntable rotation GIF of the player."""
    skin_arr = _extract_skin_arr(skin_source)
    if model is None:
        model = getattr(skin_source, "model", "default")
    images = []
    renderer = Minecraft3DRenderer(400, 480)

    for i in range(frames):
        yaw = -30 + i * (360.0 / frames)
        renderer.clear((18, 16, 24, 255))
        renderer.render_model(skin_arr, yaw_deg=yaw, pitch_deg=12, ox=200, oy=320, scale=9, layer_mode=layer_mode, model=model)
        # Crucial: copy the underlying buffer so frames do not share identical memory
        images.append(Image.fromarray(renderer.color_buf.copy()))

    duration_ms = int(1000.0 / fps)
    images[0].save(
        out_path,
        save_all=True,
        append_images=images[1:],
        duration=duration_ms,
        loop=0,
        disposal=2
    )
    return out_path


def render_bottom_up(skin_source, out_path=None, layer_mode="both", model=None):
    """Render 4-angle bottom-up 3D view (looking up from below) to inspect chin, neck, and hood underside."""
    skin_arr = _extract_skin_arr(skin_source)
    if model is None:
        model = getattr(skin_source, "model", "default")
    renderer = Minecraft3DRenderer(1000, 520)
    renderer.clear((18, 16, 24, 255))

    # Angle 1: Front low (looking up at chin & collar)
    renderer.render_model(skin_arr, yaw_deg=0, pitch_deg=-28, ox=140, oy=370, scale=9, layer_mode=layer_mode, model=model)
    # Angle 2: Front 3/4 low
    renderer.render_model(skin_arr, yaw_deg=-35, pitch_deg=-28, ox=380, oy=370, scale=9, layer_mode=layer_mode, model=model)
    # Angle 3: Back 3/4 low
    renderer.render_model(skin_arr, yaw_deg=145, pitch_deg=-28, ox=620, oy=370, scale=9, layer_mode=layer_mode, model=model)
    # Angle 4: Back straight low (looking up at hood rim/underside)
    renderer.render_model(skin_arr, yaw_deg=180, pitch_deg=-28, ox=860, oy=370, scale=9, layer_mode=layer_mode, model=model)

    out = Image.fromarray(renderer.color_buf)
    if out_path:
        out.save(out_path)
        return out_path
    return out


