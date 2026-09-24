from __future__ import annotations

import argparse
import json
import os

from .importer import BigBangScanner, serialize_discovery, serialize_git_discovery
from .interlingua import UAICompiler, render_uai_result
from .maintenance import MangoMaintainer
from .operability import attest_client, doctor, setup_clients
from .runtime import get_service, health_snapshot, refresh_workspace_attachment


def _print(value) -> None:
    print(json.dumps(value, default=str, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(prog="mangome")
    sub = parser.add_subparsers(dest="cmd", required=True)

    setup = sub.add_parser("setup", help="zero-touch setup for supported local agent clients")
    setup.add_argument("--workspace", default=None, help="workspace root; defaults to Git root/current directory")
    setup.add_argument("--client", action="append", choices=["auto", "all", "claude-code", "codex"], default=None)
    setup.add_argument("--backend", choices=["mongo", "memory"], default="mongo")
    setup.add_argument("--database", default="mangome")
    setup.add_argument("--dry-run", action="store_true")

    doctor_cmd = sub.add_parser("doctor", help="inspect client binding drift and optionally repair managed configuration")
    doctor_cmd.add_argument("--workspace", default=None)
    doctor_cmd.add_argument("--client", action="append", choices=["claude-code", "codex"], default=None)
    doctor_cmd.add_argument("--backend", choices=["mongo", "memory"], default="mongo")
    doctor_cmd.add_argument("--database", default="mangome")
    doctor_cmd.add_argument("--repair", action="store_true")

    client_attest = sub.add_parser("attest-client", help="prove static/effective MangoMe binding for a supported client")
    client_attest.add_argument("client", choices=["claude-code", "codex"])
    client_attest.add_argument("--workspace", default=None)
    client_attest.add_argument("--backend", choices=["mongo", "memory"], default="mongo")
    client_attest.add_argument("--database", default="mangome")
    client_attest.add_argument("--static-only", action="store_true")

    attach = sub.add_parser("attach", help="explicitly refresh automatic workspace attachment/discovery")
    attach.add_argument("--workspace", default=None)

    scan = sub.add_parser("scan", help="non-destructive Big-Bang filesystem/Git discovery")
    scan.add_argument("roots", nargs="+")
    scan.add_argument("--no-git", action="store_true")

    resolve = sub.add_parser("resolve", help="resolve known family/contract/slice identity")
    resolve.add_argument("query")

    status = sub.add_parser("status", help="show deterministic family status")
    status.add_argument("family_id")

    project = sub.add_parser("project", help="show deterministic project overview")
    project.add_argument("project_ref")

    sub.add_parser("health", help="show backend, schema and automatic workspace readiness")
    sub.add_parser("refresh", help="refresh materialized family views")

    diagnose = sub.add_parser("diagnose", help="run non-destructive maintenance diagnostics")
    diagnose.add_argument("--stale-hours", type=float, default=24.0)

    migrate = sub.add_parser("migrate", help="inspect/apply registered schema migrations")
    migrate.add_argument("--apply", action="store_true", help="persist migrations; default is dry-run")

    approvals = sub.add_parser("approvals", help="list approval requests")
    approvals.add_argument("--status", default=None)
    approvals.add_argument("--subject", default=None)

    approve = sub.add_parser("approve", help="owner approval; reads MANGOME_APPROVAL_TOKEN from environment")
    approve.add_argument("approval_id")
    approve.add_argument("--actor", required=True)
    approve.add_argument("--decision-ref", default=None)

    reject = sub.add_parser("reject", help="owner rejection; reads MANGOME_APPROVAL_TOKEN from environment")
    reject.add_argument("approval_id")
    reject.add_argument("--actor", required=True)
    reject.add_argument("--decision-ref", default=None)

    attest = sub.add_parser("attest-evidence", help="attest evidence with runtime capability from environment")
    attest.add_argument("evidence_id")
    attest.add_argument("--actor", required=True)
    attest.add_argument("--authority", choices=["VERIFIER", "OWNER"], default="VERIFIER")

    verify = sub.add_parser("verify", help="verify a slice using MANGOME_VERIFIER_TOKEN from environment")
    verify.add_argument("slice_id")
    verify.add_argument("--actor", required=True)

    uai = sub.add_parser("uai-context", help="compile a compact UAI/1 execution packet")
    uai.add_argument("family_id")
    uai.add_argument("--slice", dest="slice_id", default=None)

    uai_expand = sub.add_parser("uai-expand", help="expand and hash-verify a UAI/1 context packet")
    uai_expand.add_argument("wire")

    uai_render = sub.add_parser("uai-render", help="render a UAI/1R result into human-readable text")
    uai_render.add_argument("result_json")
    uai_render.add_argument("--language", choices=["en", "de"], default="en")
    uai_render.add_argument("--context-hash", default=None)

    args = parser.parse_args()

    # Operability commands intentionally do not require a live MangoMe backend.
    if args.cmd == "setup":
        clients = args.client or ["auto"]
        _print(setup_clients(
            args.workspace or os.getcwd(), clients=clients, backend=args.backend,
            database=args.database, dry_run=args.dry_run,
        ))
        return
    if args.cmd == "doctor":
        clients = args.client or ["claude-code", "codex"]
        _print(doctor(
            args.workspace, clients=clients, backend=args.backend,
            database=args.database, repair=args.repair,
        ))
        return
    if args.cmd == "attest-client":
        _print(attest_client(
            args.client, args.workspace or os.getcwd(), backend=args.backend,
            database=args.database, check_client=not args.static_only,
        ))
        return
    if args.cmd == "health":
        _print(health_snapshot())
        return

    svc = get_service()
    if args.cmd == "attach":
        result = refresh_workspace_attachment(args.workspace)
    elif args.cmd == "scan":
        scanner = BigBangScanner(svc)
        records = scanner.scan(args.roots)
        result = {"records": serialize_discovery(records)}
        if not args.no_git:
            result["git"] = serialize_git_discovery(scanner.scan_git(args.roots))
    elif args.cmd == "resolve":
        result = svc.resolve(args.query)
    elif args.cmd == "status":
        result = svc.status(args.family_id)
    elif args.cmd == "project":
        result = svc.project_overview(args.project_ref)
    elif args.cmd == "refresh":
        result = MangoMaintainer(svc).refresh_all_family_views()
    elif args.cmd == "diagnose":
        result = MangoMaintainer(svc).diagnose(stale_after_hours=args.stale_hours)
    elif args.cmd == "migrate":
        result = MangoMaintainer(svc).migrate_schema(dry_run=not args.apply)
    elif args.cmd == "approvals":
        result = svc.list_approvals(status=args.status, subject_id=args.subject)
    elif args.cmd in {"approve", "reject"}:
        token = os.environ.get("MANGOME_APPROVAL_TOKEN")
        fn = svc.approve_override if args.cmd == "approve" else svc.reject_override
        result = fn(approval_id=args.approval_id, decided_by=args.actor, approval_token=token, decision_ref=args.decision_ref)
    elif args.cmd == "attest-evidence":
        env_name = "MANGOME_APPROVAL_TOKEN" if args.authority == "OWNER" else "MANGOME_VERIFIER_TOKEN"
        token = os.environ.get(env_name)
        result = svc.attest_evidence(evidence_id=args.evidence_id, attested_by=args.actor, capability_token=token, authority=args.authority)
    elif args.cmd == "verify":
        token = os.environ.get("MANGOME_VERIFIER_TOKEN")
        result = svc.verify_slice(slice_id=args.slice_id, verifier_actor_id=args.actor, verifier_token=token)
    elif args.cmd == "uai-context":
        result = UAICompiler(svc).compile(args.family_id, args.slice_id)
    elif args.cmd == "uai-expand":
        result = UAICompiler.decode_context(args.wire)
    elif args.cmd == "uai-render":
        result = {"rendered": render_uai_result(args.result_json, language=args.language, expected_context_hash=args.context_hash)}
    else:  # pragma: no cover
        raise SystemExit(2)
    _print(result)


if __name__ == "__main__":
    main()
