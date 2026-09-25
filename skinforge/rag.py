"""
SkinForge RAG - Retrieval-Augmented Generation & Modular Assembly for Minecraft Skins.

Provides fast, native search across 900,000+ captioned Minecraft skins using
SQLite FTS5 (BM25 ranking), on-the-fly 3D previews, palette extraction,
modular Lego part assembly, aesthetic quality filtering, and image-based visual search.
"""

import os
import io
import re
import time
import base64
import sqlite3
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from PIL import Image

from .canvas import SkinCanvas, MINECRAFT_UV_MAP
from .renderer import render_3d_turnaround, render_composite_2d
from .ascii_codec import canvas_to_ascii
from .validator import compute_aesthetic_score
from .modular import ANATOMICAL_MODULES, assemble_skin, render_isolated_module
from .vision import extract_visual_features, compute_visual_similarity

# Default paths
DEFAULT_DB_DIR = Path(__file__).parent.parent / "data"
_custom_db = os.environ.get("SKINFORGE_DB_PATH")
DEFAULT_DB_PATH = Path(_custom_db) if _custom_db else DEFAULT_DB_DIR / "skins_rag.db"
DEFAULT_PREVIEW_DIR = Path(__file__).parent.parent / "previews"

STOP_WORDS = {
    "a", "an", "the", "with", "and", "or", "in", "on", "at", "to", "for",
    "of", "is", "character", "skin", "minecraft", "game", "video", "depicted",
    "image", "features", "style", "appears", "popular"
}


