"""
SkinForge RAG Database Packer (`skin_rag_pack` / `rag-pack`).

Ingests a folder of .png skins or a .zip archive (plus optional .json / .csv metadata),
validates skins (including automatic 64x32 -> 64x64 legacy conversion), computes
aesthetic_score, extracts the 299-dim CIELAB spatial-color pyramid as a float16 BLOB,
stores compressed PNG textures in SQLite BLOB, and indexes tags/captions in SQLite FTS5 (BM25).
Outputs a single compact, portable database file (.sfpack / .db).
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from PIL import Image

from ..audit.aesthetic import compute_aesthetic_score
from ..core.uv import detect_skin_model_from_array, load_skin_array
from .vision import extract_visual_features, pack_feature_blob


def _clean_stem_to_tags(stem: str) -> Tuple[str, str]:
    """Derive a clean human-readable title and tag string from a filename stem."""
    cleaned = re.sub(r"^skin\d+[-_]?", "", stem, flags=re.IGNORECASE)
    tokens = [t for t in re.split(r"[-_\s.]+", cleaned) if t]
    if not tokens:
        tokens = [stem]
    title = " ".join(tokens).strip()
    tags = " ".join(t.lower() for t in tokens)
    return title, tags


def _parse_metadata_content(raw_text: str, fmt: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse JSON or CSV metadata content into a lookup dictionary keyed by both
    skin_id (stem) and filename (with extension).
    """
    meta_map: Dict[str, Dict[str, Any]] = {}

    def _register(key: str, entry: Dict[str, Any]) -> None:
        if not key:
            return
        k_str = str(key).strip()
        meta_map[k_str] = entry
        meta_map[k_str.lower()] = entry
        stem = Path(k_str).stem
        meta_map[stem] = entry
        meta_map[stem.lower()] = entry

    if fmt == "json":
        data = json.loads(raw_text)
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    _register(k, {"title": Path(k).stem, "caption": v, "tags": v})
                elif isinstance(v, dict):
                    _register(k, v)
        elif isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                key = (
                    item.get("skin_id")
                    or item.get("id")
                    or item.get("file_name")
                    or item.get("filename")
                    or item.get("file")
                    or item.get("name")
                )
                if key:
                    _register(str(key), item)
    elif fmt == "csv":
        reader = csv.DictReader(io.StringIO(raw_text))
        for row in reader:
            if not row:
                continue
            key = (
                row.get("skin_id")
                or row.get("id")
                or row.get("file_name")
                or row.get("filename")
                or row.get("file")
                or row.get("name")
            )
            if key:
                _register(str(key), dict(row))

    return meta_map


def _load_metadata(
    source_path: Path,
    metadata_path: Optional[str] = None,
    zf: Optional[zipfile.ZipFile] = None
) -> Dict[str, Dict[str, Any]]:
    """Load optional metadata from an explicit path or auto-discover inside folder/zip."""
    if metadata_path:
        mp = Path(os.path.expanduser(metadata_path)).resolve()
        if not mp.exists():
            raise FileNotFoundError(f"Metadata file not found: '{mp}'")
        fmt = "csv" if mp.suffix.lower() == ".csv" else "json"
        return _parse_metadata_content(mp.read_text(encoding="utf-8"), fmt)

    candidate_names = (
        "metadata.json",
        "metadata.csv",
        "captions.json",
        "captions.csv",
        "skins.json",
        "skins.csv",
    )

    if zf is not None:
        namelist = zf.namelist()
        for cname in candidate_names:
            matches = [n for n in namelist if Path(n).name.lower() == cname]
            if matches:
                raw_bytes = zf.read(matches[0])
                fmt = "csv" if cname.endswith(".csv") else "json"
                try:
                    return _parse_metadata_content(raw_bytes.decode("utf-8"), fmt)
                except Exception:
                    pass
    elif source_path.is_dir():
        for cname in candidate_names:
            cand = source_path / cname
            if cand.exists():
                fmt = "csv" if cname.endswith(".csv") else "json"
                try:
                    return _parse_metadata_content(cand.read_text(encoding="utf-8"), fmt)
                except Exception:
                    pass

    return {}


