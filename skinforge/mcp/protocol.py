"""
MCP Protocol Transport, Error Handling & Multimodal Helpers for SkinForge (v2.0.0).

Supports both the official `mcp` Python SDK (MCPServer / FastMCP) and a zero-dependency
self-contained JSON-RPC 2.0 stdio fallback server. Also includes fuzzy part-name suggestions
to eliminate LLM retry loops when a UV identifier is slightly mistyped.
"""

from __future__ import annotations

import base64
import difflib
import functools
import inspect
import io
import json
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union
from PIL import Image

from ..core.uv import MINECRAFT_UV_MAP

__version__ = "2.0.0"


@dataclass
class _ToolCallResult:
    """Normalized result wrapper guaranteeing a `.content` attribute across MCPServer, FastMCP, and tests."""
    content: List[Any]
    isError: bool = False


try:
    import mcp.types as types
    if hasattr(types, "ImageContent") and not hasattr(types.ImageContent, "mimeType"):
        try:
            types.ImageContent.mimeType = property(lambda self: getattr(self, "mime_type", "image/png"))  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        from mcp.server.mcpserver import MCPServer as _BaseMCPServer  # type: ignore[import-not-found]
    except ImportError:
        from mcp.server.fastmcp import FastMCP as _BaseMCPServer  # type: ignore[import-not-found]

    class MCPServer(_BaseMCPServer):  # type: ignore[misc]
        """Unified MCPServer subclass compatible with both MCPServer and FastMCP."""

        async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
            res = await super().call_tool(name, arguments or {})
            if hasattr(res, "content"):
                return res
            if isinstance(res, tuple) and len(res) >= 1 and isinstance(res[0], (list, tuple)):
                return _ToolCallResult(content=list(res[0]))
            if isinstance(res, (list, tuple)):
                return _ToolCallResult(content=list(res))
            return _ToolCallResult(content=[res])

