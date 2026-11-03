"""
SkinForge RAG Engine (v1.3.0) with Graceful Degradation & Portable .sfpack / .db Support.

Operates seamlessly even when the 900k skin database is not installed, returning
structured instructions for running `skin_rag_pack`. When a database is present,
provides sub-millisecond SQLite FTS5 (BM25) text search, 299-dim CIELAB float16
visual similarity search, anatomical part search, and modular Lego assembly.
"""

from __future__ import annotations

import io
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from PIL import Image

from ..ascii_codec import canvas_to_ascii
from ..audit.aesthetic import compute_aesthetic_score
from ..core.canvas import SkinCanvas
from ..core.uv import MINECRAFT_UV_MAP
from ..modular import ANATOMICAL_MODULES, assemble_skin, render_isolated_module
from ..renderer import render_3d_turnaround, render_composite_2d
from .packer import init_rag_schema, pack_rag_database
from .vision import (
    FEATURE_DIM,
    compute_visual_similarity,
    extract_visual_features,
    unpack_feature_blob,
)

DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DEFAULT_PREVIEW_DIR = Path(__file__).resolve().parent.parent.parent / "previews"


def _resolve_default_db_path() -> Path:
    custom = os.environ.get("SKINFORGE_DB_PATH")
    if custom:
        return Path(os.path.expanduser(custom)).resolve()
    sfpack = DEFAULT_DB_DIR / "skins_rag.sfpack"
    if sfpack.exists():
        return sfpack
    return DEFAULT_DB_DIR / "skins_rag.db"


STOP_WORDS = {
    "a", "an", "the", "with", "and", "or", "in", "on", "at", "to", "for",
    "of", "is", "character", "skin", "minecraft", "game", "video", "depicted",
    "image", "features", "style", "appears", "popular",
}


