"""
Unit and integration tests for SkinForge RAG v1.3.0:
- Graceful degradation when database is absent/empty
- Database packing (`pack_rag_database` / `skin_rag_pack`) from folder (.png + .json) and archive (.zip + .csv)
- Automatic 64x32 -> 64x64 legacy conversion during RAG packing
- 299-dim CIELAB float16 BLOB serialization & visual similarity search
- FTS5 BM25 search, part search, reference retrieval, and skin remixing
"""

import io
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
import zipfile
import numpy as np
from PIL import Image

from skinforge import (
    FEATURE_DIM,
    SkinCanvas,
    SkinRAG,
    apply_outfit,
    create_base_body,
    get_rag,
    pack_rag_database,
    set_rag_db_path,
    unpack_feature_blob,
)


def _make_sample_skin(skin_tone: str, style: str, accent: str) -> Image.Image:
    c = SkinCanvas()
    create_base_body(c, skin_tone=skin_tone, eye_color=accent)
    apply_outfit(c, style=style, accent_color=accent)
    c.heal_layer1_holes()
    c.sanitize_outer_layer(ensure_relief=True)
    return c.to_image()


class TestSkinRAG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(prefix="skinforge_rag_test_")
        cls.skins_dir = os.path.join(cls.tmp_dir, "raw_skins")
        os.makedirs(cls.skins_dir, exist_ok=True)

        # Create 4 rich 64x64 skins and 1 legacy 64x32 skin for packing
        s1 = _make_sample_skin("fair", "techwear_hoodie", "#af36f8")
        s2 = _make_sample_skin("pale", "cargo_streetwear", "#00e5ff")
        s3 = _make_sample_skin("tan", "casual_tshirt", "#f59e0b")
        s4 = _make_sample_skin("dark", "techwear_hoodie", "#10b981")

        s1.save(os.path.join(cls.skins_dir, "skin_samurai.png"))
        s2.save(os.path.join(cls.skins_dir, "skin_ninja.png"))
        s3.save(os.path.join(cls.skins_dir, "skin_armor_tuxedo.png"))
        s4.save(os.path.join(cls.skins_dir, "skin_formal_suit.png"))

        # Legacy 64x32 skin
        legacy_arr = np.array(s1)[:32, :64, :].copy()
        Image.fromarray(legacy_arr, "RGBA").save(os.path.join(cls.skins_dir, "skin_legacy_knight.png"))

        metadata = [
            {
                "skin_id": "skin_samurai",
                "title": "Cyberpunk Street Samurai",
                "caption": "cyberpunk samurai warrior with neon purple hoodie and katana armor",
                "tags": ["samurai", "cyberpunk", "armor", "purple"],
                "model_type": "default",
            },
            {
                "skin_id": "skin_ninja",
                "title": "Shadow Ninja",
                "caption": "stealth ninja assassin with cyan scarf and dark armor",
                "tags": ["ninja", "stealth", "armor", "cyan"],
                "model_type": "default",
            },
            {
                "skin_id": "skin_armor_tuxedo",
                "title": "Armored Formal Tuxedo",
                "caption": "formal tuxedo suit with golden armor trim and blazer",
                "tags": ["tuxedo", "formal", "armor", "suit"],
                "model_type": "default",
            },
            {
                "skin_id": "skin_formal_suit",
                "title": "Emerald Formal Executive",
                "caption": "formal business suit tuxedo with emerald tie and tailored hair",
                "tags": ["formal", "tuxedo", "hair", "suit"],
                "model_type": "default",
            },
            {
                "skin_id": "skin_legacy_knight",
                "title": "Classic 64x32 Knight Armor",
                "caption": "classic medieval knight armor converted from 64x32 legacy skin",
                "tags": ["knight", "armor", "samurai", "legacy"],
                "model_type": "default",
            },
        ]
        cls.meta_json_path = os.path.join(cls.tmp_dir, "metadata.json")
        with open(cls.meta_json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        cls.db_path = os.path.join(cls.tmp_dir, "test_skins.sfpack")
        cls.pack_result = pack_rag_database(
            source_path=cls.skins_dir,
            output_path=cls.db_path,
            metadata_path=cls.meta_json_path,
            min_score=0.0,
            overwrite=True,
        )
        cls.rag = get_rag()

    @classmethod
    def tearDownClass(cls):
        if cls.rag is not None:
            cls.rag.close()
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def test_graceful_degradation_when_db_missing(self):
        """Verify RAG does not crash when database file is missing and returns skin_rag_pack instructions."""
        missing_path = os.path.join(self.tmp_dir, "nonexistent_dir", "missing.db")
        empty_rag = SkinRAG(db_path=missing_path)
        self.assertFalse(empty_rag.is_available)
        self.assertEqual(empty_rag.count(), 0)
        self.assertEqual(empty_rag.search("samurai"), [])
        self.assertEqual(empty_rag.part_search("hair", "samurai"), [])

        info = empty_rag.get_unavailable_info() if hasattr(empty_rag, "get_unavailable_info") else empty_rag.get_unavailable_response("samurai")
        self.assertEqual(info["status"], "db_not_initialized")
        self.assertFalse(info["available"])
        self.assertIn("skin_rag_pack", info["message"])
        self.assertIn("skin_rag_pack", info["instructions"]["mcp_tool"])

    def test_rag_pack_folder_and_schema_blobs(self):
        """Verify pack_rag_database validates skins, converts 64x32, and stores PNG + float16 299-dim CIELAB BLOBs."""
        self.assertEqual(self.pack_result["status"], "success")
        self.assertEqual(self.pack_result["packed_count"], 5)
        self.assertEqual(self.pack_result["converted_legacy_64x32"], 1)
        self.assertEqual(self.pack_result["feature_vector_dim"], 299)
        self.assertEqual(self.pack_result["feature_vector_dtype"], "float16")
        self.assertGreater(self.rag.count(), 0)

        # Inspect raw SQLite row to verify float16 BLOB size (299 * 2 = 598 bytes) and 64x64 PNG BLOB
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT image_bytes, feature_vec, quality_score, quality_tier FROM skins WHERE skin_id = 'skin_legacy_knight';"
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        img_bytes, feat_blob, q_score, q_tier = row
        self.assertEqual(len(feat_blob), FEATURE_DIM * 2)  # 598 bytes
        vec = unpack_feature_blob(feat_blob)
        self.assertEqual(vec.shape, (299,))
        self.assertAlmostEqual(float(np.linalg.norm(vec)), 1.0, places=3)

        with Image.open(io.BytesIO(img_bytes)) as im:
            self.assertEqual(im.size, (64, 64))
        self.assertGreater(q_score, 0.0)
        self.assertIn(q_tier, ("low", "medium", "high", "top_tier"))

    def test_rag_pack_from_zip_with_csv_metadata(self):
        """Verify packing directly from a .zip archive with .csv metadata into a .sfpack file."""
        zip_path = os.path.join(self.tmp_dir, "skins_bundle.zip")
        csv_content = "skin_id,title,caption,tags,model_type\nskin_samurai,Zip Samurai,zip samurai warrior,samurai zip,default\n"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(os.path.join(self.skins_dir, "skin_samurai.png"), arcname="skin_samurai.png")
            zf.writestr("metadata.csv", csv_content)

        out_zip_db = os.path.join(self.tmp_dir, "zip_packed.sfpack")
        res = pack_rag_database(source_path=zip_path, output_path=out_zip_db, overwrite=True)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["packed_count"], 1)

        # Restore main test DB as singleton
        set_rag_db_path(self.db_path)

    def test_format_fts_query(self):
        """Verify query formatting for FTS5."""
        q = self.rag.format_fts_query("Cyberpunk street samurai with purple scarf")
        self.assertIn('"cyberpunk"*', q)
        self.assertIn('"samurai"*', q)
        self.assertNotIn('"with"*', q)

    def test_search_skins(self):
        """Verify search returns matching skins with 3D turnaround preview."""
        results = self.rag.search("samurai", limit=2, min_quality="low", render_previews=True, preview_dir=self.tmp_dir)
        self.assertGreaterEqual(len(results), 1)
        res = results[0]
        self.assertIn("skin_id", res)
        self.assertIn("caption", res)
        self.assertIn("preview_3d_path", res)
        self.assertTrue(os.path.exists(res["preview_3d_path"]))

    def test_get_skin(self):
        """Verify retrieving a skin by ID with ASCII breakdown."""
        results = self.rag.search("ninja", limit=1, min_quality="low", render_previews=False)
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
        results = self.rag.search("armor", limit=2, min_quality="low", render_previews=False)
        self.assertGreaterEqual(len(results), 2)
        base_id = results[0]["skin_id"]
        overlay_id = results[1]["skin_id"]

        out_preview = os.path.join(self.tmp_dir, "remix_test_3d.png")
        canvas, info = self.rag.remix_skins(base_id, overlay_id, auto_fix=True, save_path=out_preview)
        self.assertIsNotNone(canvas)
        self.assertIn("preview_3d", info)
        self.assertTrue(os.path.exists(info["preview_3d"]))


if __name__ == "__main__":
    unittest.main()
