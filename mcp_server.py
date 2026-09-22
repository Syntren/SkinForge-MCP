#!/usr/bin/env python3
"""
SkinForge MCP Server Entry Point.
Runs the SkinForge Model Context Protocol (MCP) server over stdio for LLM integration.
"""

import sys
import os

# Ensure package root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skinforge.mcp_server import main

if __name__ == "__main__":
    main()
