import io
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import typing
import unittest
import urllib.request
import warnings
import numpy as np
from PIL import Image

from skinforge import (
    ALL_PARTS,
    BASE_PARTS,
    MAX_HISTORY_STATES,
    MINECRAFT_UV_MAP_CLASSIC,
    MINECRAFT_UV_MAP_SLIM,
    OUTER_PARTS,
    SkinCanvas,
    SkinRAG,
    SkinSession,
    SkinValidator,
    __version__,
    adjust_rgba_hsl,
    adjust_rgba_hsv,
    assemble_skin,
    atomic_save_png,
    auto_fix_skin,
    cielab_to_rgb,
    compute_aesthetic_score,
    compute_visual_similarity,
    convert_legacy_64x32_to_64x64,
    detect_pillow_shading,
    evaluate_golden_rules,
    extract_opaque_rgb,
    extract_visual_features,
    get_rag,
    hsl_to_rgb,
    hsv_to_rgb,
    lookup_uv_coord,
    pack_rag_database,
    render_isolated_module,
    rgb_to_cielab,
    rgb_to_hsl,
    rgb_to_hsv,
)
from skinforge.mcp_server import server, types
from viewer import DaemonThreadingHTTPServer, SkinViewerServer, find_free_port


class TestV1Features(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="skinforge_v13_test_")
        self.canvas_a = SkinCanvas()
        self.canvas_b = SkinCanvas()

        # Color canvas A in red
        for part in self.canvas_a.parts.keys():
            shape = self.canvas_a.parts[part].shape
            self.canvas_a.parts[part] = np.full(shape, (200, 30, 30, 255), dtype=np.uint8)

        # Color canvas B in blue
        for part in self.canvas_b.parts.keys():
            shape = self.canvas_b.parts[part].shape
            self.canvas_b.parts[part] = np.full(shape, (30, 30, 200, 255), dtype=np.uint8)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_version_is_1_3_0(self):
        self.assertEqual(__version__, "1.3.0")

    def test_aesthetic_scorer(self):
        res_flat = compute_aesthetic_score(self.canvas_a)
        self.assertIsInstance(res_flat["score"], float)
        self.assertIn(res_flat["tier"], ["low", "medium", "high", "top_tier"])
        self.assertLess(res_flat["score"], 0.6)

        canvas_complex = SkinCanvas()
        for part in ["head_front", "body_front"]:
            h, w = canvas_complex.parts[part].shape[:2]
            canvas_complex.parts[part] = np.random.randint(50, 220, (h, w, 4), dtype=np.uint8)
            canvas_complex.parts[part][:, :, 3] = 255
        for part in ["hat_front", "jacket_front"]:
            h, w = canvas_complex.parts[part].shape[:2]
            canvas_complex.parts[part] = np.zeros((h, w, 4), dtype=np.uint8)
            canvas_complex.parts[part][:2, :, :] = [180, 50, 220, 255]

        res_c = compute_aesthetic_score(canvas_complex)
        self.assertGreater(res_c["score"], res_flat["score"])

    def test_modular_assembly(self):
        img_a = self.canvas_a.to_image()
        img_b = self.canvas_b.to_image()

        target, result = assemble_skin(
            sources={"hair": img_a, "torso": img_b},
            auto_blend_seams=True,
        )
        self.assertIn("applied_modules", result)
        self.assertIn("hair", result["applied_modules"])
        self.assertIn("torso", result["applied_modules"])
        self.assertGreater(result["aesthetic_score"], 0.0)

        torso_pixel = target.parts["body_front"][2, 2]
        self.assertEqual(int(torso_pixel[2]), 200)

    def test_isolated_module_render(self):
        img_a = self.canvas_a.to_image()
        preview_img = render_isolated_module(img_a, module_name="hair")
        self.assertIsInstance(preview_img, Image.Image)
        self.assertGreater(preview_img.size[0], 64)
        self.assertGreater(preview_img.size[1], 64)

    def test_visual_search_vectors(self):
        img_a = self.canvas_a.to_image()
        img_b = self.canvas_b.to_image()

        vec_a = extract_visual_features(img_a)
        vec_b = extract_visual_features(img_b)

        self.assertEqual(len(vec_a), 299)
        self.assertEqual(len(vec_b), 299)

        sim_self = compute_visual_similarity(vec_a, vec_a)
        self.assertAlmostEqual(sim_self, 1.0, places=4)

        sim_diff = compute_visual_similarity(vec_a, vec_b)
        self.assertLess(sim_diff, 0.9)

        empty_rgba = np.zeros((64, 64, 4), dtype=np.uint8)
        vec_empty = extract_visual_features(empty_rgba)
        self.assertEqual(len(vec_empty), 299)

    def test_rag_v1_tools_integration(self):
        tmp_db = os.path.join(self.tmp_dir, "v1_rag_test.db")
        skins_folder = os.path.join(os.path.dirname(__file__), "..", "skins")
        pack_rag_database(source_path=skins_folder, output_path=tmp_db, overwrite=True)
        rag = SkinRAG(db_path=tmp_db)

        part_results = rag.part_search("hair", "tuxedo", limit=2, min_quality="low")
        self.assertIsInstance(part_results, list)

        quality_results = rag.search("formal", min_quality="low", limit=2)
        self.assertIsInstance(quality_results, list)

        img_a = self.canvas_a.to_image()
        img_results = rag.search_by_image(img_a, limit=2, min_quality="low")
        self.assertIsInstance(img_results, list)
        rag.close()

    def test_alex_slim_model_roundtrip_and_rendering(self):
        from skinforge.converter import convert_skin_model
        from skinforge.renderer import render_3d_turnaround, render_composite_2d

        c = SkinCanvas()
        res_slim = convert_skin_model(c, target_model="slim")
        self.assertEqual(res_slim["status"], "converted")
        self.assertEqual(c.model, "slim")
        self.assertEqual(c.parts["right_arm_front"].shape, (12, 3, 4))
        self.assertEqual(c.parts["right_arm_top"].shape, (4, 3, 4))

        tmp_slim = os.path.join(self.tmp_dir, "test_alex_slim.png")
        c.export_png(tmp_slim)
        self.assertTrue(os.path.exists(tmp_slim))
        with Image.open(tmp_slim) as im_slim:
            self.assertEqual(im_slim.size, (64, 64))

        c_loaded = SkinCanvas(model="slim")
        c_loaded.load_png(tmp_slim)
        self.assertEqual(c_loaded.parts["right_arm_front"].shape, (12, 3, 4))

        res_steve = convert_skin_model(c_loaded, target_model="default")
        self.assertEqual(res_steve["status"], "converted")
        self.assertEqual(c_loaded.model, "default")
        self.assertEqual(c_loaded.parts["right_arm_front"].shape, (12, 4, 4))

        tmp_3d = os.path.join(self.tmp_dir, "test_alex_slim_3d.png")
        tmp_2d = os.path.join(self.tmp_dir, "test_alex_slim_2d.png")
        render_3d_turnaround(c, out_path=tmp_3d)
        render_composite_2d(c, out_path=tmp_2d)
        self.assertTrue(os.path.exists(tmp_3d))
        self.assertTrue(os.path.exists(tmp_2d))

    def test_slim_auto_detection_on_default_canvas(self):
        slim_src = SkinCanvas(model="slim")
        slim_src.fill_part("head_front", "#e0b1b4")
        slim_src.fill_part("body_front", "#1e1824")
        slim_src.fill_part("right_arm_front", "#af36f8")
        slim_src.fill_part("left_arm_front", "#af36f8")
        slim_png = os.path.join(self.tmp_dir, "non_empty_alex.png")
        slim_src.export_png(slim_png)

        default_canvas = SkinCanvas()
        self.assertEqual(default_canvas.model, "default")
        default_canvas.load_png(slim_png)
        self.assertEqual(default_canvas.model, "slim")
        self.assertEqual(default_canvas.parts["right_arm_front"].shape, (12, 3, 4))
        self.assertEqual(default_canvas.parts["left_arm_front"].shape, (12, 3, 4))

    def test_craftsmanship_aesthetic_scorer_v2(self):
        res = compute_aesthetic_score(self.canvas_a)
        self.assertIn("metrics", res)
        m = res["metrics"]
        for key in ["relief_3d", "palette_harmony", "shading_depth", "spatial_coherence", "hue_shifting", "seam_continuity"]:
            self.assertIn(key, m)
            self.assertGreaterEqual(m[key], 0.0)
            self.assertLessEqual(m[key], 1.0)
        self.assertIsInstance(res["recommendations"], list)
        self.assertIsInstance(res["deductions"], list)

        clean_face = np.full((8, 8, 3), 150, dtype=np.uint8)
        self.assertFalse(detect_pillow_shading(clean_face))

        pillow_face = np.full((8, 8, 3), 80, dtype=np.uint8)
        pillow_face[2:6, 2:6] = 230
        self.assertTrue(detect_pillow_shading(pillow_face))

        palette = np.random.randint(0, 256, (50, 3), dtype=np.uint8)
        noise_img = palette[np.random.randint(0, 50, (64, 64))]
        noise_rgba = np.dstack([noise_img, np.full((64, 64), 255, dtype=np.uint8)])
        res_noise = compute_aesthetic_score(noise_rgba)
        self.assertLess(res_noise["metrics"]["spatial_coherence"], 0.95)

    def test_mcp_registered_tools(self):
        tools = server._tool_manager._tools
        for required_tool in (
            "skin_assemble",
            "skin_part_search",
            "skin_search_by_image",
            "skin_search",
            "skin_aesthetic_audit",
            "skin_rag_pack",
            "skin_undo",
            "skin_redo",
            "skin_history",
        ):
            self.assertIn(required_tool, tools)

    def test_uv_single_source_of_truth_and_64x32_legacy_converter(self):
        self.assertEqual(len(BASE_PARTS), 36)
        self.assertEqual(len(OUTER_PARTS), 36)
        self.assertEqual(len(ALL_PARTS), 72)
        self.assertEqual(len(MINECRAFT_UV_MAP_CLASSIC), 72)
        self.assertEqual(len(MINECRAFT_UV_MAP_SLIM), 72)

        hit_head = lookup_uv_coord(10, 10, model="classic")
        self.assertIsNotNone(hit_head)
        self.assertEqual(hit_head["name"], "head_front")
        self.assertEqual(hit_head["layer"], "base")
        self.assertIsNone(lookup_uv_coord(0, 0, model="classic"))

        legacy_32 = np.zeros((32, 64, 4), dtype=np.uint8)
        legacy_32[20:32, 44:48] = [210, 40, 60, 128]
        legacy_32[20:32, 4:8] = [40, 90, 210, 255]
        legacy_32[22, 40] = [255, 220, 0, 255]

        legacy_path = os.path.join(self.tmp_dir, "legacy_64x32.png")
        Image.fromarray(legacy_32, "RGBA").save(legacy_path)

        canvas = SkinCanvas()
        was_legacy = canvas.load_png(legacy_path)
        self.assertTrue(was_legacy)
        self.assertEqual(canvas.to_array().shape, (64, 64, 4))
        self.assertTrue(np.all(canvas.parts["right_arm_front"][:, :, 3] == 255))
        self.assertTrue(np.all(canvas.parts["left_arm_front"][:, :, :3] == [210, 40, 60]))
        self.assertTrue(np.all(canvas.parts["left_leg_front"][:, :, :3] == [40, 90, 210]))
        self.assertEqual(canvas.parts["left_arm_left"][2, 3, :3].tolist(), [255, 220, 0])

    def test_session_thread_safety_atomic_io_and_30_undo_states(self):
        sess = SkinSession(project_root=self.tmp_dir)
        for i in range(35):
            sess.push_undo(action=f"step_{i}")
            sess.canvas.set_pixel("head_front", i % 8, (i // 8) % 8, [i * 5 % 255, 100, 150, 255])

        self.assertEqual(len(sess.undo_stack), MAX_HISTORY_STATES)
        self.assertEqual(MAX_HISTORY_STATES, 30)
        self.assertEqual(sess.undo_stack[0].action, "step_5")
        self.assertEqual(sess.undo_stack[-1].action, "step_34")

        out_png = os.path.join(self.tmp_dir, "atomic_test.png")
        atomic_save_png(sess.canvas.to_image(), out_png)
        self.assertTrue(os.path.exists(out_png))
        tmp_files = [f for f in os.listdir(self.tmp_dir) if f.endswith(".tmp")]
        self.assertEqual(tmp_files, [])

        errors = []

        def worker(tid: int):
            try:
                for step in range(10):
                    sess.push_undo(action=f"t{tid}_{step}")
                    with sess.lock:
                        sess.canvas.set_pixel("body_front", tid % 8, step % 12, [tid * 30 % 255, step * 20 % 255, 180, 255])
                    sess.mark_dirty()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

    def test_vectorized_color_engine_and_alpha_zero_ignoring(self):
        test_rgb = np.array([
            [0, 0, 0],
            [255, 255, 255],
            [128, 128, 128],
            [255, 0, 0],
            [0, 255, 0],
            [0, 0, 255],
            [175, 54, 248],
            [24, 180, 130],
        ], dtype=np.uint8)

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            hsv = rgb_to_hsv(test_rgb)
            rgb_from_hsv = hsv_to_rgb(hsv)
            hsl = rgb_to_hsl(test_rgb)
            rgb_from_hsl = hsl_to_rgb(hsl)
            lab = rgb_to_cielab(test_rgb)
            rgb_from_lab = cielab_to_rgb(lab)

        np.testing.assert_allclose(rgb_from_hsv, test_rgb, atol=1)
        np.testing.assert_allclose(rgb_from_hsl, test_rgb, atol=1)
        np.testing.assert_allclose(rgb_from_lab, test_rgb, atol=2)

        rgba = np.zeros((4, 4, 4), dtype=np.uint8)
        rgba[0, 0] = [255, 50, 50, 0]
        rgba[1, 1] = [100, 150, 200, 255]

        opaque_only = extract_opaque_rgb(rgba)
        self.assertEqual(len(opaque_only), 1)
        self.assertEqual(opaque_only[0].tolist(), [100, 150, 200])

        adjusted_hsv, cnt_hsv = adjust_rgba_hsv(rgba, hue_shift=90.0, sat_mult=50.0, val_mult=50.0)
        self.assertEqual(cnt_hsv, 1)
        self.assertEqual(adjusted_hsv[0, 0].tolist(), [255, 50, 50, 0])

        adjusted_hsl, cnt_hsl = adjust_rgba_hsl(rgba, hue_shift=45.0, sat_mult=10.0, light_mult=10.0)
        self.assertEqual(cnt_hsl, 1)
        self.assertEqual(adjusted_hsl[0, 0].tolist(), [255, 50, 50, 0])

    def test_four_golden_rules_and_auto_fix(self):
        c = SkinCanvas()
        for p in BASE_PARTS:
            c.fill_part(p, "#3a2e4d")
        c.set_pixel("head_front", 3, 3, [0, 0, 0, 0])
        c.set_pixel("body_front", 4, 5, [0, 0, 0, 0])

        for p in OUTER_PARTS:
            c.fill_part(p, "#9a32dc")

        c.set_pixel("hat_front", 2, 4, "#ff0055")
        c.set_pixel("hat_front", 5, 6, "#ff0055")

        c.fill_part("hat_top", [0, 0, 0, 0])
        for x in range(5):
            c.set_pixel("hat_top", x, 0, "#ffffff")

        before_rules = evaluate_golden_rules(c.to_array(), model=c.model)
        self.assertFalse(before_rules["all_passed"])
        self.assertFalse(before_rules["rule1_zero_holes"]["passed"])
        self.assertFalse(before_rules["rule2_relief_depth"]["passed"])
        self.assertFalse(before_rules["rule3_hat_front"]["passed"])
        self.assertFalse(before_rules["rule4_hat_top"]["passed"])

        fix_res = auto_fix_skin(c, ensure_relief=True)
        after_rules = fix_res["golden_rules"]
        self.assertTrue(after_rules["all_passed"])
        self.assertTrue(after_rules["rule1_zero_holes"]["passed"])
        self.assertTrue(after_rules["rule2_relief_depth"]["passed"])
        self.assertTrue(after_rules["rule3_hat_front"]["passed"])
        self.assertTrue(after_rules["rule4_hat_top"]["passed"])

        self.assertEqual(int(np.sum(c.parts["hat_front"][4:8, :, 3] > 0)), 0)
        self.assertEqual(int(np.sum(c.parts["hat_top"][:, :, 3] > 0)), 0)

    def test_viewer_sse_and_fallback_endpoints(self):
        port = find_free_port(18920)
        httpd = DaemonThreadingHTTPServer(("127.0.0.1", port), SkinViewerServer)
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/events?once=1", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("text/event-stream", resp.headers.get("Content-Type", ""))
                body = resp.read().decode("utf-8")
                self.assertIn("event: skin_update", body)
                data_line = [line for line in body.split("\n") if line.startswith("data: ")][0]
                payload = json.loads(data_line[len("data: "):])
                self.assertIn("audit", payload)
                self.assertIn("uv_map", payload)
                self.assertIn("golden_rules", payload["audit"])

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                status_data = json.loads(resp.read().decode("utf-8"))
                self.assertIn("mtime", status_data)
                self.assertIn("model", status_data)

            for route in ("/", "/static/app.js", "/static/style.css"):
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{route}", timeout=5) as resp:
                    self.assertEqual(resp.status, 200)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_type_hints_and_ingest_init_db(self):
        import viewer
        import skinforge.audit.aesthetic as aesthetic_mod
        import scripts.ingest_full_dataset as ingest_mod

        hints_aes = typing.get_type_hints(aesthetic_mod._extract_canvas_array)
        self.assertIn("return", hints_aes)
        hints_sse = typing.get_type_hints(viewer.SSEBroadcaster.__init__)
        self.assertIsInstance(hints_sse, dict)

        conn = sqlite3.connect(":memory:")
        ingest_mod.init_db(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(skins);").fetchall()}
        self.assertIn("feature_vec", cols)
        self.assertIn("layer2_ratio", cols)
        self.assertIn("quality_score", cols)
        conn.close()

    def test_instructions_sync_and_jsonrpc_stdio_loop(self):
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with open(os.path.join(root_dir, "instructions.md"), "r", encoding="utf-8") as f1:
            inst1 = f1.read()
        with open(os.path.join(root_dir, "skinforge", "instructions.md"), "r", encoding="utf-8") as f2:
            inst2 = f2.read()
        self.assertEqual(inst1, inst2)
        self.assertIn('skin_part_search(category, query, limit=5, min_quality="medium", render_previews=True)', inst1)
        self.assertIn("skin_assemble(components=", inst1)
        self.assertIn("skin_rag_pack", inst1)
        self.assertIn("skin_history", inst1)
        self.assertIn("SSE real-time live sync viewer (/api/events)", inst1)

        ic = types.ImageContent(type="image", data="YWJj", mime_type="image/png")
        self.assertEqual(getattr(ic, "mime_type", None), "image/png")
        self.assertEqual(getattr(ic, "mimeType", None), "image/png")

        if hasattr(server, "handle_jsonrpc_request"):
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "skin_list_palettes", "arguments": {}}},
                {"jsonrpc": "2.0", "id": 4, "method": "resources/list"},
                {"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": {"uri": "skin://layer-rules"}},
                {"jsonrpc": "2.0", "id": 6, "method": "prompts/list"},
                {"jsonrpc": "2.0", "id": 7, "method": "prompts/get", "params": {"name": "create-skin"}},
            ]
            in_stream = io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n")
            out_stream = io.StringIO()
            server.run("stdio", input_stream=in_stream, output_stream=out_stream)

            responses = [json.loads(line) for line in out_stream.getvalue().strip().split("\n") if line.strip()]
            self.assertEqual(len(responses), 7)
            self.assertEqual(responses[0]["id"], 1)
            self.assertEqual(responses[0]["result"]["serverInfo"]["version"], "1.3.0")
            self.assertGreater(len(responses[1]["result"]["tools"]), 25)
            self.assertIn("TECHWEAR_CYBERPUNK", responses[2]["result"]["content"][0]["text"])
            self.assertEqual(len(responses[3]["result"]["resources"]), 4)
            self.assertIn("Rule 1", responses[4]["result"]["contents"][0]["text"])
            self.assertEqual(len(responses[5]["result"]["prompts"]), 2)
            self.assertGreaterEqual(len(responses[6]["result"]["messages"]), 1)


if __name__ == "__main__":
    unittest.main()