def init_rag_schema(conn: sqlite3.Connection) -> None:
    """Create or migrate the SQLite schema and FTS5 BM25 virtual table for SkinForge RAG."""
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS skins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skin_id TEXT UNIQUE,
            title TEXT,
            caption TEXT,
            tags TEXT DEFAULT '',
            image_bytes BLOB,
            feature_vec BLOB,
            model_type TEXT DEFAULT 'default',
            quality_score REAL DEFAULT 0.0,
            quality_tier TEXT DEFAULT 'medium',
            layer2_ratio REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    c.execute("PRAGMA table_info(skins);")
    existing_cols = {row[1] for row in c.fetchall()}
    migrations = [
        ("tags", "TEXT DEFAULT ''"),
        ("feature_vec", "BLOB"),
        ("quality_score", "REAL DEFAULT 0.0"),
        ("quality_tier", "TEXT DEFAULT 'medium'"),
        ("layer2_ratio", "REAL DEFAULT 0.0"),
    ]
    for col_name, col_def in migrations:
        if col_name not in existing_cols:
            c.execute(f"ALTER TABLE skins ADD COLUMN {col_name} {col_def};")

    c.execute("CREATE INDEX IF NOT EXISTS idx_skins_quality ON skins(quality_score);")

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
    conn.commit()


def _iter_png_sources(source_path: Path) -> Tuple[List[Tuple[str, bytes]], Optional[zipfile.ZipFile]]:
    """Return list of (filename, raw_bytes) from either a directory or a .zip archive."""
    items: List[Tuple[str, bytes]] = []
    if source_path.is_file() and source_path.suffix.lower() == ".zip":
        zf = zipfile.ZipFile(source_path, "r")
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if name.startswith("__MACOSX") or Path(name).name.startswith("."):
                continue
            if name.lower().endswith(".png"):
                items.append((Path(name).name, zf.read(name)))
        return items, zf
    elif source_path.is_dir():
        for p in sorted(source_path.rglob("*.png")):
            if p.name.startswith("."):
                continue
            items.append((p.name, p.read_bytes()))
        return items, None
    elif source_path.is_file() and source_path.suffix.lower() == ".png":
        items.append((source_path.name, source_path.read_bytes()))
        return items, None
    else:
        raise ValueError(f"source_path must be a directory of .png files or a .zip archive, got: '{source_path}'")


