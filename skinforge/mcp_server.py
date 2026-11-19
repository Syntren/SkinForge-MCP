"""
SkinForge Model Context Protocol (MCP) Server Facade (v2.0.0).

Cleanly wires the modular `skinforge.mcp` package (session, editing, procedural shading,
semantic region painting, 2D primitives, high-level design, multimodal critic, RAG,
resources, and prompts) while preserving 100% backward compatibility for direct imports.
"""

from __future__ import annotations

import os
from typing import Optional

from .core import SkinSession
from .mcp import (
    BatchActionSchema,
    MCPServer,
    PixelCoordSchema,
    RagPackConfigSchema,
    _ToolCallResult,
    __version__,
    execute_preset_on_canvas as _execute_preset_on_canvas,
    handle_mcp_errors,
    image_to_content as _image_to_content,
    register_audit_tools,
    register_design_tools,
    register_editing_tools,
    register_rag_tools,
    register_resources_and_prompts,
    register_session_tools,
    types,
    validate_part_name as _validate_part_name,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Active thread-safe session singleton
session = SkinSession(project_root=PROJECT_ROOT)

# Load AI agent system instructions
INSTRUCTIONS_PATH = os.path.join(PROJECT_ROOT, "instructions.md")
if not os.path.exists(INSTRUCTIONS_PATH):
    INSTRUCTIONS_PATH = os.path.join(os.path.dirname(__file__), "instructions.md")

instructions_content: Optional[str] = None
if os.path.exists(INSTRUCTIONS_PATH):
    try:
        with open(INSTRUCTIONS_PATH, "r", encoding="utf-8") as _f:
            instructions_content = _f.read()
    except Exception:
        pass

server = MCPServer(
    name="skinforge",
    instructions=instructions_content,
)

# Register all modular tool groups
_session_tools = register_session_tools(server, session, PROJECT_ROOT)
_design_tools = register_design_tools(server, session)
_editing_tools = register_editing_tools(server, session, skin_save_fn=_session_tools["skin_save"])
_audit_tools = register_audit_tools(server, session, PROJECT_ROOT)
_rag_tools = register_rag_tools(server, session)
_resources_prompts = register_resources_and_prompts(
    server,
    get_session_info_fn=_session_tools["skin_get_session_info"],
)

# Re-export all registered tool functions at module level for backward compatibility
for _registry in (
    _session_tools,
    _design_tools,
    _editing_tools,
    _audit_tools,
    _rag_tools,
    _resources_prompts,
):
    globals().update(_registry)


def main() -> None:
    """Run the SkinForge MCP Server over stdio."""
    server.run("stdio")


if __name__ == "__main__":
    main()
