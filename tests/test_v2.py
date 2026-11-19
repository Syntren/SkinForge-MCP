import asyncio
import json
import os
import shutil
import tempfile
import unittest
import numpy as np

from skinforge import (
    OUTFIT_STYLES,
    PALETTE_REGISTRY,
    PRESET_REGISTRY,
    SHADING_STYLES,
    SkinCanvas,
    __version__,
    auto_shade_skin,
    compute_aesthetic_score,
    draw_primitive,
    generate_harmonious_palette,
    paint_region,
)
from skinforge.mcp_server import server, session


class TestV2AIFirstFeatures(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="skinforge_v2_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _run_tool(self, name, args=None):
        res = asyncio.run(server.call_tool(name, args or {}))
        return res.content

    def test_version_and_tool_count(self):
        self.assertEqual(__version__, "2.0.0")
        tools = server._tool_manager._tools
        self.assertEqual(len(tools), 63)
        for expected in (
            "skin_auto_shade",
            "skin_paint_region",
            "skin_draw_primitive",
            "skin_generate_palette",
            "skin_inspect_blueprint",
            "skin_critic",
        ):
            self.assertIn(expected, tools)

    def test_hue_shifted_auto_shading_improves_flat_skin_and_preserves_alpha(self):
        c = SkinCanvas()
        # Fill base solid flat color, leave outer mostly transparent except bangs
        for part in c.parts:
            if not part.startswith(("hat_", "jacket_", "right_sleeve_", "left_sleeve_", "right_pants_", "left_pants_")):
                c.fill_part(part, "#3a4f7a")
        c.draw_rect("hat_front", 0, 0, 8, 2, "#242836")

        before = compute_aesthetic_score(c)
        res = auto_shade_skin(c, target="base", style="directional", strength=0.40, hue_shift_deg=22.0, dither=True)
        after = compute_aesthetic_score(c)

        self.assertGreater(res["shaded_pixels"], 1000)
        self.assertGreater(after["metrics"]["shading_depth"], before["metrics"]["shading_depth"])
        # Verify alpha == 0 pixels on hat_front rows 4..7 remained strictly transparent
        self.assertEqual(int(np.sum(c.parts["hat_front"][4:, :, 3] > 0)), 0)

        # Verify all 6 shading styles run cleanly
        for style in SHADING_STYLES:
            r = auto_shade_skin(c, target="head_front", style=style, strength=0.25)
            self.assertEqual(r["shaded_pixels"], 64)

    def test_semantic_region_painter_and_primitives(self):
        c = SkinCanvas()
        res = paint_region(c, region="torso", color="#223355", secondary_color="#446699", pattern="vertical_gradient")
        self.assertEqual(res["modified_parts_count"], 6)
        self.assertGreater(res["pixels_painted"], 200)

        # Wrap-around stripe band on legs
        band = paint_region(c, region="legs", color="#ff3366", row_start=4, row_end=6, include_caps=False)
        self.assertEqual(band["modified_parts_count"], 8)
        self.assertEqual(c.get_pixel("right_leg_front", 0, 4)[:3], [255, 51, 102])

        # 2D Primitives: line, outline, flood_fill, dither_rect, mirror_x
        c.fill_part("head_front", "#e0b0a0")
        draw_primitive(c, "head_front", "line", x0=0, y0=0, x1=3, y1=3, color="#112233")
        self.assertEqual(c.get_pixel("head_front", 0, 0)[:3], [17, 34, 51])
        self.assertEqual(c.get_pixel("head_front", 3, 3)[:3], [17, 34, 51])

        draw_primitive(c, "head_front", "mirror_x", direction="left_to_right")
        self.assertEqual(c.get_pixel("head_front", 7, 0)[:3], [17, 34, 51])
        self.assertEqual(c.get_pixel("head_front", 4, 3)[:3], [17, 34, 51])

        draw_primitive(c, "body_front", "outline", x0=1, y0=1, width=6, height=6, color="#ffffff")
        self.assertEqual(c.get_pixel("body_front", 1, 1)[:3], [255, 255, 255])

        ff = draw_primitive(c, "body_front", "flood_fill", x0=3, y0=3, color="#00ff88", tolerance=40)
        self.assertGreater(ff["pixels_changed"], 0)
        self.assertEqual(c.get_pixel("body_front", 3, 3)[:3], [0, 255, 136])

        dr = draw_primitive(c, "jacket_front", "dither_rect", x0=0, y0=0, width=4, height=4, color="#ff0000", secondary_color="#0000ff")
        self.assertEqual(dr["pixels_changed"], 16)

    def test_harmonious_palette_generator_and_new_outfits_and_presets(self):
        pal = generate_harmonious_palette("#7c3aed", harmony="cyberpunk")
        self.assertIn("ascii_palette", pal)
        self.assertIn("outfit_args", pal)
        self.assertIn("CYBER_NINJA", PALETTE_REGISTRY)
        self.assertIn("COZY_PASTEL", PALETTE_REGISTRY)
        self.assertGreaterEqual(len(OUTFIT_STYLES), 7)
        self.assertGreaterEqual(len(PRESET_REGISTRY), 10)

        # Verify all new outfits & presets work via MCP tools without Golden Rules violations
        for outfit in ("fantasy_knight", "cyber_ninja", "formal_suit", "cozy_sweater"):
            self._run_tool("skin_new", {"template": "base_body"})
            out = self._run_tool("skin_apply_outfit", {"style": outfit})
            self.assertIn(outfit, out[0].text)

        for preset in ("visor_glasses", "crown", "scarf", "blush_and_mouth"):
            out = self._run_tool("skin_apply_preset", {"preset_name": preset})
            self.assertIn(preset, out[0].text)

    def test_blueprint_inspector_critic_and_batch_preview_mcp_flow(self):
        self._run_tool("skin_new", {"template": "base_body", "skin_tone": "anime"})
        batch_out = self._run_tool(
            "skin_batch_actions",
            {
                "actions": [
                    {"action": "apply_outfit", "style": "cyber_ninja", "primary_color": "#161c28", "secondary_color": "#263044", "accent_color": "#00d4ff", "trim_color": "#f0f4ff"},
                    {"action": "apply_preset", "preset_name": "hair_bangs", "params": {"hair_color": "#181c26", "highlight_color": "#00d4ff"}},
                    {"action": "auto_shade", "target": "base", "style": "directional", "strength": 0.35, "hue_shift_deg": 20.0},
                    {"action": "align_seams", "seam_name": "all", "mode": "blend"},
                    {"action": "auto_fix"},
                ],
                "return_preview": True,
            },
        )
        self.assertEqual(len(batch_out), 2)
        self.assertIn("5/5 succeeded", batch_out[0].text)
        self.assertEqual(batch_out[1].type, "image")

        # Blueprint Inspector
        bp_raw = self._run_tool("skin_inspect_blueprint", {"include_ascii_region": "head"})[0].text
        bp = json.loads(bp_raw)
        self.assertEqual(bp["status"], "success")
        self.assertTrue(bp["golden_rules_passed"])
        self.assertIn("head_front", bp["ascii_parts"])

        # Multimodal Critic
        critic_out = self._run_tool("skin_critic", {})
        self.assertEqual(len(critic_out), 2)
        self.assertIn("SkinForge v2.0 Multimodal Critic", critic_out[0].text)
        self.assertEqual(critic_out[1].type, "image")

    def test_fuzzy_part_name_suggestions(self):
        err_out = self._run_tool("skin_fill_part", {"part_name": "head_frnt", "color": "#ff0000"})[0].text
        self.assertIn("Did you mean", err_out)
        self.assertIn("head_front", err_out)


if __name__ == "__main__":
    unittest.main()
