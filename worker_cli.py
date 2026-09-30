from __future__ import annotations

import argparse
import json
import sys

from .cli import main as _cli_main


def _print(value) -> None:
    print(json.dumps(value, default=str, indent=2, ensure_ascii=False))


def _database_reset() -> None:
    from .database_admin import (
        DATABASE_RESET_CONFIRMATION,
        DatabaseResetError,
        database_reset_warning,
        total_reset_database,
    )

    parser = argparse.ArgumentParser(prog=f"{sys.argv[0]} {sys.argv[1]}")
    parser.add_argument(
        "--confirm",
        default="",
        help=f"required exact confirmation: {DATABASE_RESET_CONFIRMATION}",
    )
    args = parser.parse_args(sys.argv[2:])

    _print(database_reset_warning())
    if args.confirm != DATABASE_RESET_CONFIRMATION:
        raise SystemExit(2)
    try:
        _print(total_reset_database(confirmation=args.confirm))
    except DatabaseResetError as exc:
        _print({"ok": False, "error": {"code": exc.code, "message": str(exc)}})
        raise SystemExit(1) from exc


def main() -> None:
    """Run the normal CLI with the seven-tool managed worker surface."""
    if len(sys.argv) > 1 and sys.argv[1] in {"database-reset", "db-reset", "total-reset"}:
        _database_reset()
        return
    _cli_main(surface="worker")


if __name__ == "__main__":
    main()
