import unittest
import numpy as np
from PIL import Image

from skinforge.canvas import SkinCanvas
from skinforge.validator import compute_aesthetic_score, SkinValidator
from skinforge.modular import assemble_skin, render_isolated_module
from skinforge.vision import extract_visual_features, compute_visual_similarity
from skinforge.rag import get_rag
from skinforge.mcp_server import server

class TestV1Features(unittest.TestCase):
    def setUp(self):
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

    def test_aesthetic_scorer(self):
        # Empty / flat canvas should have low aesthetic score
        res_flat = compute_aesthetic_score(self.canvas_a)
        self.assertIsInstance(res_flat['score'], float)
        self.assertIn(res_flat['tier'], ['low', 'medium', 'high', 'top_tier'])
        self.assertLess(res_flat['score'], 0.6)

        # Skin with Layer 2 details and variance
        canvas_complex = SkinCanvas()
        for part in ['head_front', 'body_front']:
            h, w = canvas_complex.parts[part].shape[:2]
            # Add colored pixels with variance
            canvas_complex.parts[part] = np.random.randint(50, 220, (h, w, 4), dtype=np.uint8)
            canvas_complex.parts[part][:, :, 3] = 255
        # Add layer 2 details
        for part in ['hat_front', 'jacket_front']:
            h, w = canvas_complex.parts[part].shape[:2]
            canvas_complex.parts[part] = np.zeros((h, w, 4), dtype=np.uint8)
            canvas_complex.parts[part][:2, :, :] = [180, 50, 220, 255] # relief bangs / rim

        res_c = compute_aesthetic_score(canvas_complex)
        self.assertGreater(res_c['score'], res_flat['score'])

    def test_modular_assembly(self):
        img_a = self.canvas_a.to_image()
        img_b = self.canvas_b.to_image()
        
        target, result = assemble_skin(
            sources={
                'hair': img_a,
                'torso': img_b
            },
            auto_blend_seams=True
        )
        self.assertIn('applied_modules', result)
        self.assertIn('hair', result['applied_modules'])
        self.assertIn('torso', result['applied_modules'])
        self.assertGreater(result['aesthetic_score'], 0.0)

        # Verify torso parts match canvas B (blue)
        torso_pixel = target.parts['body_front'][2, 2]
        self.assertEqual(int(torso_pixel[2]), 200) # Blue channel

    def test_isolated_module_render(self):
        img_a = self.canvas_a.to_image()
        preview_img = render_isolated_module(img_a, module_name='hair')
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

        # Self similarity should be ~1.0
        sim_self = compute_visual_similarity(vec_a, vec_a)
        self.assertAlmostEqual(sim_self, 1.0, places=4)

        # Different colors similarity should be noticeably lower
        sim_diff = compute_visual_similarity(vec_a, vec_b)
        self.assertLess(sim_diff, 0.9)

    def test_rag_v1_tools_integration(self):
        rag = get_rag()
        if not rag.is_available:
            self.skipTest('RAG SQLite DB not available')

        # Part search
        part_results = rag.part_search('hair', 'tuxedo', limit=2)
        self.assertIsInstance(part_results, list)

        # Search with min_quality
        quality_results = rag.search('formal', min_quality='medium', limit=2)
        self.assertIsInstance(quality_results, list)

        # Image search
        img_a = self.canvas_a.to_image()
        img_results = rag.search_by_image(img_a, limit=2)
        self.assertIsInstance(img_results, list)

    def test_mcp_registered_tools(self):
        tools = server._tool_manager._tools
        self.assertIn('skin_assemble', tools)
        self.assertIn('skin_part_search', tools)
        self.assertIn('skin_search_by_image', tools)
        self.assertIn('skin_search', tools)

if __name__ == '__main__':
    unittest.main()
