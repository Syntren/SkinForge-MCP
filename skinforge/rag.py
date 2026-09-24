"""
SkinForge RAG - Retrieval-Augmented Generation & Reference Search for Minecraft Skins.

Provides fast, native search across 900,000+ captioned Minecraft skins using
SQLite FTS5 (BM25 ranking), on-the-fly 3D previews, palette extraction,
and intelligent skin remixing for LLMs and autonomous agents.
"""

import os
import io
import re
import time
import base64
import sqlite3
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image

from .canvas import SkinCanvas, MINECRAFT_UV_MAP
from .renderer import render_3d_turnaround, render_composite_2d
from .ascii_codec import canvas_to_ascii

# Default paths
DEFAULT_DB_DIR = Path(__file__).parent.parent / "data"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "skins_rag.db"
DEFAULT_PREVIEW_DIR = Path(__file__).parent.parent / "previews"

STOP_WORDS = {
    "a", "an", "the", "with", "and", "or", "in", "on", "at", "to", "for",
    "of", "is", "character", "skin", "minecraft", "game", "video", "depicted",
    "image", "features", "style", "appears", "popular"
}


class SkinRAG:
    """Retrieval-Augmented Generation engine for Minecraft Skins."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """Initialize SQLite tables and FTS5 full-text search index."""
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS skins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skin_id TEXT UNIQUE,
                title TEXT,
                caption TEXT,
                image_bytes BLOB,
                model_type TEXT DEFAULT 'default',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS skins_fts USING fts5(
                skin_id UNINDEXED,
                title,
                caption,
                content=skins,
                content_rowid=id
            );
        """)
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS skins_ai AFTER INSERT ON skins BEGIN
                INSERT INTO skins_fts(rowid, skin_id, title, caption)
                VALUES (new.id, new.skin_id, new.title, new.caption);
            END;
        """)
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS skins_ad AFTER DELETE ON skins BEGIN
                INSERT INTO skins_fts(skins_fts, rowid, skin_id, title, caption)
                VALUES('delete', old.id, old.skin_id, old.title, old.caption);
            END;
        """)
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS skins_au AFTER UPDATE ON skins BEGIN
                INSERT INTO skins_fts(skins_fts, rowid, skin_id, title, caption)
                VALUES('delete', old.id, old.skin_id, old.title, old.caption);
                INSERT INTO skins_fts(rowid, skin_id, title, caption)
                VALUES (new.id, new.skin_id, new.title, new.caption);
            END;
        """)
        self.conn.commit()

    def count(self) -> int:
        """Return total number of indexed skins."""
        res = self.conn.execute("SELECT count(*) FROM skins;").fetchone()
        return res[0] if res else 0

    def format_fts_query(self, query: str) -> str:
        """Sanitize and format query into high-recall FTS5 prefix match string."""
        tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())
        meaningful = [t for t in tokens if t not in STOP_WORDS and len(t) > 1]
        if not meaningful:
            meaningful = tokens
        if not meaningful:
            return "*"
        # Match each meaningful token as prefix or full word
        return " OR ".join(f'"{t}"*' for t in meaningful)

    def search(
        self,
        query: str,
        limit: int = 5,
        render_previews: bool = True,
        preview_dir: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for skins matching the query using BM25 relevance ranking.
        Optionally generates 3D turnaround and 2D composite previews.
        """
        if self.count() == 0:
            return []

        fts_q = self.format_fts_query(query)
        sql = """
            SELECT s.id, s.skin_id, s.title, s.caption, s.image_bytes, s.model_type, bm25(skins_fts) as rank
            FROM skins_fts
            JOIN skins s ON s.id = skins_fts.rowid
            WHERE skins_fts MATCH ?
            ORDER BY rank
            LIMIT ?;
        """
        rows = self.conn.execute(sql, (fts_q, limit)).fetchall()

        out_dir = Path(preview_dir) if preview_dir else DEFAULT_PREVIEW_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for r in rows:
            skin_id = r["skin_id"]
            img_bytes = r["image_bytes"]
            caption = r["caption"] or ""
            title = r["title"] or ""

            item: Dict[str, Any] = {
                "skin_id": skin_id,
                "title": title,
                "caption": caption[:300] + ("..." if len(caption) > 300 else ""),
                "rank": round(float(r["rank"]), 2),
                "model_type": r["model_type"] or "default",
            }

            # Inspect skin layers & palette
            try:
                canvas = SkinCanvas()
                canvas.load_png(io.BytesIO(img_bytes))
                palette, _ = canvas_to_ascii(canvas)

                # Check if outer layer has visible non-transparent pixels
                outer_parts = ["hat_front", "jacket_front", "right_sleeve_front", "left_sleeve_front", "right_pants_front", "left_pants_front"]
                has_outer = any(np.any(canvas.parts[p][:, :, 3] > 0) for p in outer_parts if p in canvas.parts)

                item["has_outer_layer"] = has_outer
                item["palette_colors"] = list(palette.values())[:10]  # Top colors

                if render_previews:
                    p3d = str(out_dir / f"rag_{skin_id}_3d.png")
                    p2d = str(out_dir / f"rag_{skin_id}_2d.png")
                    if not os.path.exists(p3d):
                        render_3d_turnaround(canvas, out_path=p3d)
                    if not os.path.exists(p2d):
                        render_composite_2d(canvas, out_path=p2d)
                    item["preview_3d_path"] = p3d
                    item["preview_2d_path"] = p2d

            except Exception as e:
                item["error"] = str(e)

            results.append(item)

        return results

    def get_skin(
        self,
        skin_id: str,
        as_canvas: bool = False,
        as_ascii: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Retrieve skin by ID with decoded canvas or ASCII matrices."""
        row = self.conn.execute("SELECT * FROM skins WHERE skin_id = ?;", (skin_id,)).fetchone()
        if not row:
            return None

        canvas = SkinCanvas()
        canvas.load_png(io.BytesIO(row["image_bytes"]))

        ret: Dict[str, Any] = {
            "skin_id": row["skin_id"],
            "title": row["title"],
            "caption": row["caption"],
            "model_type": row["model_type"],
        }

        if as_ascii:
            palette, parts = canvas_to_ascii(canvas)
            ret["palette"] = palette
            ret["parts"] = parts

        if as_canvas:
            ret["canvas"] = canvas

        return ret

    def remix_skins(
        self,
        base_skin_id: str,
        overlay_skin_id: str,
        parts_to_take: Optional[List[str]] = None,
        auto_fix: bool = True,
        save_path: Optional[str] = None
    ) -> Tuple[SkinCanvas, Dict[str, str]]:
        """
        Blend or remix two skins:
        Takes base body from base_skin and overlays parts/accessories from overlay_skin.
        """
        base_data = self.get_skin(base_skin_id, as_canvas=True, as_ascii=False)
        if not base_data:
            raise ValueError(f"Base skin not found: {base_skin_id}")
        overlay_data = self.get_skin(overlay_skin_id, as_canvas=True, as_ascii=False)
        if not overlay_data:
            raise ValueError(f"Overlay skin not found: {overlay_skin_id}")

        base_canvas: SkinCanvas = base_data["canvas"]
        overlay_canvas: SkinCanvas = overlay_data["canvas"]

        # If no specific parts specified, transfer all Layer 2 outer accessories
        if not parts_to_take:
            parts_to_take = [
                name for name in MINECRAFT_UV_MAP.keys()
                if any(k in name for k in ("hat", "jacket", "sleeve", "pants"))
            ]

        for part_name in parts_to_take:
            if part_name in overlay_canvas.parts and part_name in base_canvas.parts:
                src = overlay_canvas.parts[part_name]
                dst = base_canvas.parts[part_name]
                # Alpha composite
                alpha = src[:, :, 3:4] / 255.0
                dst_rgb = dst[:, :, :3]
                src_rgb = src[:, :, :3]
                out_rgb = (src_rgb * alpha + dst_rgb * (1.0 - alpha)).astype(np.uint8)
                out_a = np.maximum(src[:, :, 3], dst[:, :, 3])
                base_canvas.parts[part_name] = np.dstack([out_rgb, out_a])

        if auto_fix:
            base_canvas.heal_layer1_holes()
            base_canvas.sanitize_outer_layer()

        if save_path:
            base_canvas.export_png(save_path)

        preview_3d = str(DEFAULT_PREVIEW_DIR / f"remix_{base_skin_id[:8]}_{overlay_skin_id[:8]}_3d.png")
        render_3d_turnaround(base_canvas, out_path=preview_3d)

        return base_canvas, {"preview_3d": preview_3d, "status": "Remix completed successfully"}

    def index_parquet(
        self,
        parquet_path: str,
        max_records: Optional[int] = None,
        batch_size: int = 5000
    ) -> int:
        """
        Index skins from a Parquet dataset file into the SQLite FTS5 database.
        """
        import pyarrow.parquet as pq

        p = Path(parquet_path)
        if not p.exists():
            raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

        print(f"📖 Reading parquet shard: {p.name}...")
        table = pq.read_table(str(p))
        total_rows = len(table)
        limit = min(max_records, total_rows) if max_records else total_rows

        print(f"⚡ Indexing {limit:,} skins in batches of {batch_size:,}...")
        t0 = time.time()
        c = self.conn.cursor()

        indexed_count = 0
        batch = []

        for i in range(limit):
            fn = table["file_name"][i].as_py() if "file_name" in table.column_names else f"skin_{i:06d}.png"
            skin_id = Path(fn).stem
            cap = table["text"][i].as_py() or ""
            title = table["title"][i].as_py() if "title" in table.column_names else ""
            b64_img = table["image"][i].as_py()

            try:
                raw_bytes = base64.b64decode(b64_img)
            except Exception:
                continue

            batch.append((skin_id, title or skin_id, cap, raw_bytes, "default"))

            if len(batch) >= batch_size:
                c.executemany("""
                    INSERT OR IGNORE INTO skins (skin_id, title, caption, image_bytes, model_type)
                    VALUES (?, ?, ?, ?, ?);
                """, batch)
                self.conn.commit()
                indexed_count += len(batch)
                batch = []
                elapsed = time.time() - t0
                rate = indexed_count / elapsed
                print(f"  -> Indexed {indexed_count:,}/{limit:,} skins ({rate:.0f} skins/sec)...")

        if batch:
            c.executemany("""
                INSERT OR IGNORE INTO skins (skin_id, title, caption, image_bytes, model_type)
                VALUES (?, ?, ?, ?, ?);
            """, batch)
            self.conn.commit()
            indexed_count += len(batch)

        elapsed = time.time() - t0
        print(f"✅ Indexed {indexed_count:,} skins in {elapsed:.2f}s ({indexed_count/elapsed:.0f} skins/sec). Total in DB: {self.count():,}")
        return indexed_count


# Global singleton instance
_rag_instance: Optional[SkinRAG] = None

def get_rag() -> SkinRAG:
    """Get or initialize the global SkinRAG singleton."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = SkinRAG()
    return _rag_instance