def pack_rag_database(
    source_path: str,
    output_path: Optional[str] = None,
    metadata_path: Optional[str] = None,
    min_score: float = 0.0,
    overwrite: bool = False
) -> Dict[str, Any]:
    """
    Pack a folder of .png skins or a .zip archive into a single portable SQLite FTS5
    database (.sfpack / .db) with compressed PNG BLOBs, aesthetic scores, and
    299-dimensional CIELAB spatial-color pyramid float16 feature vectors.
    """
    t0 = time.time()
    src = Path(os.path.expanduser(source_path)).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source path not found: '{src}'")

    default_out = Path(__file__).resolve().parent.parent.parent / "data" / "skins_rag.db"
    out_db = Path(os.path.expanduser(output_path)).resolve() if output_path else default_out
    out_db.parent.mkdir(parents=True, exist_ok=True)

    if overwrite and out_db.exists():
        out_db.unlink()

    png_items, zf = _iter_png_sources(src)
    try:
        meta_map = _load_metadata(src, metadata_path=metadata_path, zf=zf)
    finally:
        if zf is not None:
            zf.close()

    conn = sqlite3.connect(str(out_db), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    init_rag_schema(conn)

    packed_count = 0
    skipped_invalid = 0
    skipped_low_score = 0
    converted_legacy_count = 0
    tier_counts: Dict[str, int] = {"top_tier": 0, "high": 0, "medium": 0, "low": 0}
    batch: List[Tuple[Any, ...]] = []

    for filename, raw_bytes in png_items:
        stem = Path(filename).stem
        try:
            arr, was_legacy = load_skin_array(raw_bytes)
            if was_legacy:
                converted_legacy_count += 1
        except Exception:
            skipped_invalid += 1
            continue

        meta = (
            meta_map.get(filename)
            or meta_map.get(filename.lower())
            or meta_map.get(stem)
            or meta_map.get(stem.lower())
            or {}
        )

        skin_id = str(meta.get("skin_id") or meta.get("id") or stem).strip()
        model_type = str(meta.get("model_type") or meta.get("model") or "").strip().lower()
        if model_type not in ("slim", "default", "classic"):
            model_type = detect_skin_model_from_array(arr)
        elif model_type == "classic":
            model_type = "default"

        aesthetic = compute_aesthetic_score(arr, model=model_type, deduct_defects=True)
        score = float(aesthetic["score"])
        tier = str(aesthetic["tier"])
        l2_ratio = float(aesthetic["layer2_ratio"])

        if score < float(min_score):
            skipped_low_score += 1
            continue

        # Compute 299-dim CIELAB spatial-color pyramid in float16 BLOB (598 bytes)
        feat_vec = extract_visual_features(arr)
        feat_blob = pack_feature_blob(feat_vec)

        # Compress 64x64 RGBA PNG into BLOB
        png_buf = io.BytesIO()
        Image.fromarray(arr, mode="RGBA").save(png_buf, format="PNG", optimize=True)
        compressed_png = png_buf.getvalue()

        auto_title, auto_tags = _clean_stem_to_tags(stem)
        title = str(meta.get("title") or meta.get("name") or auto_title).strip()

        raw_tags = meta.get("tags") or ""
        if isinstance(raw_tags, list):
            tags_str = " ".join(str(t) for t in raw_tags)
        else:
            tags_str = str(raw_tags)
        if not tags_str:
            tags_str = auto_tags

        raw_caption = (
            meta.get("caption")
            or meta.get("description")
            or meta.get("text")
            or ""
        )
        caption = f"{raw_caption} {tags_str} {tier} {model_type}".strip()
        if not caption:
            caption = f"{title} {auto_tags} {tier}"

        batch.append((
            skin_id,
            title,
            caption,
            tags_str,
            compressed_png,
            feat_blob,
            model_type,
            score,
            tier,
            l2_ratio,
        ))
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        packed_count += 1

        if len(batch) >= 500:
            conn.executemany(
                """
                INSERT OR REPLACE INTO skins (
                    skin_id, title, caption, tags, image_bytes, feature_vec,
                    model_type, quality_score, quality_tier, layer2_ratio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                batch,
            )
            conn.commit()
            batch.clear()

    if batch:
        conn.executemany(
            """
            INSERT OR REPLACE INTO skins (
                skin_id, title, caption, tags, image_bytes, feature_vec,
                model_type, quality_score, quality_tier, layer2_ratio
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            batch,
        )
        conn.commit()
        batch.clear()

    # Optimize FTS5 BM25 index and checkpoint WAL into single portable file
    conn.execute("INSERT INTO skins_fts(skins_fts) VALUES('optimize');")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.commit()

    total_in_db = conn.execute("SELECT count(*) FROM skins;").fetchone()[0]
    conn.close()

    # Hot-reload singleton if packing into active/default DB
    from .engine import set_rag_db_path
    set_rag_db_path(str(out_db))

    elapsed = round(time.time() - t0, 3)
    size_bytes = out_db.stat().st_size if out_db.exists() else 0

    return {
        "status": "success",
        "source_path": str(src),
        "output_path": str(out_db),
        "packed_count": packed_count,
        "total_indexed_skins": int(total_in_db),
        "converted_legacy_64x32": converted_legacy_count,
        "skipped_invalid": skipped_invalid,
        "skipped_low_score": skipped_low_score,
        "tier_distribution": tier_counts,
        "feature_vector_dim": 299,
        "feature_vector_dtype": "float16",
        "database_size_bytes": size_bytes,
        "database_size_mb": round(size_bytes / (1024.0 * 1024.0), 3),
        "elapsed_seconds": elapsed,
    }
