#!/usr/bin/env python3
"""
SkinForge MCP Server Entry Point (v1.3.0).
Runs the SkinForge Model Context Protocol (MCP) server over stdio for LLM integration.
"""

import os
import sys

__version__ = "1.3.0"

# Ensure package root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skinforge.mcp_server import main

if __name__ == "__main__":
    main()
