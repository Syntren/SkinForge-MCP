#!/usr/bin/env python3
"""
SkinForge CLI Entry Point.
Command-line interface for rendering, inspecting, and managing Minecraft skins.
"""

import sys
import os
import argparse

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skinforge import (
    SkinCanvas,
    render_composite_2d,
    render_3d_turnaround,
    render_turntable_gif,
    SkinValidator,
    check_seams,
    align_seams,
    convert_skin_model
)

def main():
    parser = argparse.ArgumentParser(
        prog="skinforge",
        description="SkinForge: Advanced Minecraft Skin Creation, Quality Audit & 3D Visualization"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Render command
    p_render = subparsers.add_parser("render", help="Render 2D and 3D visual previews")
    p_render.add_argument("skin", help="Path to input 64x64 skin PNG")
    p_render.add_argument("--out3d", default=None, help="Output path for 3D turnaround image")
    p_render.add_argument("--out2d", default=None, help="Output path for 2D composite image")
    p_render.add_argument("--layer", choices=["both", "base", "outer"], default="both", help="Filter layers to render (both, base, outer)")

    # Turnaround GIF command
    p_gif = subparsers.add_parser("gif", help="Generate an animated 360-degree turntable GIF")
    p_gif.add_argument("skin", help="Path to input 64x64 skin PNG")
    p_gif.add_argument("--out", default="previews/turntable_360.gif", help="Output GIF path")
    p_gif.add_argument("--frames", type=int, default=16, help="Number of rotation frames")
    p_gif.add_argument("--layer", choices=["both", "base", "outer"], default="both", help="Filter layers for GIF (both, base, outer)")

    # Inspect command
    p_inspect = subparsers.add_parser("inspect", help="Inspect and audit skin layers and geometry")
    p_inspect.add_argument("skin", help="Path to input 64x64 skin PNG")

    # Seams command
    p_seams = subparsers.add_parser("seams", help="Audit or align 3D cube edge wrap-around seams")
    p_seams.add_argument("skin", help="Path to input 64x64 skin PNG")
    p_seams.add_argument("--align", action="store_true", help="Automatically heal detected seams")
    p_seams.add_argument("--mode", default="blend", choices=["blend", "copy_a_to_b"], help="Alignment mode")
    p_seams.add_argument("--out", default=None, help="Output path if aligned (overwrites input if omitted)")

    # Convert model command
    p_conv = subparsers.add_parser("convert", help="Convert skin between classic Steve (4px) and Alex slim (3px)")
    p_conv.add_argument("skin", help="Path to input 64x64 skin PNG")
    p_conv.add_argument("--to", required=True, choices=["slim", "default"], help="Target model format")
    p_conv.add_argument("--out", default=None, help="Output path (overwrites input if omitted)")

    # Mirror command
    p_mirror = subparsers.add_parser("mirror", help="Mirror a limb from right to left or vice versa")
    p_mirror.add_argument("skin", help="Path to input 64x64 skin PNG")
    p_mirror.add_argument("--from-limb", default="right_arm", choices=["right_arm", "left_arm", "right_leg", "left_leg"])
    p_mirror.add_argument("--to-limb", default="left_arm", choices=["right_arm", "left_arm", "right_leg", "left_leg"])
    p_mirror.add_argument("--out", default=None, help="Output path (overwrites input if omitted)")

    # View command
    p_view = subparsers.add_parser("view", help="Start interactive 3D WebGL skin viewer")

    # MCP server command
    p_mcp = subparsers.add_parser("mcp", help="Start SkinForge Model Context Protocol (MCP) server for LLMs")

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

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
