from __future__ import annotations

import argparse
import json

from .importer import BigBangScanner, serialize_discovery
from .maintenance import MangoMaintainer
from .runtime import get_service


def main() -> None:
    parser = argparse.ArgumentParser(prog="mangome")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="non-destructive Big-Bang filesystem discovery")
    scan.add_argument("roots", nargs="+")

    resolve = sub.add_parser("resolve", help="resolve known family/contract/slice identity")
    resolve.add_argument("query")

    status = sub.add_parser("status", help="show deterministic family status")
    status.add_argument("family_id")

    sub.add_parser("refresh", help="refresh materialized family views")

    args = parser.parse_args()
    svc = get_service()
    if args.cmd == "scan":
        result = serialize_discovery(BigBangScanner(svc).scan(args.roots))
    elif args.cmd == "resolve":
        result = svc.resolve(args.query)
    elif args.cmd == "status":
        result = svc.status(args.family_id)
    else:
        result = MangoMaintainer(svc).refresh_all_family_views()
    print(json.dumps(result, default=str, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
