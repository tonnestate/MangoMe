#!/usr/bin/env python3
"""Repair managed bindings and run MangoMe's bounded zero-touch deployment bootstrap."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="/root/MangoMe-latest")
    parser.add_argument("--workspace", default="/root")
    parser.add_argument("--client", action="append", choices=["codex", "claude-code", "all"], default=["codex"])
    parser.add_argument("--database", default="mangome")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    src = repo / "src"
    if not src.is_dir():
        raise SystemExit(f"repo source not found: {src}")
    sys.path.insert(0, str(src))

    from mangome.operability import setup_clients

    result = setup_clients(
        args.workspace,
        clients=args.client,
        backend="mongo",
        database=args.database,
        dry_run=False,
    )
    bootstrap = result.get("bootstrap") or {}
    print("MangoMe runtime binding repaired; bounded zero-touch bootstrap completed or reported its blocker.")
    print(f"bootstrap={bootstrap.get('status', 'UNKNOWN')} database_ready={bootstrap.get('database_ready')}")
    print(f"workspace={result['workspace_root']} database={args.database} clients={','.join(args.client)}")
    print("Restart the agent/MCP session so the new managed binding is loaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
