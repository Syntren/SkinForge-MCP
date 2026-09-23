#!/usr/bin/env python3
"""
Dataset Preparation Script for Fine-Tuning Multimodal Model (Qwen2.5-VL) on SkinForge MCP.

Dataset source: summykai/minecraft-skins-captioned-900k
Outputs:
  - 15,000 processed samples in ChatML format with <tool_call> syntax for `skin_build`.
  - 50% multimodal (text prompt + 2D front projection reference image).
  - 50% text-only (text prompt only).
"""

import os
import sys
import json
import base64
import io
import argparse
from pathlib import Path
from PIL import Image
import numpy as np
from tqdm import tqdm
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

# Add SkinForge-MCP to sys.path so we can import canvas_to_ascii
SKINFORGE_PATH = "/mnt/storage/My/Projects/SkinForge-MCP"
if SKINFORGE_PATH not in sys.path:
    sys.path.insert(0, SKINFORGE_PATH)

from skinforge import canvas_to_ascii


def render_front_projection(im: Image.Image, scale: int = 4) -> Image.Image:
    """
    Renders a crisp 2D front projection of the Minecraft character
    with Layer 1 base and Layer 2 3D relief overlays.
    Returns an image of size (16*scale, 32*scale).
    """
    im = im.convert("RGBA")
    
    # Head Base & Hat Outer
    head_base = im.crop((8, 8, 16, 16))
    hat_outer = im.crop((40, 8, 48, 16))
    head = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    head.paste(head_base, (0, 0))
    head.paste(hat_outer, (0, 0), hat_outer)

    # Torso Base & Jacket Outer
    body_base = im.crop((20, 20, 28, 32))
    jacket_outer = im.crop((20, 36, 28, 48))
    body = Image.new("RGBA", (8, 12), (0, 0, 0, 0))
    body.paste(body_base, (0, 0))
    body.paste(jacket_outer, (0, 0), jacket_outer)

    # Right Arm Base & Sleeve Outer
    r_arm_base = im.crop((44, 20, 48, 32))
    r_sleeve_outer = im.crop((44, 36, 48, 48))
    r_arm = Image.new("RGBA", (4, 12), (0, 0, 0, 0))
    r_arm.paste(r_arm_base, (0, 0))
    r_arm.paste(r_sleeve_outer, (0, 0), r_sleeve_outer)

    # Left Arm Base & Sleeve Outer
    l_arm_base = im.crop((36, 52, 40, 64))
    l_sleeve_outer = im.crop((52, 52, 56, 64))
    l_arm = Image.new("RGBA", (4, 12), (0, 0, 0, 0))
    l_arm.paste(l_arm_base, (0, 0))
    l_arm.paste(l_sleeve_outer, (0, 0), l_sleeve_outer)

    # Right Leg Base & Pants Outer
    r_leg_base = im.crop((4, 20, 8, 32))
    r_pants_outer = im.crop((4, 36, 8, 48))
    r_leg = Image.new("RGBA", (4, 12), (0, 0, 0, 0))
    r_leg.paste(r_leg_base, (0, 0))
    r_leg.paste(r_pants_outer, (0, 0), r_pants_outer)

    # Left Leg Base & Pants Outer
    l_leg_base = im.crop((20, 52, 24, 64))
    l_pants_outer = im.crop((4, 52, 8, 64))
    l_leg = Image.new("RGBA", (4, 12), (0, 0, 0, 0))
    l_leg.paste(l_leg_base, (0, 0))
    l_leg.paste(l_pants_outer, (0, 0), l_pants_outer)

    # Assemble Front composite (16x32)
    front = Image.new("RGBA", (16, 32), (0, 0, 0, 0))
    front.paste(head, (4, 0), head)
    front.paste(body, (4, 8), body)
    front.paste(r_arm, (0, 8), r_arm)
    front.paste(l_arm, (12, 8), l_arm)
    front.paste(r_leg, (4, 20), r_leg)
    front.paste(l_leg, (8, 20), l_leg)

    return front.resize((16 * scale, 32 * scale), Image.Resampling.NEAREST)


