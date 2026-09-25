#!/usr/bin/env python3
"""
SkinForge Full Dataset Downloader, Quality Filter & Ingestion Engine.
Downloads all 7 splits (900,000 skins) from Hugging Face:
  summykai/minecraft-skins-captioned-900k
Applies algorithmic aesthetic filtering (compute_aesthetic_score),
discards low-quality slag/noise, and populates SQLite FTS5 database.
"""

import sys
import os
import time
import base64
import io
import sqlite3
from pathlib import Path
from PIL import Image
import numpy as np
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

# Path setup
PROJECT_ROOT = Path("/mnt/storage/My/Projects/SkinForge-MCP")
sys.path.insert(0, str(PROJECT_ROOT))

from skinforge.validator import compute_aesthetic_score
from skinforge.canvas import MINECRAFT_UV_MAP

DB_PATH = PROJECT_ROOT / "data" / "skins_rag.db"
REPO_ID = "summykai/minecraft-skins-captioned-900k"
TOTAL_SPLITS = 7
MIN_SCORE_THRESHOLD = 0.35  # Filter out low-effort flat flood fills and noise


def init_db(conn: sqlite3.Connection):
    c = conn.cursor()
    # Check if quality columns exist
    c.execute("PRAGMA table_info(skins);")
    cols = [r[1] for r in c.fetchall()]
    if "quality_score" not in cols:
        print("[*] Adding quality_score column to skins table...")
        c.execute("ALTER TABLE skins ADD COLUMN quality_score REAL DEFAULT 0.0;")
    if "quality_tier" not in cols:
        print("[*] Adding quality_tier column to skins table...")
        c.execute("ALTER TABLE skins ADD COLUMN quality_tier TEXT DEFAULT 'medium';")
    
    c.execute("CREATE INDEX IF NOT EXISTS idx_skins_quality ON skins(quality_score);")
    conn.commit()


def process_split(split_idx: int, conn: sqlite3.Connection, existing_ids: set):
    filename = f"data/train-{split_idx:05d}-of-00007.parquet"
    print(f"\n=======================================================")
    print(f"[*] Processing Split {split_idx+1}/{TOTAL_SPLITS}: {filename}")
    print(f"=======================================================")

    t0 = time.time()
    parquet_path = hf_hub_download(
        repo_id=REPO_ID,
        filename=filename,
        repo_type="dataset"
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

    tier_counts = {"top_tier": 0, "high": 0, "medium": 0}

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
            im = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
            arr = np.array(im)

            # Algorithmic Quality Score
            aesthetic = compute_aesthetic_score(arr)
            score = aesthetic["score"]
            tier = aesthetic["tier"]

            # Quality Filtering
            if score < MIN_SCORE_THRESHOLD:
                skipped_low_quality += 1
                continue

            title = table["title"][idx].as_py() or ""
            caption = table["description"][idx].as_py() or table["text"][idx].as_py() or ""
            model_type = "default"

            batch.append((skin_id, title, caption, raw_bytes, model_type, score, tier))
            existing_ids.add(skin_id)
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            inserted += 1

            if len(batch) >= 2500:
                c.executemany("""
                    INSERT OR IGNORE INTO skins (skin_id, title, caption, image_bytes, model_type, quality_score, quality_tier)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, batch)
                conn.commit()
                batch.clear()

                elapsed = time.time() - t_start
                rate = (idx + 1) / elapsed
                print(f"  -> Processed {idx+1:,}/{total_rows:,} ({rate:.0f} skins/s) | Kept: {inserted:,} | Filtered: {skipped_low_quality:,}")

        except Exception as e:
            continue

    if batch:
        c.executemany("""
            INSERT OR IGNORE INTO skins (skin_id, title, caption, image_bytes, model_type, quality_score, quality_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, batch)
        conn.commit()
        batch.clear()

    total_time = time.time() - t_start
    print(f"\n[+] Split {split_idx+1} Complete in {total_time:.1f}s:")
    print(f"    - Kept High Quality: {inserted:,} (Top: {tier_counts.get('top_tier',0):,}, High: {tier_counts.get('high',0):,}, Medium: {tier_counts.get('medium',0):,})")
    print(f"    - Filtered Slag/Low: {skipped_low_quality:,}")
    print(f"    - Skipped Existing:  {skipped_existing:,}")


def main():
    print(f"[*] Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    init_db(conn)

    # Load existing IDs to prevent duplicates
    print("[*] Loading existing skin IDs from database...")
    c = conn.cursor()
    c.execute("SELECT skin_id FROM skins;")
    existing_ids = set(r[0] for r in c.fetchall())
    print(f"[+] Loaded {len(existing_ids):,} existing skins in database.")

    # Process all splits
    for split_idx in range(TOTAL_SPLITS):
        process_split(split_idx, conn, existing_ids)

    # Final count and optimization
    c.execute("SELECT count(*) FROM skins;")
    final_count = c.fetchone()[0]
    print(f"\n=======================================================")
    print(f"[+] ALL 7 SPLITS PROCESSED! Total skins in DB: {final_count:,}")
    print(f"[*] Optimizing FTS5 index...")
    c.execute("INSERT INTO skins_fts(skins_fts) VALUES('optimize');")
    conn.commit()
    conn.close()
    print("[+] Database optimization complete! SkinForge RAG is primed with full 900k quality dataset.")


if __name__ == '__main__':
    main()
