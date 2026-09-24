"""Compatibility shim for v0.1.1 imports."""
from .mcp_server import main, mcp

__all__ = ["mcp", "main"]

if __name__ == "__main__":
    main()
