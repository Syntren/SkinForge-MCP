"""
SkinForge Modular MCP Package (v2.0.0).

Cleanly separates MCP transport, Pydantic schemas, session management, editing/shading/region
tools, high-level design tools, multimodal critique/auditing, RAG tools, and resources/prompts.
"""

from .protocol import (
    MCPServer,
    _ToolCallResult,
    __version__,
    handle_mcp_errors,
    image_to_content,
    types,
    validate_part_name,
)
from .schemas import BatchActionSchema, PixelCoordSchema, RagPackConfigSchema
from .tools_audit import register_audit_tools
from .tools_design import execute_preset_on_canvas, register_design_tools
from .tools_editing import register_editing_tools
from .tools_rag import register_rag_tools
from .tools_session import register_session_tools
from .resources import register_resources_and_prompts

__all__ = [
    "__version__",
    "MCPServer",
    "types",
    "_ToolCallResult",
    "handle_mcp_errors",
    "image_to_content",
    "validate_part_name",
    "PixelCoordSchema",
    "BatchActionSchema",
    "RagPackConfigSchema",
    "execute_preset_on_canvas",
    "register_session_tools",
    "register_design_tools",
    "register_editing_tools",
    "register_audit_tools",
    "register_rag_tools",
    "register_resources_and_prompts",
]