except ImportError:
    class _FallbackTypes:
        @dataclass
        class TextContent:
            type: str = "text"
            text: str = ""

        @dataclass
        class ImageContent:
            type: str = "image"
            data: str = ""
            mime_type: str = "image/png"
            mimeType: str = "image/png"

            def __post_init__(self) -> None:
                if self.mime_type != "image/png" and self.mimeType == "image/png":
                    self.mimeType = self.mime_type
                elif self.mimeType != "image/png" and self.mime_type == "image/png":
                    self.mime_type = self.mimeType

        @dataclass
        class PromptMessage:
            role: str
            content: Any

        ContentBlock = Union[TextContent, ImageContent]

    types = _FallbackTypes()  # type: ignore[assignment]

    @dataclass
    class _ResourceInfo:
        uri: str
        name: str
        fn: Callable

    @dataclass
    class _PromptInfo:
        name: str
        fn: Callable

    class _ToolManager:
        def __init__(self) -> None:
            self._tools: Dict[str, Callable] = {}

    class MCPServer:  # type: ignore[no-redef]
        """Full JSON-RPC 2.0 stdio MCP server fallback when external `mcp` package is absent."""

        def __init__(self, name: str = "skinforge", instructions: Optional[str] = None) -> None:
            self.name = name
            self.instructions = instructions
            self._tool_manager = _ToolManager()
            self._resources: Dict[str, _ResourceInfo] = {}
            self._prompts: Dict[str, _PromptInfo] = {}

        def tool(self, name: Optional[str] = None) -> Callable:
            def decorator(fn: Callable) -> Callable:
                t_name = name or fn.__name__
                self._tool_manager._tools[t_name] = fn
                return fn
            return decorator

        def resource(self, uri: str) -> Callable:
            def decorator(fn: Callable) -> Callable:
                self._resources[uri] = _ResourceInfo(uri=uri, name=fn.__name__, fn=fn)
                return fn
            return decorator

        def prompt(self, name: str) -> Callable:
            def decorator(fn: Callable) -> Callable:
                self._prompts[name] = _PromptInfo(name=name, fn=fn)
                return fn
            return decorator

        def _invoke_tool_sync(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> _ToolCallResult:
            if name not in self._tool_manager._tools:
                raise ValueError(f"Unknown tool: {name}")
            fn = self._tool_manager._tools[name]
            res = fn(**(arguments or {}))
            if isinstance(res, list):
                content = [
                    item if hasattr(item, "type") else types.TextContent(type="text", text=str(item))
                    for item in res
                ]
            elif hasattr(res, "type"):
                content = [res]
            else:
                content = [types.TextContent(type="text", text=str(res))]
            return _ToolCallResult(content=content)

        async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> _ToolCallResult:
            return self._invoke_tool_sync(name, arguments)

        async def list_resources(self) -> List[_ResourceInfo]:
            return list(self._resources.values())

        async def list_prompts(self) -> List[_PromptInfo]:
            return list(self._prompts.values())

        @staticmethod
        def _build_tool_schema(t_name: str, fn: Callable) -> Dict[str, Any]:
            sig = inspect.signature(fn)
            properties: Dict[str, Any] = {}
            required: List[str] = []
            for p_name, param in sig.parameters.items():
                ann = str(param.annotation)
                if "int" in ann and "List" not in ann and "Dict" not in ann:
                    p_type = "integer"
                elif "float" in ann and "List" not in ann:
                    p_type = "number"
                elif "bool" in ann:
                    p_type = "boolean"
                elif "List" in ann or "list" in ann:
                    p_type = "array"
                elif "Dict" in ann or "dict" in ann:
                    p_type = "object"
                else:
                    p_type = "string"
                prop_schema: Dict[str, Any] = {"type": p_type}
                if param.default is not inspect.Parameter.empty:
                    prop_schema["default"] = param.default
                else:
                    required.append(p_name)
                properties[p_name] = prop_schema
            return {
                "name": t_name,
                "description": (fn.__doc__ or "").strip(),
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }

        @staticmethod
        def _serialize_content_block(block: Any) -> Dict[str, Any]:
            b_type = getattr(block, "type", "text")
            if b_type == "image":
                mime = getattr(block, "mimeType", getattr(block, "mime_type", "image/png"))
                return {
                    "type": "image",
                    "data": getattr(block, "data", ""),
                    "mimeType": mime,
                }
            return {
                "type": "text",
                "text": getattr(block, "text", str(block)),
            }

        def handle_jsonrpc_request(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            """Process a single JSON-RPC 2.0 request/notification dict and return response dict (or None)."""
            method = msg.get("method", "")
            req_id = msg.get("id")
            params = msg.get("params") or {}

            if req_id is None or method.startswith("notifications/"):
                return None

            try:
                if method == "initialize":
                    result: Dict[str, Any] = {
                        "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "resources": {"subscribe": False, "listChanged": False},
                            "prompts": {"listChanged": False},
                        },
                        "serverInfo": {
                            "name": self.name,
                            "version": __version__,
                        },
                    }
                    if self.instructions:
                        result["instructions"] = self.instructions
                elif method == "ping":
                    result = {}
                elif method == "tools/list":
                    result = {
                        "tools": [
                            self._build_tool_schema(t_name, fn)
                            for t_name, fn in self._tool_manager._tools.items()
                        ]
                    }
                elif method == "tools/call":
                    t_name = params.get("name", "")
                    t_args = params.get("arguments") or {}
                    if t_name not in self._tool_manager._tools:
                        close = difflib.get_close_matches(t_name, list(self._tool_manager._tools.keys()), n=3, cutoff=0.5)
                        hint = f" Did you mean: {close}?" if close else ""
                        return {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32602, "message": f"Unknown tool: {t_name}.{hint}"},
                        }
                    call_res = self._invoke_tool_sync(t_name, t_args)
                    result = {
                        "content": [self._serialize_content_block(b) for b in call_res.content],
                        "isError": bool(call_res.isError),
                    }
                elif method == "resources/list":
                    result = {
                        "resources": [
                            {
                                "uri": r.uri,
                                "name": r.name,
                                "description": (r.fn.__doc__ or "").strip(),
                                "mimeType": "text/plain",
                            }
                            for r in self._resources.values()
                        ]
                    }
                elif method == "resources/read":
                    uri = params.get("uri", "")
                    if uri not in self._resources:
                        return {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32602, "message": f"Unknown resource URI: {uri}"},
                        }
                    text_val = self._resources[uri].fn()
                    result = {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "text/plain",
                                "text": str(text_val),
                            }
                        ]
                    }
                elif method == "prompts/list":
                    result = {
                        "prompts": [
                            {
                                "name": p.name,
                                "description": (p.fn.__doc__ or "").strip(),
                            }
                            for p in self._prompts.values()
                        ]
                    }
                elif method == "prompts/get":
                    p_name = params.get("name", "")
                    if p_name not in self._prompts:
                        return {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32602, "message": f"Unknown prompt: {p_name}"},
                        }
                    p_obj = self._prompts[p_name]
                    p_msgs = p_obj.fn(**(params.get("arguments") or {}))
                    serialized_msgs = [
                        {
                            "role": getattr(m, "role", "user"),
                            "content": self._serialize_content_block(getattr(m, "content", m)),
                        }
                        for m in p_msgs
                    ]
                    result = {
                        "description": (p_obj.fn.__doc__ or "").strip(),
                        "messages": serialized_msgs,
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    }

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": result,
                }
            except Exception as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(exc)},
                }

        def run(self, transport: str = "stdio", input_stream: Any = None, output_stream: Any = None) -> None:
            """Run full JSON-RPC 2.0 stdio event loop reading from stdin and writing to stdout."""
            in_s = input_stream if input_stream is not None else sys.stdin
            out_s = output_stream if output_stream is not None else sys.stdout

            for raw_line in in_s:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception as exc:
                    err_resp = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": f"Parse error: {exc}"},
                    }
                    out_s.write(json.dumps(err_resp) + "\n")
                    out_s.flush()
                    continue

                if isinstance(msg, dict):
                    resp = self.handle_jsonrpc_request(msg)
                    if resp is not None:
                        out_s.write(json.dumps(resp) + "\n")
                        out_s.flush()


