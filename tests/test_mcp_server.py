"""
Unit and integration test suite for SkinForge MCP Server.
Tests session state, drawing tools, ASCII reverse-engineering, auto-fixing, multimodal rendering, and resources.
"""

import sys
import os
import unittest
import asyncio

# Add SkinForge to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from skinforge.mcp_server import server, session


class TestSkinForgeMCPServer(unittest.TestCase):
    def setUp(self):
        # Reset session before each test and isolate from live project files
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._orig_targets = list(session.project_targets)
        self._orig_file = session.file_path
        session.project_targets = []

    def tearDown(self):
        session.project_targets = list(self._orig_targets)
        session.file_path = self._orig_file
        self.loop.close()

    def call(self, tool_name, args=None):
        return self.loop.run_until_complete(server.call_tool(tool_name, args or {}))

    def test_skin_new_and_session_info(self):
        res = self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})
        self.assertIn("100% solid", res.content[0].text)

        info = self.call("skin_get_session_info", {})
        self.assertIn("Layer 1 (Base Body):", info.content[0].text)
        self.assertIn("100.0% solid", info.content[0].text)

    def test_ascii_get_and_set(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})

        # Get ASCII
        res = self.call("skin_get_part_ascii", {"part_name": "head_front"})
        text = res.content[0].text
        self.assertIn("=== Part: head_front (8x8 px) ===", text)
        self.assertIn("Palette:", text)
        self.assertIn("ASCII Grid:", text)

        # Set custom ASCII
        custom_grid = """
            ########
            #======#
            #==..==#
            #==..==#
            #======#
            #======#
            #======#
            ########
        """
        palette = {
            "#": "#141018",
            "=": "#e0b1b4",
            ".": "transparent",
        }
        res_set = self.call("skin_set_part_ascii", {
            "part_name": "hat_front",
            "ascii_grid": custom_grid,
            "palette": palette
        })
        self.assertIn("Successfully updated 'hat_front'", res_set.content[0].text)

    def test_validation_and_autofix(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})

        # Corrupt Layer 1 holes
        session.canvas.set_pixel("head_front", 3, 3, [0, 0, 0, 0])
        # Corrupt Layer 2 floating profile pixels
        session.canvas.set_pixel("hat_front", 0, 6, [255, 0, 0, 255])

        # Validate detects issues
        val_res = self.call("skin_validate", {})
        val_text = val_res.content[0].text
        self.assertIn("WARNINGS", val_text)
        self.assertIn("Rule 1", val_text)
        self.assertIn("Rule 3", val_text)

        # Auto fix
        fix_res = self.call("skin_auto_fix", {})
        self.assertIn("Healed Layer 1 holes", fix_res.content[0].text)
        self.assertIn("Sanitized Layer 2", fix_res.content[0].text)

        # Validate clean
        val_clean = self.call("skin_validate", {})
        self.assertIn("Zero visual warnings", val_clean.content[0].text)

    def test_multimodal_rendering(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})

        # 3D turnaround
        res3d = self.call("skin_render_3d", {"preset": "turnaround"})
        self.assertEqual(len(res3d.content), 2)
        self.assertEqual(res3d.content[0].type, "text")
        self.assertEqual(res3d.content[1].type, "image")
        self.assertEqual(res3d.content[1].mime_type, "image/png")
        self.assertGreater(len(res3d.content[1].data), 1000)

        # 2D composite
        res2d = self.call("skin_render_2d", {})
        self.assertEqual(len(res2d.content), 2)
        self.assertEqual(res2d.content[1].type, "image")
        self.assertEqual(res2d.content[1].mime_type, "image/png")

        # Zoomed part
        res_part = self.call("skin_render_part", {"part_name": "head_front"})
        self.assertEqual(len(res_part.content), 2)
        self.assertEqual(res_part.content[1].type, "image")

    def test_presets_and_color_ramps(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})

        res_eyes = self.call("skin_apply_preset", {
            "preset_name": "anime_eyes_2x2",
            "params": {"iris_color": "#be50fa"}
        })
        self.assertIn("Successfully applied preset 'anime_eyes_2x2'", res_eyes.content[0].text)

        res_bangs = self.call("skin_apply_preset", {
            "preset_name": "hair_bangs",
            "params": {"hair_color": "#1e1824"}
        })
        self.assertIn("Successfully applied preset 'hair_bangs'", res_bangs.content[0].text)

        res_ramp = self.call("skin_generate_color_ramp", {"base_color": "#be50fa"})
        self.assertIn("Color Ramp for Base '#be50fa':", res_ramp.content[0].text)
        self.assertIn("Copyable ASCII Palette Dict:", res_ramp.content[0].text)

    def test_resources_and_prompts(self):
        resources = self.loop.run_until_complete(server.list_resources())
        resource_uris = [r.uri for r in resources]
        self.assertIn("skin://uv-map", resource_uris)
        self.assertIn("skin://layer-rules", resource_uris)
        self.assertIn("skin://palettes", resource_uris)
        self.assertIn("skin://session-state", resource_uris)

        prompts = self.loop.run_until_complete(server.list_prompts())
        prompt_names = [p.name for p in prompts]
        self.assertIn("create-skin", prompt_names)
        self.assertIn("audit-and-fix-skin", prompt_names)

    def test_sample_reference(self):
        # Create self-contained synthetic test reference image
        tmp_ref = "/tmp/test_synthetic_ref.png"
        from PIL import Image
        img = Image.new("RGB", (40, 40), color=(142, 38, 222))
        img.save(tmp_ref)

        # Test point sampling
        res_pt = self.call("skin_sample_reference", {
            "image_path": tmp_ref,
            "x": 0.5,
            "y": 0.5
        })
        text_pt = res_pt.content[0].text
        self.assertIn("=== Sampled Point at", text_pt)
        self.assertIn("Hex:", text_pt)
        self.assertIn("RGB:", text_pt)

        # Test region crop & palette extraction
        res_pal = self.call("skin_sample_reference", {
            "image_path": tmp_ref,
            "region": [0.11, 0.14, 0.21, 0.28],
            "num_colors": 6
        })
        text_pal = res_pal.content[0].text
        self.assertIn("=== Extracted Palette", text_pal)
        self.assertIn("Ready-to-use ASCII Palette", text_pal)

    def test_replace_color_and_set_pixels(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})

        # Set specific micro pixels
        res_pixels = self.call("skin_set_pixels", {
            "part_name": "head_front",
            "pixels": [
                {"x": 1, "y": 5, "color": "#112233"},
                {"x": 2, "y": 5, "color": "#112233"}
            ]
        })
        self.assertIn("Successfully updated 2 pixel(s)", res_pixels.content[0].text)

        # Replace color with tolerance
        res_rep = self.call("skin_replace_color", {
            "old_color": "#112233",
            "new_color": "#ff00ff",
            "part_name": "head_front",
            "tolerance": 5
        })
        text_rep = res_rep.content[0].text
        self.assertIn("Successfully replaced color", text_rep)
        self.assertIn("Total pixels replaced: 2", text_rep)

    def test_skin_diff_and_list_colors(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})

        # List colors
        res_colors = self.call("skin_list_colors", {"part_name": "head_front", "top_n": 8})
        self.assertIn("=== Top Colors on head_front ===", res_colors.content[0].text)

        # Diff against self
        skin_file = os.path.join(os.path.dirname(__file__), "..", "skins", "skin_syntren.png")
        if not os.path.exists(skin_file):
            custom = os.environ.get("SKINFORGE_DEFAULT_SKIN")
            if custom and os.path.exists(custom):
                skin_file = custom
        if os.path.exists(skin_file):
            self.call("skin_load", {"file_path": skin_file})
            res_diff = self.call("skin_diff", {"other_file_path": skin_file})
            self.assertIn("Status: IDENTICAL", res_diff.content[0].text)
            self.assertIn("Total Differing Pixels: 0", res_diff.content[0].text)

    def test_batch_actions(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})

        actions = [
            {"action": "set_pixel", "part_name": "head_front", "x": 0, "y": 0, "color": "#ff0000"},
            {"action": "draw_rect", "part_name": "hat_front", "x": 0, "y": 0, "width": 4, "height": 2, "color": "#1e1824"},
            {"action": "replace_color", "old_color": "#ff0000", "new_color": "#00ff00", "part_name": "head_front"},
        ]
        res = self.call("skin_batch_actions", {"actions": actions})
        text = res.content[0].text
        self.assertIn("Batch Execution Complete (3/3 succeeded)", text)

    def test_multi_save_and_previews(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})
        tmp_main = "/tmp/test_skin_main.png"
        tmp_sync = "/tmp/test_skin_sync.png"

        res = self.call("skin_save", {
            "file_path": tmp_main,
            "also_export": [tmp_sync],
            "update_previews": False
        })
        self.assertIn("Saved 64x64 skin", res.content[0].text)
        self.assertIn("Synced to:", res.content[0].text)
        self.assertTrue(os.path.exists(tmp_main))
        self.assertTrue(os.path.exists(tmp_sync))

        if os.path.exists(tmp_main):
            os.remove(tmp_main)
        if os.path.exists(tmp_sync):
            os.remove(tmp_sync)

    def test_checkpoints_undo_redo(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})
        res_ckpt = self.call("skin_checkpoint", {"name": "clean_state"})
        self.assertIn("Created checkpoint 'clean_state'", res_ckpt.content[0].text)

        # Modify pixel
        self.call("skin_set_pixel", {"part_name": "head_front", "x": 0, "y": 0, "color": "#ff0000"})
        px_mod = self.call("skin_get_pixel", {"part_name": "head_front", "x": 0, "y": 0})
        self.assertIn("#ff0000", px_mod.content[0].text.lower())

        # Undo
        res_undo = self.call("skin_undo", {})
        self.assertIn("Undid last action", res_undo.content[0].text)
        px_reverted = self.call("skin_get_pixel", {"part_name": "head_front", "x": 0, "y": 0})
        self.assertNotIn("#ff0000", px_reverted.content[0].text.lower())

        # Redo
        res_redo = self.call("skin_redo", {})
        self.assertIn("Redid previous action", res_redo.content[0].text)
        px_redone = self.call("skin_get_pixel", {"part_name": "head_front", "x": 0, "y": 0})
        self.assertIn("#ff0000", px_redone.content[0].text.lower())

        # Restore checkpoint
        res_rest = self.call("skin_restore_checkpoint", {"name": "clean_state"})
        self.assertIn("Successfully restored canvas to checkpoint 'clean_state'", res_rest.content[0].text)
        px_restored = self.call("skin_get_pixel", {"part_name": "head_front", "x": 0, "y": 0})
        self.assertNotIn("#ff0000", px_restored.content[0].text.lower())

    def test_adjust_hsv_and_shift_hue(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})
        self.call("skin_set_pixel", {"part_name": "head_front", "x": 0, "y": 0, "color": "#ff0000"})

        # Shift red (+120 deg) -> green
        res_shift = self.call("skin_shift_hue", {
            "hue_shift": 120.0,
            "part_name": "head_front",
            "target_color": "#ff0000",
            "tolerance": 10
        })
        self.assertIn("Adjusted HSV on head_front", res_shift.content[0].text)
        px = self.call("skin_get_pixel", {"part_name": "head_front", "x": 0, "y": 0})
        self.assertIn("#00ff00", px.content[0].text.lower())

    def test_seams_check_and_align(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})

        # Corrupt an edge pixel on head_front right border
        self.call("skin_set_pixel", {"part_name": "head_front", "x": 7, "y": 2, "color": "#00ff00"})
        self.call("skin_set_pixel", {"part_name": "head_left", "x": 0, "y": 2, "color": "#ff00ff"})

        # Check seams detects it
        res_check = self.call("skin_check_seams", {"tolerance": 20})
        self.assertIn("Seam Continuity Audit", res_check.content[0].text)
        self.assertIn("Head Front-Right", res_check.content[0].text)

        # Align seams heals it
        res_align = self.call("skin_align_seams", {"seam_name": "Head Front-Right", "mode": "blend"})
        self.assertIn("Successfully aligned", res_align.content[0].text)

    def test_typography_and_symbols(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})

        # Draw text
        res_text = self.call("skin_draw_text", {
            "part_name": "jacket_back",
            "text": "S",
            "x": 2,
            "y": 1,
            "color": "#af36f8"
        })
        self.assertIn("Rendered text 'S' on 'jacket_back'", res_text.content[0].text)

        # Draw symbol
        res_sym = self.call("skin_draw_symbol", {
            "part_name": "jacket_back",
            "symbol_name": "cyber_s",
            "x": 1,
            "y": 1,
            "color": "#be50fa"
        })
        self.assertIn("Rendered symbol 'cyber_s' on 'jacket_back'", res_sym.content[0].text)

    def test_turntable_gif_animation(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})
        gif_out = os.path.join(os.path.dirname(__file__), "test_turntable_test.gif")
        res = self.call("skin_render_turntable_gif", {"frames": 16, "fps": 12, "out_path": gif_out})
        self.assertTrue(len(res.content) >= 1)
        self.assertIn("Successfully generated 16-frame turntable GIF", res.content[0].text)
        from PIL import Image
        with Image.open(gif_out) as im:
            self.assertTrue(getattr(im, "is_animated", False))
            self.assertEqual(getattr(im, "n_frames", 1), 16)
        if os.path.exists(gif_out):
            os.remove(gif_out)

    def test_server_instructions(self):
        self.assertIsNotNone(server.instructions)
        self.assertIn("The 4 Golden Rules of Minecraft Skin Depth", server.instructions)
        self.assertIn("UV Face Identifier Reference", server.instructions)
        self.assertIn("Recommended Autonomous Workflow", server.instructions)

    def test_outfit_and_converter(self):
        self.call("skin_new", {"template": "base_body", "skin_tone": "fair"})

        # Apply techwear outfit
        res_outfit = self.call("skin_apply_outfit", {"style": "techwear_hoodie"})
        self.assertIn("Applied outfit 'techwear_hoodie'", res_outfit.content[0].text)

        # Validate outfit compliance
        val_res = self.call("skin_validate", {})
        self.assertIn("Zero visual warnings", val_res.content[0].text)

        # Convert to Alex 3px slim model
        res_conv = self.call("skin_convert_model", {"target_model": "slim"})
        self.assertIn("Successfully converted skin geometry to slim", res_conv.content[0].text)
        self.assertEqual(session.model, "slim")

        # Validate and export slim model without exceptions
        val_slim = self.call("skin_validate", {})
        self.assertIn("Zero visual warnings", val_slim.content[0].text)

        tmp_slim = "/tmp/test_mcp_slim_save.png"
        res_save = self.call("skin_save", {"file_path": tmp_slim, "update_previews": False})
        self.assertIn("Saved 64x64 skin", res_save.content[0].text)
        self.assertTrue(os.path.exists(tmp_slim))
        if os.path.exists(tmp_slim):
            os.remove(tmp_slim)



    def test_skin_build_and_canvas_to_ascii(self):
        from skinforge import canvas_to_ascii
        from skinforge.canvas import SkinCanvas

        src_path = os.path.join(os.path.dirname(__file__), "..", "skins", "skin_syntren.png")
        self.assertTrue(os.path.exists(src_path))

        orig_canvas = SkinCanvas()
        orig_canvas.load_png(src_path)

        palette, parts = canvas_to_ascii(orig_canvas, tolerance=12)
        self.assertGreater(len(palette), 5)
        self.assertGreater(len(parts), 30)

        res = self.call("skin_build", {
            "palette": palette,
            "parts": parts,
            "model_type": "default",
            "auto_fix": True
        })
        self.assertIn("Skin successfully built", res.content[0].text)

        val_res = self.call("skin_validate", {})
        self.assertIn("Zero visual warnings", val_res.content[0].text)

    def test_skin_aesthetic_audit_tool(self):
        # 1. Audit default Syntren skin
        audit_res = self.call("skin_aesthetic_audit", {})
        text = audit_res.content[0].text
        self.assertIn("SkinForge Aesthetic Craftsmanship Audit", text)
        self.assertIn("Craftsmanship Radar Metrics", text)
        self.assertIn("3D Relief Depth", text)
        self.assertIn("Spatial Coherence", text)
        self.assertIn("Hue-Shift Dynamics", text)

        # 2. Session info includes aesthetic score
        info_res = self.call("skin_get_session_info", {})
        info_text = info_res.content[0].text
        self.assertIn("Aesthetic Score", info_text)


if __name__ == "__main__":
    unittest.main()


