"""
RAG Search, Visual Search, Modular Lego Constructor & Database Packer MCP Tools (v2.0.0).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Union

from ..core import SkinCanvas
from ..rag import get_rag, pack_rag_database
from .protocol import MCPServer, handle_mcp_errors
from .schemas import RagPackConfigSchema


def register_rag_tools(server: MCPServer, session: Any) -> Dict[str, Any]:
    """Register RAG search, packing, remixing, visual search, and modular assembly tools."""

    @server.tool()
    @handle_mcp_errors(json_output=True)
    def skin_rag_pack(
        source_path: str,
        output_path: Optional[str] = None,
        metadata_path: Optional[str] = None,
        min_score: float = 0.0,
        overwrite: bool = False,
    ) -> str:
        """
        Pack a folder of .png skins or a .zip archive (with optional .json/.csv metadata) into a
        single compact, portable SQLite FTS5 + 299-dim CIELAB float16 database (.sfpack / .db).
        """
        cfg = RagPackConfigSchema(
            source_path=source_path,
            output_path=output_path,
            metadata_path=metadata_path,
            min_score=min_score,
            overwrite=overwrite,
        )
        res = pack_rag_database(
            source_path=cfg.source_path,
            output_path=cfg.output_path,
            metadata_path=cfg.metadata_path,
            min_score=cfg.min_score,
            overwrite=cfg.overwrite,
        )
        return json.dumps(res, indent=2)

    @server.tool()
    @handle_mcp_errors(json_output=True)
    def skin_search(
        query: str,
        limit: int = 5,
        min_quality: str = "medium",
        render_previews: bool = True,
    ) -> str:
        """Search across indexed Minecraft skins using SQLite FTS5 BM25 relevance ranking."""
        rag = get_rag()
        if not rag.is_available:
            return json.dumps(rag.get_unavailable_response(query=query), indent=2)

        results = rag.search(query=query, limit=min(limit, 20), min_quality=min_quality, render_previews=render_previews)
        if not results:
            return json.dumps({
                "status": "empty",
                "message": f"No skins found matching query: '{query}'. Total skins in DB: {rag.count()}",
                "results": [],
            }, indent=2)

        return json.dumps({
            "status": "success",
            "query": query,
            "total_results": len(results),
            "results": results,
        }, indent=2)

    @server.tool()
    @handle_mcp_errors(json_output=True)
    def skin_get_reference(
        skin_id: str,
        load_to_canvas: bool = False,
        as_ascii: bool = True,
    ) -> str:
        """Retrieve full details for a reference skin by ID from the RAG dataset."""
        rag = get_rag()
        if not rag.is_available:
            return json.dumps(rag.get_unavailable_response(query=skin_id), indent=2)

        skin_data = rag.get_skin(skin_id, as_canvas=load_to_canvas, as_ascii=as_ascii)
        if not skin_data:
            return json.dumps({"status": "not_found", "error": f"Skin '{skin_id}' not found in RAG database."})

        if load_to_canvas and "canvas" in skin_data:
            with session.lock:
                session.push_undo(action=f"load_reference:{skin_id}")
                session.canvas = skin_data["canvas"]
                session.model = skin_data.get("model_type", "default")
                session.mark_dirty()

        resp: Dict[str, Any] = {
            "status": "success",
            "skin_id": skin_data["skin_id"],
            "title": skin_data.get("title"),
            "caption": skin_data.get("caption"),
            "model_type": skin_data.get("model_type", "default"),
            "loaded_to_active_canvas": load_to_canvas,
        }
        if as_ascii:
            resp["palette"] = skin_data.get("palette")
            resp["parts"] = skin_data.get("parts")

        return json.dumps(resp, indent=2)

    @server.tool()
    @handle_mcp_errors(json_output=True)
    def skin_remix(
        base_skin_id: str,
        overlay_skin_id: str,
        parts_to_take: Optional[List[str]] = None,
        auto_fix: bool = True,
        save_path: Optional[str] = None,
    ) -> str:
        """Remix two reference skins from the RAG dataset or file paths."""
        rag = get_rag()
        if not rag.is_available and not (os.path.exists(base_skin_id) and os.path.exists(overlay_skin_id)):
            return json.dumps(rag.get_unavailable_response(), indent=2)

        remixed_canvas, info = rag.remix_skins(
            base_skin_id=base_skin_id,
            overlay_skin_id=overlay_skin_id,
            parts_to_take=parts_to_take,
            auto_fix=auto_fix,
            save_path=save_path,
        )
        with session.lock:
            session.push_undo(action=f"remix:{base_skin_id}+{overlay_skin_id}")
            session.canvas = remixed_canvas
            session.mark_dirty()

        return json.dumps({
            "status": "success",
            "message": f"Successfully remixed '{base_skin_id}' with '{overlay_skin_id}'.",
            "preview_3d_path": info.get("preview_3d"),
            "saved_to": save_path,
        }, indent=2)

    @server.tool()
    @handle_mcp_errors(json_output=True)
    def skin_rag_status() -> str:
        """Get the status of the SkinForge RAG database (number of indexed skins, database path)."""
        rag = get_rag()
        count = rag.count()
        if count == 0:
            info = rag.get_unavailable_response()
            info["database_size_mb"] = round(os.path.getsize(rag.db_path) / (1024 * 1024), 2) if os.path.exists(rag.db_path) else 0
            return json.dumps(info, indent=2)

        return json.dumps({
            "status": "ready",
            "available": True,
            "total_indexed_skins": count,
            "database_path": str(rag.db_path),
            "database_size_mb": round(os.path.getsize(rag.db_path) / (1024 * 1024), 2) if os.path.exists(rag.db_path) else 0,
        }, indent=2)

    @server.tool()
    @handle_mcp_errors(json_output=True)
    def skin_part_search(
        category: str,
        query: str,
        limit: int = 5,
        min_quality: str = "medium",
        render_previews: bool = True,
    ) -> str:
        """Search for specific anatomical components (hair, face, torso, arms, legs, outfit)."""
        rag = get_rag()
        if not rag.is_available:
            return json.dumps(rag.get_unavailable_response(query=query), indent=2)

        results = rag.part_search(
            category=category,
            query=query,
            limit=limit,
            min_quality=min_quality,
            render_previews=render_previews,
        )
        return json.dumps({
            "status": "success",
            "category": category,
            "query": query,
            "total_results": len(results),
            "results": results,
        }, indent=2)

    @server.tool()
    @handle_mcp_errors(json_output=True)
    def skin_assemble(
        components: Dict[str, str],
        auto_blend_seams: bool = True,
        auto_fix: bool = True,
    ) -> str:
        """Lego Constructor: Assemble a complete Minecraft skin from modular component sources."""
        rag = get_rag()
        resolved_components: Dict[str, Union[str, SkinCanvas]] = {}
        for mod, src in components.items():
            if src == "active":
                resolved_components[mod] = session.canvas
            else:
                if not os.path.exists(src) and not rag.is_available:
                    return json.dumps(rag.get_unavailable_response(query=src), indent=2)
                resolved_components[mod] = src

        assembled_canvas, summary = rag.assemble_modules(
            components=resolved_components,
            base_canvas=session.canvas,
            auto_blend_seams=auto_blend_seams,
            auto_fix=auto_fix,
        )
        with session.lock:
            session.push_undo(action="assemble_skin")
            session.canvas = assembled_canvas
            session.mark_dirty()

        return json.dumps({
            "status": "success",
            "message": f"Successfully assembled skin from {list(components.keys())}.",
            "summary": summary,
            "preview_3d_path": summary.get("preview_3d_path"),
        }, indent=2)

    @server.tool()
    @handle_mcp_errors(json_output=True)
    def skin_search_by_image(
        image_path: str,
        limit: int = 5,
        min_quality: str = "medium",
        render_previews: bool = True,
    ) -> str:
        """Visual Reference Search: Find skins matching a concept image using 299-dim CIELAB pyramids."""
        if not os.path.exists(image_path):
            return json.dumps({"status": "error", "error": f"Reference image not found: {image_path}"})

        rag = get_rag()
        if not rag.is_available:
            return json.dumps(rag.get_unavailable_response(query=image_path), indent=2)

        results = rag.search_by_image(
            image_input=image_path,
            limit=limit,
            min_quality=min_quality,
            render_previews=render_previews,
        )
        return json.dumps({
            "status": "success",
            "query_image": image_path,
            "total_results": len(results),
            "results": results,
        }, indent=2)

    return {
        "skin_rag_pack": skin_rag_pack,
        "skin_search": skin_search,
        "skin_get_reference": skin_get_reference,
        "skin_remix": skin_remix,
        "skin_rag_status": skin_rag_status,
        "skin_part_search": skin_part_search,
        "skin_assemble": skin_assemble,
        "skin_search_by_image": skin_search_by_image,
    }