def handle_mcp_errors(json_output: bool = False, multimodal: bool = False) -> Callable:
    """
    Unified error-handling decorator for all SkinForge MCP tools.
    Catches exceptions cleanly and formats error responses consistently.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                if multimodal:
                    return [types.TextContent(type="text", text=f"Error in {fn.__name__}: {str(exc)}")]
                if json_output:
                    return json.dumps({"status": "error", "error": str(exc)}, indent=2)
                return f"Error: {str(exc)}"
        return wrapper
    return decorator


def validate_part_name(part_name: str) -> Optional[str]:
    """Validate a UV part identifier and return an actionable fuzzy suggestion if invalid."""
    if part_name in MINECRAFT_UV_MAP:
        return None
    valid_keys = list(MINECRAFT_UV_MAP.keys())
    matches = difflib.get_close_matches(part_name, valid_keys, n=5, cutoff=0.45)
    hint = f" Did you mean one of: {matches}?" if matches else ""
    return f"Error: Unknown part '{part_name}'.{hint} Read resource 'skin://uv-map' for all 72 valid UV part names."


def image_to_content(im: Image.Image) -> types.ImageContent:
    """Convert PIL Image into an MCP ImageContent object for multimodal LLM feedback."""
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
    try:
        return types.ImageContent(type="image", data=b64_str, mime_type="image/png", mimeType="image/png")
    except TypeError:
        try:
            return types.ImageContent(type="image", data=b64_str, mimeType="image/png")
        except TypeError:
            return types.ImageContent(type="image", data=b64_str, mime_type="image/png")
