#!/usr/bin/env python3
"""
SkinForge CLI Entry Point (v1.3.0).
Command-line interface for rendering, inspecting, packing RAG databases, and managing Minecraft skins.
"""

import argparse
import json
import os
import sys

__version__ = "1.3.0"

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skinforge import (
    SkinCanvas,
    SkinValidator,
    __version__ as sf_version,
    align_seams,
    assemble_skin,
    check_seams,
    compute_aesthetic_score,
    convert_skin_model,
    get_rag,
    pack_rag_database,
    render_3d_turnaround,
    render_composite_2d,
    render_turntable_gif,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="skinforge",
        description=f"SkinForge v{sf_version}: Advanced Minecraft Skin Creation, Quality Audit, RAG Packing & 3D Visualization",
    )
    parser.add_argument("--version", action="version", version=f"skinforge {sf_version}")
    subparsers = parser.add_subparsers(dest="command")

    # Render command
    p_render = subparsers.add_parser("render", help="Render 2D and 3D visual previews")
    p_render.add_argument("skin", help="Path to input 64x64 (or legacy 64x32) skin PNG")
    p_render.add_argument("--out3d", default=None, help="Output path for 3D turnaround image")
    p_render.add_argument("--out2d", default=None, help="Output path for 2D composite image")
    p_render.add_argument("--layer", choices=["both", "base", "outer"], default="both", help="Filter layers to render")

    # Turnaround GIF command
    p_gif = subparsers.add_parser("gif", help="Generate an animated 360-degree turntable GIF")
    p_gif.add_argument("skin", help="Path to input 64x64 skin PNG")
    p_gif.add_argument("--out", default="previews/turntable_360.gif", help="Output GIF path")
    p_gif.add_argument("--frames", type=int, default=16, help="Number of rotation frames")
    p_gif.add_argument("--layer", choices=["both", "base", "outer"], default="both", help="Filter layers for GIF")

    # Inspect command
    p_inspect = subparsers.add_parser("inspect", help="Inspect and audit skin layers and geometry")
    p_inspect.add_argument("skin", help="Path to input 64x64 (or 64x32) skin PNG")

    # Seams command
    p_seams = subparsers.add_parser("seams", help="Audit or align 3D cube edge wrap-around seams")
    p_seams.add_argument("skin", help="Path to input 64x64 skin PNG")
    p_seams.add_argument("--align", action="store_true", help="Automatically heal detected seams")
    p_seams.add_argument("--mode", default="blend", choices=["blend", "copy_a_to_b"], help="Alignment mode")
    p_seams.add_argument("--out", default=None, help="Output path if aligned (overwrites input if omitted)")

    # Convert model command
    p_conv = subparsers.add_parser("convert", help="Convert skin between classic Steve (4px) and Alex slim (3px)")
    p_conv.add_argument("skin", help="Path to input 64x64 (or 64x32) skin PNG")
    p_conv.add_argument("--to", required=True, choices=["slim", "default", "classic"], help="Target model format")
    p_conv.add_argument("--out", default=None, help="Output path (overwrites input if omitted)")

    # Mirror command
    p_mirror = subparsers.add_parser("mirror", help="Mirror a limb from right to left or vice versa")
    p_mirror.add_argument("skin", help="Path to input 64x64 skin PNG")
    p_mirror.add_argument("--from-limb", default="right_arm", choices=["right_arm", "left_arm", "right_leg", "left_leg"])
    p_mirror.add_argument("--to-limb", default="left_arm", choices=["right_arm", "left_arm", "right_leg", "left_leg"])
    p_mirror.add_argument("--out", default=None, help="Output path (overwrites input if omitted)")

    # View command
    subparsers.add_parser("view", help="Start interactive 3D WebGL SkinForge Studio viewer")

    # MCP server command
    subparsers.add_parser("mcp", help="Start SkinForge Model Context Protocol (MCP) server for LLMs")

    # Lego Constructor Assemble command
    p_assemble = subparsers.add_parser("assemble", help="Lego Constructor: Assemble modular skin components")
    p_assemble.add_argument("--hair", default=None, help="Skin ID or PNG path for hair")
    p_assemble.add_argument("--face", default=None, help="Skin ID or PNG path for face/eyes")
    p_assemble.add_argument("--torso", default=None, help="Skin ID or PNG path for torso/shirt")
    p_assemble.add_argument("--arms", default=None, help="Skin ID or PNG path for arms/sleeves")
    p_assemble.add_argument("--legs", default=None, help="Skin ID or PNG path for legs/pants")
    p_assemble.add_argument("--outfit", default=None, help="Skin ID or PNG path for full outfit")
    p_assemble.add_argument("--base", default=None, help="Optional base skin ID or PNG to inherit unspecified parts")
    p_assemble.add_argument("--out", default="assembled_skin.png", help="Output PNG path")
    p_assemble.add_argument("--preview", action="store_true", help="Also generate 3D turnaround and 2D composite previews")

    # Search command
    p_search = subparsers.add_parser("search", help="Search Minecraft skins RAG database")
    p_search.add_argument("query", help="Text search query")
    p_search.add_argument("--limit", type=int, default=5, help="Maximum results to return")
    p_search.add_argument("--min-quality", choices=["all", "low", "medium", "high"], default="medium", help="Minimum aesthetic quality tier")

    # Part search command
    p_part_search = subparsers.add_parser("part-search", help="Search for specific anatomical module")
    p_part_search.add_argument("category", choices=["hair", "face", "torso", "arms", "legs", "outfit"], help="Anatomical module category")
    p_part_search.add_argument("query", help="Text search query")
    p_part_search.add_argument("--limit", type=int, default=5, help="Maximum results to return")
    p_part_search.add_argument("--min-quality", choices=["all", "low", "medium", "high"], default="medium", help="Minimum aesthetic quality tier")

    # RAG Pack command (New in v1.3.0)
    p_pack = subparsers.add_parser(
        "rag-pack",
        help="Pack a folder of .png skins or a .zip archive into a portable SQLite FTS5 + CIELAB float16 database (.sfpack / .db)",
    )
    p_pack.add_argument("source", help="Path to folder containing .png skins or .zip archive")
    p_pack.add_argument("--out", default="data/skins_rag.db", help="Output database file path (.sfpack or .db)")
    p_pack.add_argument("--metadata", default=None, help="Optional path to .json or .csv metadata file")
    p_pack.add_argument("--min-score", type=float, default=0.0, help="Minimum aesthetic_score threshold (0.0 to 1.0)")
    p_pack.add_argument("--overwrite", action="store_true", help="Overwrite existing output database file")

    args = parser.parse_args()

    if args.command == "render":
        out3d = args.out3d or "previews/3d_turnaround.png"
        out2d = args.out2d or "previews/2d_composite.png"
        print(f"[*] Rendering 3D turnaround ({args.layer}) to '{out3d}'...")
        render_3d_turnaround(args.skin, out3d, layer_mode=args.layer)
        print(f"[*] Rendering 2D composite to '{out2d}'...")
        render_composite_2d(args.skin, out2d)
        print("[+] Rendering complete!")

    elif args.command == "gif":
        print(f"[*] Generating {args.frames}-frame 360 turntable ({args.layer}) to '{args.out}'...")
        render_turntable_gif(args.skin, args.out, frames=args.frames, layer_mode=args.layer)
        print("[+] Turntable GIF generated!")

    elif args.command == "inspect":
        validator = SkinValidator(args.skin)
        valid, report = validator.validate()
        print(report)

    elif args.command == "seams":
        canvas = SkinCanvas()
        canvas.load_png(args.skin)
        discrepancies = check_seams(canvas)
        if not discrepancies:
            print("[+] 3D Seams check PASSED! All adjacent cube edges are well-aligned.")
        else:
            print(f"[!] Detected {len(discrepancies)} seam discrepancies.")
            for d in discrepancies:
                print(f"  - {d['seam_name']}: {d['mismatch_count']} mismatched pixels")
            if args.align:
                count = align_seams(canvas, mode=args.mode)
                out_p = args.out or args.skin
                canvas.export_png(out_p)
                print(f"[+] Automatically healed {count} edge pixels -> saved to '{out_p}'")

    elif args.command == "convert":
        canvas = SkinCanvas()
        canvas.load_png(args.skin)
        res = convert_skin_model(canvas, target_model=args.to)
        out_p = args.out or args.skin
        canvas.export_png(out_p)
        print(f"[+] {res['message']} -> saved to '{out_p}'")

    elif args.command == "mirror":
        out_path = args.out or args.skin
        canvas = SkinCanvas()
        canvas.load_png(args.skin)
        canvas.mirror_limb(args.from_limb, args.to_limb)
        canvas.export_png(out_path)
        print(f"[+] Mirrored {args.from_limb} -> {args.to_limb} saved to '{out_path}'")

    elif args.command == "view":
        viewer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer.py")
        import runpy
        runpy.run_path(viewer_path, run_name="__main__")

    elif args.command == "mcp":
        from skinforge.mcp_server import main as run_mcp
        run_mcp()

    elif args.command == "rag-pack":
        print(f"[*] Packing skins from '{args.source}' into '{args.out}'...")
        res = pack_rag_database(
            source_path=args.source,
            output_path=args.out,
            metadata_path=args.metadata,
            min_score=args.min_score,
            overwrite=args.overwrite,
        )
        print(json.dumps(res, indent=2))
        print(f"[+] Successfully packed {res['packed_count']} skins into '{res['output_path']}' ({res['database_size_mb']} MB)!")

    elif args.command == "assemble":
        rag = get_rag()
        components = {}
        for mod in ["hair", "face", "torso", "arms", "legs", "outfit"]:
            val = getattr(args, mod, None)
            if val:
                components[mod] = val

        if not components:
            print("[!] Error: No components specified. Use --hair, --torso, --legs, etc.")
            sys.exit(1)

        print(f"[*] Assembling skin from modules: {list(components.keys())}...")
        base_c = None
        if args.base:
            base_c = SkinCanvas()
            if os.path.exists(args.base):
                base_c.load_png(args.base)
            elif rag.is_available:
                s_data = rag.get_skin(args.base, as_canvas=True, as_ascii=False)
                if s_data and "canvas" in s_data:
                    base_c = s_data["canvas"]

        assembled_canvas, summary = rag.assemble_modules(
            components=components,
            base_canvas=base_c,
            auto_blend_seams=True,
            auto_fix=True,
        )

        assembled_canvas.export_png(args.out)
        print(f"[+] Successfully assembled skin saved to '{args.out}'!")
        print(f"    - Aesthetic Score: {summary.get('aesthetic_score')} ({summary.get('aesthetic_tier')})")
        print(f"    - Applied Modules: {', '.join(summary.get('applied_modules', []))}")
        print(f"    - Seam issues detected & healed: {summary.get('seam_issues_detected', 0)}")

        if args.preview:
            p3d = os.path.splitext(args.out)[0] + "_3d.png"
            p2d = os.path.splitext(args.out)[0] + "_2d.png"
            render_3d_turnaround(assembled_canvas, p3d)
            render_composite_2d(assembled_canvas, p2d)
            print(f"[+] Generated previews: '{p3d}' and '{p2d}'")

    elif args.command == "search":
        rag = get_rag()
        if not rag.is_available:
            print(json.dumps(rag.get_unavailable_response(query=args.query), indent=2))
            return
        results = rag.search(args.query, limit=args.limit, min_quality=args.min_quality, render_previews=False)
        print(f"[*] Found {len(results)} skins matching '{args.query}' (min quality: {args.min_quality}):")
        for i, r in enumerate(results, 1):
            print(f"  {i}. [{r['skin_id']}] {r['title'] or r['caption'][:60]} (Quality: {r['quality_score']}, Tier: {r['quality_tier']})")

    elif args.command == "part-search":
        rag = get_rag()
        if not rag.is_available:
            print(json.dumps(rag.get_unavailable_response(query=args.query), indent=2))
            return
        results = rag.part_search(args.category, args.query, limit=args.limit, min_quality=args.min_quality, render_previews=False)
        print(f"[*] Found {len(results)} {args.category} modules matching '{args.query}':")
        for i, r in enumerate(results, 1):
            print(f"  {i}. [{r['skin_id']}] {r['caption'][:60]} (Quality: {r['quality_score']}, Tier: {r['quality_tier']})")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