class SkinRAG:
    """Retrieval-Augmented Generation & Modular Assembly engine for Minecraft Skins."""

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

    @property
    def is_available(self) -> bool:
        """Check if the RAG database exists and contains indexed skins."""
        try:
            return self.count() > 0
        except Exception:
            return False

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
        return " OR ".join(f'"{t}"*' for t in meaningful)

    def search(
        self,
        query: str,
        limit: int = 5,
        min_quality: str = "medium",
        render_previews: bool = True,
        preview_dir: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for skins matching the query using BM25 relevance ranking and aesthetic quality filtering.
        Optionally generates 3D turnaround and 2D composite previews.
        
        Args:
            query: Keywords or description (e.g. 'purple tuxedo', 'cyberpunk samurai').
            limit: Maximum candidate skins to return.
            min_quality: 'all', 'low', 'medium' (score >= 0.40), or 'high' (score >= 0.65).
            render_previews: Whether to render 3D turnaround PNGs for visual inspection.
            preview_dir: Destination folder for rendered previews.
        """
        if self.count() == 0:
            return []

        fts_q = self.format_fts_query(query)
        # Fetch slightly larger candidate pool to allow quality filtering
        fetch_limit = limit * 4 if min_quality != "all" else limit

        sql = """
            SELECT s.id, s.skin_id, s.title, s.caption, s.image_bytes, s.model_type, bm25(skins_fts) as rank
            FROM skins_fts
            JOIN skins s ON s.id = skins_fts.rowid
            WHERE skins_fts MATCH ?
            ORDER BY rank
            LIMIT ?;
        """
        rows = self.conn.execute(sql, (fts_q, fetch_limit)).fetchall()

        out_dir = Path(preview_dir) if preview_dir else DEFAULT_PREVIEW_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        quality_thresholds = {
            "all": 0.0,
            "low": 0.20,
            "medium": 0.40,
            "high": 0.65
        }
        min_score = quality_thresholds.get(min_quality, 0.40)

        results = []
        for r in rows:
            skin_id = r["skin_id"]
            img_bytes = r["image_bytes"]
            caption = r["caption"] or ""
            title = r["title"] or ""

            try:
                canvas = SkinCanvas()
                canvas.load_png(io.BytesIO(img_bytes))

                # Aesthetic quality assessment
                aesthetic = compute_aesthetic_score(canvas)
                if aesthetic["score"] < min_score:
                    continue  # Skip low quality skins

                palette, _ = canvas_to_ascii(canvas)

                item: Dict[str, Any] = {
                    "skin_id": skin_id,
                    "title": title,
                    "caption": caption[:300] + ("..." if len(caption) > 300 else ""),
                    "rank": round(float(r["rank"]), 2),
                    "quality_score": aesthetic["score"],
                    "quality_tier": aesthetic["tier"],
                    "layer2_ratio": aesthetic["layer2_ratio"],
                    "model_type": r["model_type"] or "default",
                    "palette_colors": list(palette.values())[:10]
                }

                if render_previews:
                    p3d = str(out_dir / f"rag_{skin_id}_3d.png")
                    p2d = str(out_dir / f"rag_{skin_id}_2d.png")
                    if not os.path.exists(p3d):
                        render_3d_turnaround(canvas, out_path=p3d)
                    if not os.path.exists(p2d):
                        render_composite_2d(canvas, out_path=p2d)
                    item["preview_3d_path"] = p3d
                    item["preview_2d_path"] = p2d

                results.append(item)
                if len(results) >= limit:
                    break

            except Exception as e:
                continue

        return results

    def part_search(
        self,
        category: str,
        query: str,
        limit: int = 5,
        min_quality: str = "medium",
        render_previews: bool = True,
        preview_dir: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for specific anatomical components (hair, face, torso, arms, legs, outfit)
        and render isolated 3D component previews on a neutral mannequin.
        """
        valid_cats = list(ANATOMICAL_MODULES.keys())
        if category not in valid_cats:
            raise ValueError(f"Invalid category '{category}'. Choose from: {valid_cats}")

        # Augment search query with category context
        augmented_query = f"{query} {category}"
        candidates = self.search(
            query=augmented_query,
            limit=limit,
            min_quality=min_quality,
            render_previews=False
        )

        out_dir = Path(preview_dir) if preview_dir else DEFAULT_PREVIEW_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for item in candidates:
            skin_id = item["skin_id"]
            skin_data = self.get_skin(skin_id, as_canvas=True, as_ascii=False)
            if not skin_data or "canvas" not in skin_data:
                continue

            canvas = skin_data["canvas"]
            part_item = {
                "skin_id": skin_id,
                "category": category,
                "title": item["title"],
                "caption": item["caption"],
                "quality_tier": item["quality_tier"],
                "quality_score": item["quality_score"],
                "palette_colors": item["palette_colors"]
            }

            if render_previews:
                p_part = str(out_dir / f"rag_part_{category}_{skin_id}.png")
                if not os.path.exists(p_part):
                    im_part = render_isolated_module(canvas, category)
                    im_part.save(p_part)
                part_item["preview_part_path"] = p_part

            results.append(part_item)

        return results

    def search_by_image(
        self,
        image_input: Union[str, Image.Image, np.ndarray],
        limit: int = 5,
        candidate_pool: int = 40,
        min_quality: str = "medium",
        render_previews: bool = True,
        preview_dir: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search Minecraft skins visually matching a concept art image, reference photo, or drawing.
        Uses spatial-color LAB pyramid feature vectors (OpenCV + NumPy).
        """
        if self.count() == 0:
            return []

        # Extract query feature vector
        query_vec = extract_visual_features(image_input)

        out_dir = Path(preview_dir) if preview_dir else DEFAULT_PREVIEW_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        # Retrieve candidate pool from database
        sql = """
            SELECT skin_id, title, caption, image_bytes, model_type
            FROM skins
            ORDER BY RANDOM()
            LIMIT ?;
        """
        rows = self.conn.execute(sql, (candidate_pool,)).fetchall()

        candidates = []
        for r in rows:
            try:
                canvas = SkinCanvas()
                canvas.load_png(io.BytesIO(r["image_bytes"]))
                aesthetic = compute_aesthetic_score(canvas)

                if min_quality == "high" and aesthetic["score"] < 0.65:
                    continue
                if min_quality == "medium" and aesthetic["score"] < 0.40:
                    continue

                feat = extract_visual_features(io.BytesIO(r["image_bytes"]))
                sim = compute_visual_similarity(query_vec, feat)

                candidates.append({
                    "skin_id": r["skin_id"],
                    "title": r["title"] or "",
                    "caption": (r["caption"] or "")[:250],
                    "similarity": round(float(sim), 3),
                    "quality_score": aesthetic["score"],
                    "quality_tier": aesthetic["tier"],
                    "canvas": canvas
                })
            except Exception:
                continue

        # Sort by visual similarity descending
        candidates.sort(key=lambda x: x["similarity"], reverse=True)
        top_matches = candidates[:limit]

        results = []
        for c in top_matches:
            item = {
                "skin_id": c["skin_id"],
                "title": c["title"],
                "caption": c["caption"],
                "similarity_score": c["similarity"],
                "quality_tier": c["quality_tier"]
            }

            if render_previews:
                p3d = str(out_dir / f"rag_vis_{c['skin_id']}_3d.png")
                if not os.path.exists(p3d):
                    render_3d_turnaround(c["canvas"], out_path=p3d)
                item["preview_3d_path"] = p3d

            results.append(item)

        return results

    def assemble_modules(
        self,
        components: Dict[str, Union[str, SkinCanvas]],
        base_canvas: Optional[SkinCanvas] = None,
        auto_blend_seams: bool = True,
        auto_fix: bool = True
    ) -> Tuple[SkinCanvas, Dict[str, Any]]:
        """
        Assemble a complete skin from modular component sources (Lego Constructor).
        Components maps module name ('hair', 'face', 'torso', 'arms', 'legs', 'outfit')
        to either a skin_id string or a SkinCanvas instance.
        """
        resolved_sources: Dict[str, SkinCanvas] = {}

        for mod_name, src in components.items():
            if isinstance(src, SkinCanvas):
                resolved_sources[mod_name] = src
            elif isinstance(src, str):
                if os.path.exists(src):
                    c = SkinCanvas()
                    c.load_png(src)
                    resolved_sources[mod_name] = c
                else:
                    skin_data = self.get_skin(src, as_canvas=True, as_ascii=False)
                    if not skin_data or "canvas" not in skin_data:
                        raise ValueError(f"Component '{mod_name}' references unknown skin_id or file: '{src}'")
                    resolved_sources[mod_name] = skin_data["canvas"]

        assembled, summary = assemble_skin(
            sources=resolved_sources,
            base_canvas=base_canvas,
            auto_blend_seams=auto_blend_seams,
            auto_fix=auto_fix
        )

        # Generate 3D turnaround
        preview_path = str(DEFAULT_PREVIEW_DIR / f"assemble_preview_{int(time.time())}.png")
        render_3d_turnaround(assembled, out_path=preview_path)
        summary["preview_3d_path"] = preview_path

        return assembled, summary

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

        if not parts_to_take:
            parts_to_take = [
                name for name in MINECRAFT_UV_MAP.keys()
                if any(k in name for k in ("hat", "jacket", "sleeve", "pants"))
            ]

        for part_name in parts_to_take:
            if part_name in overlay_canvas.parts and part_name in base_canvas.parts:
                src = overlay_canvas.parts[part_name]
                dst = base_canvas.parts[part_name]
                alpha = src[:, :, 3:4] / 255.0
                dst_rgb = dst[:, :, :3]
                src_rgb = src[:, :, :3]
                out_rgb = (src_rgb * alpha + dst_rgb * (1.0 - alpha)).astype(np.uint8)
                out_a = np.maximum(src[:, :, 3], dst[:, :, 3])
                base_canvas.parts[part_name] = np.dstack([out_rgb, out_a])

        if auto_fix:
            base_canvas.heal_layer1_holes()
            base_canvas.sanitize_outer_layer()

        p3d = save_path or str(DEFAULT_PREVIEW_DIR / f"remix_{base_skin_id}_{overlay_skin_id}_3d.png")
        render_3d_turnaround(base_canvas, out_path=p3d)

        return base_canvas, {"preview_3d": p3d, "status": "success"}


# Global singleton instance
_rag_instance: Optional[SkinRAG] = None

def get_rag() -> SkinRAG:
    """Get or initialize the global SkinRAG singleton."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = SkinRAG()
    return _rag_instance