class SkinRAG:
    """Retrieval-Augmented Generation & Modular Assembly engine for Minecraft Skins."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path: Path = Path(os.path.expanduser(str(db_path))).resolve() if db_path else _resolve_default_db_path()
        self.conn: Optional[sqlite3.Connection] = None
        if self.db_path.exists() and self.db_path.stat().st_size > 0:
            self._connect()

    def _connect(self) -> Optional[sqlite3.Connection]:
        if self.conn is not None:
            return self.conn
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            init_rag_schema(self.conn)
            return self.conn
        except Exception:
            self.conn = None
            return None

    def _ensure_conn(self) -> Optional[sqlite3.Connection]:
        if self.conn is not None:
            return self.conn
        if self.db_path.exists() and self.db_path.stat().st_size > 0:
            return self._connect()
        return None

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    @property
    def is_available(self) -> bool:
        """Check if the RAG database exists and contains at least 1 indexed skin."""
        return self.count() > 0

    def count(self) -> int:
        """Return total number of indexed skins (0 if database does not exist or is empty)."""
        conn = self._ensure_conn()
        if conn is None:
            return 0
        try:
            res = conn.execute("SELECT count(*) FROM skins;").fetchone()
            return int(res[0]) if res else 0
        except Exception:
            return 0

    def get_unavailable_response(self, query: Optional[str] = None) -> Dict[str, Any]:
        """
        Return a structured graceful-degradation dictionary when the RAG database is absent
        or empty, providing instructions on how to pack a skin dataset with `skin_rag_pack`.
        """
        resp: Dict[str, Any] = {
            "status": "db_not_initialized",
            "available": False,
            "total_indexed_skins": 0,
            "database_path": str(self.db_path),
            "message": (
                "The SkinForge RAG database is not installed or currently empty. "
                "All procedural authoring, templates, outfits, and auditing tools work normally without it. "
                "To enable RAG search, pack a folder of .png skins or a .zip archive using 'skin_rag_pack' "
                "(MCP tool) or 'python cli.py rag-pack <source_dir_or_zip> --out data/skins_rag.db' (CLI)."
            ),
            "instructions": {
                "mcp_tool": "skin_rag_pack(source_path='path/to/skins_folder_or_zip', output_path='data/skins_rag.db')",
                "cli_command": "skinforge rag-pack <source_folder_or_zip> --out data/skins_rag.db",
            },
            "results": [],
        }
        if query is not None:
            resp["query"] = query
        return resp

    def pack(
        self,
        source_path: str,
        output_path: Optional[str] = None,
        metadata_path: Optional[str] = None,
        min_score: float = 0.0,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """Pack skins from a directory or .zip archive into the RAG database and hot-reload."""
        target_out = output_path or str(self.db_path)
        self.close()
        res = pack_rag_database(
            source_path=source_path,
            output_path=target_out,
            metadata_path=metadata_path,
            min_score=min_score,
            overwrite=overwrite,
        )
        self.db_path = Path(res["output_path"])
        self._connect()
        return res

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
        Search for skins matching the query using SQLite FTS5 BM25 relevance ranking
        and aesthetic quality filtering. Gracefully returns [] if DB is unavailable.
        """
        conn = self._ensure_conn()
        if conn is None or self.count() == 0:
            return []

        fts_q = self.format_fts_query(query)
        fetch_limit = max(limit * 4, 20) if min_quality != "all" else limit

        if fts_q == "*":
            sql = """
                SELECT id, skin_id, title, caption, image_bytes, model_type,
                       quality_score, quality_tier, layer2_ratio, 0.0 as rank
                FROM skins
                ORDER BY quality_score DESC
                LIMIT ?;
            """
            rows = conn.execute(sql, (fetch_limit,)).fetchall()
        else:
            sql = """
                SELECT s.id, s.skin_id, s.title, s.caption, s.image_bytes, s.model_type,
                       s.quality_score, s.quality_tier, s.layer2_ratio, bm25(skins_fts) as rank
                FROM skins_fts
                JOIN skins s ON s.id = skins_fts.rowid
                WHERE skins_fts MATCH ?
                ORDER BY rank
                LIMIT ?;
            """
            try:
                rows = conn.execute(sql, (fts_q, fetch_limit)).fetchall()
            except sqlite3.OperationalError:
                rows = []

        out_dir = Path(preview_dir) if preview_dir else DEFAULT_PREVIEW_DIR
        if render_previews:
            out_dir.mkdir(parents=True, exist_ok=True)

        quality_thresholds = {
            "all": 0.0,
            "low": 0.20,
            "medium": 0.40,
            "high": 0.65,
            "top_tier": 0.78,
        }
        min_score = quality_thresholds.get(min_quality, 0.40)

        results: List[Dict[str, Any]] = []
        for r in rows:
            skin_id = r["skin_id"]
            img_bytes = r["image_bytes"]
            caption = r["caption"] or ""
            title = r["title"] or ""

            try:
                canvas = SkinCanvas()
                canvas.load_png(io.BytesIO(img_bytes))

                stored_score = r["quality_score"] if "quality_score" in r.keys() else None
                if stored_score is not None and float(stored_score) > 0.0:
                    score_val = round(float(stored_score), 3)
                    tier_val = r["quality_tier"] or ("top_tier" if score_val >= 0.78 else "high" if score_val >= 0.62 else "medium" if score_val >= 0.42 else "low")
                    l2_val = round(float(r["layer2_ratio"] or 0.0), 3)
                else:
                    aesthetic = compute_aesthetic_score(canvas)
                    score_val = aesthetic["score"]
                    tier_val = aesthetic["tier"]
                    l2_val = aesthetic["layer2_ratio"]

                if score_val < min_score:
                    continue

                palette, _ = canvas_to_ascii(canvas)

                item: Dict[str, Any] = {
                    "skin_id": skin_id,
                    "title": title,
                    "caption": caption[:300] + ("..." if len(caption) > 300 else ""),
                    "rank": round(float(r["rank"]), 2),
                    "quality_score": score_val,
                    "quality_tier": tier_val,
                    "layer2_ratio": l2_val,
                    "model_type": r["model_type"] or "default",
                    "palette_colors": list(palette.values())[:10],
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
            except Exception:
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
        Search for specific anatomical components (hair, face, torso, arms, legs, head, outfit)
        and render isolated 3D component previews on a neutral mannequin.
        """
        valid_cats = list(ANATOMICAL_MODULES.keys())
        if category not in valid_cats:
            raise ValueError(f"Invalid category '{category}'. Choose from: {valid_cats}")

        if not self.is_available:
            return []

        augmented_query = f"{query} {category}"
        candidates = self.search(
            query=augmented_query,
            limit=limit,
            min_quality=min_quality,
            render_previews=False,
        )
        if not candidates and query.strip():
            candidates = self.search(
                query=query,
                limit=limit,
                min_quality=min_quality,
                render_previews=False,
            )

        out_dir = Path(preview_dir) if preview_dir else DEFAULT_PREVIEW_DIR
        if render_previews:
            out_dir.mkdir(parents=True, exist_ok=True)

        results: List[Dict[str, Any]] = []
        for item in candidates:
            skin_id = item["skin_id"]
            skin_data = self.get_skin(skin_id, as_canvas=True, as_ascii=False)
            if not skin_data or "canvas" not in skin_data:
                continue

            canvas = skin_data["canvas"]
            part_item: Dict[str, Any] = {
                "skin_id": skin_id,
                "category": category,
                "title": item["title"],
                "caption": item["caption"],
                "quality_tier": item["quality_tier"],
                "quality_score": item["quality_score"],
                "palette_colors": item["palette_colors"],
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
        candidate_pool: int = 100,
        min_quality: str = "medium",
        render_previews: bool = True,
        preview_dir: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search Minecraft skins visually matching a concept art image, reference photo, or drawing
        using 299-dimensional CIELAB spatial-color pyramid feature vectors (stored as float16 BLOBs).
        """
        conn = self._ensure_conn()
        if conn is None or self.count() == 0:
            return []

        query_vec = extract_visual_features(image_input)

        out_dir = Path(preview_dir) if preview_dir else DEFAULT_PREVIEW_DIR
        if render_previews:
            out_dir.mkdir(parents=True, exist_ok=True)

        sql = """
            SELECT skin_id, title, caption, image_bytes, feature_vec,
                   model_type, quality_score, quality_tier
            FROM skins
            ORDER BY RANDOM()
            LIMIT ?;
        """
        rows = conn.execute(sql, (candidate_pool,)).fetchall()

        quality_thresholds = {
            "all": 0.0,
            "low": 0.20,
            "medium": 0.40,
            "high": 0.65,
            "top_tier": 0.78,
        }
        min_score = quality_thresholds.get(min_quality, 0.40)

        candidates: List[Dict[str, Any]] = []
        for r in rows:
            try:
                stored_score = r["quality_score"] if "quality_score" in r.keys() else None
                canvas: Optional[SkinCanvas] = None
                if stored_score is not None and float(stored_score) > 0.0:
                    score_val = round(float(stored_score), 3)
                    tier_val = r["quality_tier"] or "medium"
                else:
                    canvas = SkinCanvas()
                    canvas.load_png(io.BytesIO(r["image_bytes"]))
                    aesthetic = compute_aesthetic_score(canvas)
                    score_val = aesthetic["score"]
                    tier_val = aesthetic["tier"]

                if score_val < min_score:
                    continue

                feat_blob = r["feature_vec"] if "feature_vec" in r.keys() else None
                if feat_blob and len(feat_blob) == FEATURE_DIM * 2:
                    feat = unpack_feature_blob(feat_blob)
                else:
                    feat = extract_visual_features(io.BytesIO(r["image_bytes"]))

                sim = compute_visual_similarity(query_vec, feat)

                candidates.append({
                    "skin_id": r["skin_id"],
                    "title": r["title"] or "",
                    "caption": (r["caption"] or "")[:250],
                    "similarity": round(float(sim), 3),
                    "quality_score": score_val,
                    "quality_tier": tier_val,
                    "image_bytes": r["image_bytes"],
                    "canvas": canvas,
                })
            except Exception:
                continue

        candidates.sort(key=lambda x: x["similarity"], reverse=True)
        top_matches = candidates[:limit]

        results: List[Dict[str, Any]] = []
        for c in top_matches:
            item: Dict[str, Any] = {
                "skin_id": c["skin_id"],
                "title": c["title"],
                "caption": c["caption"],
                "similarity_score": c["similarity"],
                "quality_score": c["quality_score"],
                "quality_tier": c["quality_tier"],
            }

            if render_previews:
                p3d = str(out_dir / f"rag_vis_{c['skin_id']}_3d.png")
                if not os.path.exists(p3d):
                    c_obj = c["canvas"]
                    if c_obj is None:
                        c_obj = SkinCanvas()
                        c_obj.load_png(io.BytesIO(c["image_bytes"]))
                    render_3d_turnaround(c_obj, out_path=p3d)
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
        """Assemble a complete skin from modular component sources (Lego Constructor)."""
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
                    if not self.is_available:
                        raise RuntimeError(self.get_unavailable_response()["message"])
                    skin_data = self.get_skin(src, as_canvas=True, as_ascii=False)
                    if not skin_data or "canvas" not in skin_data:
                        raise ValueError(f"Component '{mod_name}' references unknown skin_id or file: '{src}'")
                    resolved_sources[mod_name] = skin_data["canvas"]

        assembled, summary = assemble_skin(
            sources=resolved_sources,
            base_canvas=base_canvas,
            auto_blend_seams=auto_blend_seams,
            auto_fix=auto_fix,
        )

        DEFAULT_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
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
        conn = self._ensure_conn()
        if conn is None:
            return None
        try:
            row = conn.execute("SELECT * FROM skins WHERE skin_id = ?;", (skin_id,)).fetchone()
        except sqlite3.OperationalError:
            return None
        if not row:
            return None

        canvas = SkinCanvas()
        canvas.load_png(io.BytesIO(row["image_bytes"]))

        ret: Dict[str, Any] = {
            "skin_id": row["skin_id"],
            "title": row["title"],
            "caption": row["caption"],
            "model_type": row["model_type"] or "default",
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
        """Blend or remix two skins from the RAG dataset or file paths."""
        def _resolve_skin(sid: str) -> Optional[SkinCanvas]:
            if os.path.exists(sid):
                c = SkinCanvas()
                c.load_png(sid)
                return c
            data = self.get_skin(sid, as_canvas=True, as_ascii=False)
            return data["canvas"] if data and "canvas" in data else None

        base_canvas = _resolve_skin(base_skin_id)
        if base_canvas is None:
            if not self.is_available:
                raise RuntimeError(self.get_unavailable_response()["message"])
            raise ValueError(f"Base skin not found: {base_skin_id}")

        overlay_canvas = _resolve_skin(overlay_skin_id)
        if overlay_canvas is None:
            if not self.is_available:
                raise RuntimeError(self.get_unavailable_response()["message"])
            raise ValueError(f"Overlay skin not found: {overlay_skin_id}")

        if not parts_to_take:
            parts_to_take = [
                name for name in MINECRAFT_UV_MAP.keys()
                if any(k in name for k in ("hat", "jacket", "sleeve", "pants"))
            ]

        for part_name in parts_to_take:
            if part_name in overlay_canvas.parts and part_name in base_canvas.parts:
                src = overlay_canvas.parts[part_name]
                dst = base_canvas.parts[part_name]
                alpha = src[:, :, 3:4].astype(np.float64) / 255.0
                dst_rgb = dst[:, :, :3].astype(np.float64)
                src_rgb = src[:, :, :3].astype(np.float64)
                out_rgb = np.clip(np.round(src_rgb * alpha + dst_rgb * (1.0 - alpha)), 0, 255).astype(np.uint8)
                out_a = np.maximum(src[:, :, 3], dst[:, :, 3])
                base_canvas.parts[part_name] = np.dstack([out_rgb, out_a])

        if auto_fix:
            base_canvas.heal_layer1_holes()
            base_canvas.sanitize_outer_layer()

        DEFAULT_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        p3d = save_path or str(DEFAULT_PREVIEW_DIR / f"remix_{Path(base_skin_id).stem}_{Path(overlay_skin_id).stem}_3d.png")
        render_3d_turnaround(base_canvas, out_path=p3d)

        return base_canvas, {"preview_3d": p3d, "status": "success"}


_rag_instance: Optional[SkinRAG] = None


def get_rag(db_path: Optional[str] = None) -> SkinRAG:
    """Get or initialize the global SkinRAG singleton."""
    global _rag_instance
    if db_path is not None:
        return SkinRAG(db_path=db_path)
    if _rag_instance is None:
        _rag_instance = SkinRAG()
    return _rag_instance


def set_rag_db_path(db_path: str) -> SkinRAG:
    """Point the global SkinRAG singleton to a newly packed or custom database file."""
    global _rag_instance
    if _rag_instance is not None:
        _rag_instance.close()
    _rag_instance = SkinRAG(db_path=db_path)
    return _rag_instance
