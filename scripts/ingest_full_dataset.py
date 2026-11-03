#!/usr/bin/env python3
"""
SkinForge Full Dataset Downloader, Quality Filter & Ingestion Engine (v1.3.0).
Downloads all 7 splits (900,000 skins) from Hugging Face:
  summykai/minecraft-skins-captioned-900k
Applies algorithmic aesthetic filtering (compute_aesthetic_score),
computes 299-dim CIELAB float16 spatial-color pyramid vectors,
and populates the portable SQLite FTS5 database using the v1.3.0 schema.
"""

import base64
import io
import os
import sqlite3
import sys
import time
from pathlib import Path
import numpy as np
from PIL import Image

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from skinforge.audit import compute_aesthetic_score
from skinforge.core import detect_skin_model_from_array, load_skin_array
from skinforge.rag.packer import init_rag_schema
from skinforge.rag.vision import extract_visual_features, pack_feature_blob

DB_PATH = PROJECT_ROOT / "data" / "skins_rag.db"
REPO_ID = "summykai/minecraft-skins-captioned-900k"
TOTAL_SPLITS = 7
MIN_SCORE_THRESHOLD = 0.35  # Filter out low-effort flat flood fills and noise


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize full v1.3.0 SQLite + FTS5 schema via init_rag_schema."""
    init_rag_schema(conn)


def process_split(split_idx: int, conn: sqlite3.Connection, existing_ids: set) -> None:
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    filename = f"data/train-{split_idx:05d}-of-00007.parquet"
    print("\n=======================================================")
    print(f"[*] Processing Split {split_idx+1}/{TOTAL_SPLITS}: {filename}")
    print("=======================================================")

    t0 = time.time()
    parquet_path = hf_hub_download(
        repo_id=REPO_ID,
        filename=filename,
        repo_type="dataset",
    )
    dl_dur = time.time() - t0
    print(f"[+] Parquet ready: {parquet_path} ({dl_dur:.1f}s)")

    table = pq.read_table(parquet_path)
    total_rows = len(table)
    print(f"[*] Scanning {total_rows:,} skins in split...")

    c = conn.cursor()
    batch = []
    skipped_existing = 0
    skipped_low_quality = 0
    inserted = 0
    t_start = time.time()

    tier_counts = {"top_tier": 0, "high": 0, "medium": 0, "low": 0}

    for idx in range(total_rows):
        file_name = table["file_name"][idx].as_py()
        skin_id = Path(file_name).stem if file_name else f"skin_{split_idx}_{idx}"

        if skin_id in existing_ids:
            skipped_existing += 1
            continue

        b64_str = table["image"][idx].as_py()
        if not b64_str:
            continue

        try:
            raw_bytes = base64.b64decode(b64_str)
            arr, was_legacy = load_skin_array(raw_bytes)
            model_type = detect_skin_model_from_array(arr)

            aesthetic = compute_aesthetic_score(arr, model=model_type)
            score = float(aesthetic["score"])
            tier = str(aesthetic["tier"])
            l2_ratio = float(aesthetic["layer2_ratio"])

            if score < MIN_SCORE_THRESHOLD:
                skipped_low_quality += 1
                continue

            feat_blob = pack_feature_blob(extract_visual_features(arr))
            if was_legacy:
                png_buf = io.BytesIO()
                Image.fromarray(arr, mode="RGBA").save(png_buf, format="PNG", optimize=True)
                raw_bytes = png_buf.getvalue()

            title = table["title"][idx].as_py() or ""
            caption = table["description"][idx].as_py() or table["text"][idx].as_py() or ""
            tags = f"{title} {tier} {model_type}".strip()

            batch.append((
                skin_id,
                title,
                caption,
                tags,
                raw_bytes,
                feat_blob,
                model_type,
                score,
                tier,
                l2_ratio,
            ))
            existing_ids.add(skin_id)
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            inserted += 1

            if len(batch) >= 2500:
                c.executemany(
                    """
                    INSERT OR IGNORE INTO skins (
                        skin_id, title, caption, tags, image_bytes, feature_vec,
                        model_type, quality_score, quality_tier, layer2_ratio
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    batch,
                )
                conn.commit()
                batch.clear()

                elapsed = time.time() - t_start
                rate = (idx + 1) / max(1e-3, elapsed)
                print(f"  -> Processed {idx+1:,}/{total_rows:,} ({rate:.0f} skins/s) | Kept: {inserted:,} | Filtered: {skipped_low_quality:,}")

        except Exception:
            continue

    if batch:
        c.executemany(
            """
            INSERT OR IGNORE INTO skins (
                skin_id, title, caption, tags, image_bytes, feature_vec,
                model_type, quality_score, quality_tier, layer2_ratio
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            batch,
        )
        conn.commit()
        batch.clear()

    total_time = time.time() - t_start
    print(f"\n[+] Split {split_idx+1} Complete in {total_time:.1f}s:")
    print(f"    - Kept High Quality: {inserted:,} (Top: {tier_counts.get('top_tier',0):,}, High: {tier_counts.get('high',0):,}, Medium: {tier_counts.get('medium',0):,})")
    print(f"    - Filtered Slag/Low: {skipped_low_quality:,}")
    print(f"    - Skipped Existing:  {skipped_existing:,}")


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"[*] Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    init_db(conn)

    print("[*] Loading existing skin IDs from database...")
    c = conn.cursor()
    c.execute("SELECT skin_id FROM skins;")
    existing_ids = set(r[0] for r in c.fetchall())
    print(f"[+] Loaded {len(existing_ids):,} existing skins in database.")

    for split_idx in range(TOTAL_SPLITS):
        process_split(split_idx, conn, existing_ids)

    c.execute("SELECT count(*) FROM skins;")
    final_count = c.fetchone()[0]
    print("\n=======================================================")
    print(f"[+] ALL 7 SPLITS PROCESSED! Total skins in DB: {final_count:,}")
    print("[*] Optimizing FTS5 index...")
    c.execute("INSERT INTO skins_fts(skins_fts) VALUES('optimize');")
    conn.commit()
    conn.close()
    print("[+] Database optimization complete! SkinForge RAG is primed with full 900k quality dataset.")


if __name__ == "__main__":
    main()