def build_tool_call(palette: dict, parts: dict, model_type: str = "default") -> str:
    """Formats the skin into a deterministic <tool_call> string."""
    tool_args = {
        "palette": palette,
        "parts": parts,
        "model_type": model_type,
        "auto_fix": True
    }
    payload = {
        "name": "skin_build",
        "arguments": tool_args
    }
    return f"<tool_call>\n{json.dumps(payload, ensure_ascii=False)}\n</tool_call>"


def prepare_dataset(
    num_samples: int = 15000,
    output_dir: str = "./data",
    tolerance: int = 12,
    max_palette_size: int = 32
):
    output_path = Path(output_dir)
    images_dir = output_path / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    jsonl_file = output_path / "minecraft_skins_15k.jsonl"

    print(f"📥 Loading dataset shard from Hugging Face...")
    parquet_path = hf_hub_download(
        repo_id="summykai/minecraft-skins-captioned-900k",
        filename="data/train-00000-of-00007.parquet",
        repo_type="dataset"
    )
    print(f"✅ Shard ready at: {parquet_path}")

    table = pq.read_table(parquet_path)
    total_rows = len(table)
    print(f"📊 Shard rows available: {total_rows} (target subset: {num_samples})")

    samples_processed = 0
    multimodal_count = 0
    text_only_count = 0

    with open(jsonl_file, "w", encoding="utf-8") as out_f:
        pbar = tqdm(total=num_samples, desc="Processing skins")
        for i in range(total_rows):
            if samples_processed >= num_samples:
                break

            b64_img = table["image"][i].as_py()
            caption = table["text"][i].as_py() or table["description"][i].as_py() or "Minecraft character skin"
            caption = caption.strip()
            if not caption:
                continue

            try:
                raw_bytes = base64.b64decode(b64_img)
                skin_img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
                if skin_img.size != (64, 64):
                    continue

                # Encode skin into deterministic global palette & part-by-part ASCII grids
                palette, parts = canvas_to_ascii(skin_img, tolerance=tolerance, max_palette_size=max_palette_size)
                if not parts:
                    continue

                tool_call_str = build_tool_call(palette, parts)

                # 50% multimodal (even indices), 50% text-only (odd indices)
                is_multimodal = (samples_processed % 2 == 0)

                if is_multimodal:
                    ref_img = render_front_projection(skin_img, scale=4)
                    rel_img_path = f"images/ref_{samples_processed:05d}.png"
                    abs_img_path = images_dir / f"ref_{samples_processed:05d}.png"
                    ref_img.save(abs_img_path)

                    prompt_text = f"Create a Minecraft skin matching this character appearance: {caption}"
                    user_content = [
                        {"type": "image", "image": rel_img_path},
                        {"type": "text", "text": prompt_text}
                    ]
                    multimodal_count += 1
                else:
                    prompt_text = f"Create a Minecraft skin based on description: {caption}"
                    user_content = [
                        {"type": "text", "text": prompt_text}
                    ]
                    text_only_count += 1

                record = {
                    "id": f"skin_{samples_processed:05d}",
                    "messages": [
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": tool_call_str}
                    ]
                }

                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                samples_processed += 1
                pbar.update(1)

            except Exception as e:
                continue

        pbar.close()

    print(f"\n🎉 Dataset preparation finished!")
    print(f"   - Total samples: {samples_processed}")
    print(f"   - Multimodal samples (image + text): {multimodal_count}")
    print(f"   - Text-only samples: {text_only_count}")
    print(f"   - Saved JSONL: {jsonl_file}")
    print(f"   - Saved Images dir: {images_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare Minecraft skin dataset for VLM fine-tuning")
    parser.add_argument("--num-samples", type=int, default=15000, help="Number of samples to process (default: 15000)")
    parser.add_argument("--output-dir", type=str, default="./data", help="Output directory")
    parser.add_argument("--tolerance", type=int, default=12, help="Color clustering tolerance (default: 12)")
    parser.add_argument("--max-palette", type=int, default=32, help="Max palette size (default: 32)")

    args = parser.parse_args()
    prepare_dataset(
        num_samples=args.num_samples,
        output_dir=args.output_dir,
        tolerance=args.tolerance,
        max_palette_size=args.max_palette
    )
