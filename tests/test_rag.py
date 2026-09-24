"""Unit tests for SkinForge RAG search, retrieval, and remixing."""

import os
import unittest
from skinforge.rag import SkinRAG, get_rag


class TestSkinRAG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rag = get_rag()

    def test_rag_database_exists_and_populated(self):
        """Verify that the RAG SQLite database exists and has indexed skins."""
        count = self.rag.count()
        self.assertGreater(count, 0, "RAG database should contain indexed skins")

    def test_format_fts_query(self):
        """Verify query formatting for FTS5."""
        q = self.rag.format_fts_query("Cyberpunk street samurai with purple scarf")
        self.assertIn('"cyberpunk"*', q)
        self.assertIn('"samurai"*', q)
        self.assertNotIn('"with"*', q)  # Stop word removed

    def test_search_skins(self):
        """Verify search returns matching skins with 3D turnaround preview."""
        results = self.rag.search("samurai", limit=2, render_previews=True)
        self.assertGreaterEqual(len(results), 1)
        res = results[0]
        self.assertIn("skin_id", res)
        self.assertIn("caption", res)
        self.assertIn("preview_3d_path", res)
        self.assertTrue(os.path.exists(res["preview_3d_path"]))

    def test_get_skin(self):
        """Verify retrieving a skin by ID with ASCII breakdown."""
        results = self.rag.search("ninja", limit=1, render_previews=False)
        self.assertTrue(len(results) > 0)
        skin_id = results[0]["skin_id"]

        data = self.rag.get_skin(skin_id, as_canvas=True, as_ascii=True)
        self.assertIsNotNone(data)
        self.assertEqual(data["skin_id"], skin_id)
        self.assertIn("palette", data)
        self.assertIn("parts", data)
        self.assertIn("canvas", data)
        self.assertIn("head_front", data["parts"])

    def test_remix_skins(self):
        """Verify remixing two skins together."""
        results = self.rag.search("armor", limit=2, render_previews=False)
        self.assertGreaterEqual(len(results), 2)
        base_id = results[0]["skin_id"]
        overlay_id = results[1]["skin_id"]

        canvas, info = self.rag.remix_skins(base_id, overlay_id, auto_fix=True)
        self.assertIsNotNone(canvas)
        self.assertIn("preview_3d", info)
        self.assertTrue(os.path.exists(info["preview_3d"]))


if __name__ == "__main__":
    unittest.main()
