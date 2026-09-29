"""Convenience entry point for `mcp dev server.py` using the bounded worker facade."""
from mangome.worker_mcp_server import mcp

__all__ = ["mcp"]
