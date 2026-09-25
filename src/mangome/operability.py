from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]
from pathlib import Path
from typing import Any, Iterable

from . import __version__
from .filesystem import FilesystemScanner
from .importer import BigBangReconciler, BigBangScanner, serialize_git_discovery
from .service import MangoMeService



_MANGOME_INSTRUCTION_BEGIN = "<!-- BEGIN MANGOME ZERO-TOUCH -->"
_MANGOME_INSTRUCTION_END = "<!-- END MANGOME ZERO-TOUCH -->"
_MANGOME_ALWAYS_ON_INSTRUCTION = """<!-- BEGIN MANGOME ZERO-TOUCH -->
MangoMe is governed project infrastructure for this workspace. Zero-touch applies to the user interface, not to governance. For substantive project work, call `workspace_status` first. Automatic filesystem/Big-Bang discovery is CANDIDATE_ONLY and must never be treated as canonical history. If no admitted MangoMe family/specification fits the current task, call `enter_work` with the user's actual request before productive mutation; it creates current-user-intent-backed canonical work plus the mandatory Plan/Slice binding without promoting discovered history. Reuse `begin_work` for already admitted work. If a managed binding/readiness problem is safely deterministic, run `mangome doctor --repair` yourself before asking the user. Never ask the user to operate Big Bang, contracts, slices, plans, or MangoMe vocabulary. `DONE_CLAIMED` is only a claim; verifier/owner authority remains separate and must never be fabricated.
<!-- END MANGOME ZERO-TOUCH -->"""

class OperabilityError(RuntimeError):
    """Fail-closed error for deterministic bootstrap/attestation problems."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _git(root: Path, args: list[str]) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], stderr=subprocess.DEVNULL, text=True, timeout=5
        ).strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _git_root(start: Path) -> Path | None:
    value = _git(start, ["rev-parse", "--show-toplevel"])
    return Path(value).resolve() if value else None


def installation_identity() -> dict[str, Any]:
    package_dir = Path(__file__).resolve().parent
    source_root = _git_root(package_dir)
    return {
        "version": __version__,
        "python": os.path.abspath(sys.executable),
        "package_path": str(package_dir),
        "source_root": str(source_root) if source_root else None,
        "git_commit": _git(source_root, ["rev-parse", "HEAD"]) if source_root else None,
    }


def enforce_expected_identity() -> dict[str, Any]:
    """Fail closed when a managed client launches a different MangoMe than configured."""
    identity = installation_identity()
    expected_version = os.environ.get("MANGOME_EXPECTED_VERSION", "").strip()
    if expected_version and identity["version"] != expected_version:
        raise OperabilityError(
            "WRONG_MANGOME_VERSION",
            f"expected MangoMe {expected_version}, running {identity['version']}",
        )
    expected_root = os.environ.get("MANGOME_EXPECTED_SOURCE_ROOT", "").strip()
    if expected_root:
        actual_root = identity.get("source_root")
        if actual_root is None or Path(actual_root).resolve() != Path(expected_root).expanduser().resolve():
            raise OperabilityError("WRONG_MCP_TARGET", "running MangoMe source root does not match managed client binding")
    return identity


def resolve_workspace_root(value: str | None = None) -> Path:
    explicit = value or os.environ.get("MANGOME_WORKSPACE_ROOT")
    if explicit:
        root = Path(explicit).expanduser().resolve()
    else:
        root = _git_root(Path.cwd()) or Path.cwd().resolve()
    if not root.exists() or not root.is_dir():
        raise OperabilityError("WORKSPACE_NOT_FOUND", f"workspace is not an existing directory: {root}")
    return root


def attach_workspace(
    service: MangoMeService,
    workspace_root: str | None = None,
    *,
    include_git: bool = True,
    max_files: int = 50_000,
) -> dict[str, Any]:
    """Attach a workspace without inventing semantic truth.

    Unknown workspaces receive one Big-Bang discovery pass plus the normal filesystem
    inventory. Known workspaces receive the inventory refresh only. Discovery may
    register observable artifacts but never canonicalizes contract/spec/slice truth.
    """
    root = resolve_workspace_root(workspace_root)
    root_text = str(root)
    known = bool(service.store.find("filesystem_roots", {"root_path": root_text}))

    inventory = FilesystemScanner(service).scan([root_text], max_files=max_files)
    discovery: dict[str, Any] | None = None
    if not known:
        scanner = BigBangScanner(service)
        records = scanner.scan([root_text])
        reconciliation = BigBangReconciler(service).reconcile(records)
        git_records = scanner.scan_git([root_text]) if include_git else []
        discovery = {
            "record_count": len(records),
            "matched_count": len(reconciliation["matched"]),
            "collision_count": len(reconciliation["collisions"]),
            "unresolved_count": len(reconciliation["unresolved"]),
            "git": serialize_git_discovery(git_records),
            "canonical_mutations": reconciliation["canonical_mutations"],
        }

    return {
        "workspace_root": root_text,
        "first_attach": not known,
        "inventory": inventory,
        "discovery": discovery,
        "discovery_truth_level": "CANDIDATE",
        "rule": (
            "Workspace attachment is automatic discovery only. Ambiguous discoveries remain candidates; "
            "canonical operational work begins separately from explicit current user intent or explicit admission."
        ),
    }


def _skill_source() -> Path:
    packaged = Path(__file__).resolve().parent / "skill" / "SKILL.md"
    if packaged.is_file():
        return packaged
    source_root = installation_identity().get("source_root")
    if source_root:
        candidate = Path(source_root) / "skill" / "mangome" / "SKILL.md"
        if candidate.is_file():
            return candidate
    raise OperabilityError("SKILL_NOT_INSTALLED", "canonical MangoMe Skill is not available in this installation")


def _backup_once(path: Path) -> str | None:
    if not path.exists():
        return None
    backup = path.with_name(path.name + ".mangome.bak")
    if not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    return str(backup)


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".mangome.tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def _server_identity(workspace: Path, *, backend: str, database: str) -> dict[str, Any]:
    identity = installation_identity()
    env = {
        "MANGOME_BACKEND": backend,
        "MANGOME_DATABASE": database,
        "MANGOME_RUNTIME_ROLE": "WORKER",
        "MANGOME_WORKSPACE_ROOT": str(workspace),
        "MANGOME_AUTO_ATTACH": "1",
        "MANGOME_EXPECTED_VERSION": identity["version"],
    }
    if identity.get("source_root"):
        env["MANGOME_EXPECTED_SOURCE_ROOT"] = str(identity["source_root"])
    return {
        "command": identity["python"],
        "args": ["-m", "mangome.mcp_server"],
        "cwd": str(workspace),
        "env": env,
    }


def _json_load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OperabilityError("CLIENT_CONFIGURATION_AMBIGUOUS", f"cannot safely parse {path}") from exc
    if not isinstance(value, dict):
        raise OperabilityError("CLIENT_CONFIGURATION_AMBIGUOUS", f"expected object in {path}")
    return value


def _claude_shadow_candidates(home: Path, workspace: Path) -> list[str]:
    path = home / ".claude.json"
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [str(path) + ":UNPARSEABLE"]
    found: list[str] = []

    def walk(value: Any, trail: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                next_trail = f"{trail}.{key}" if trail else str(key)
                if str(key).lower().startswith("mangome") and "mcp" in trail.lower():
                    found.append(f"{path}:{next_trail}")
                walk(child, next_trail)
        elif isinstance(value, list):
            for idx, child in enumerate(value):
                walk(child, f"{trail}[{idx}]")

    walk(raw, "")
    return sorted(set(found))


def _remove_claude_mangome_shadows(home: Path, workspace: Path, *, dry_run: bool) -> list[str]:
    path = home / ".claude.json"
    if not path.exists():
        return []
    data = _json_load(path)
    removed: list[str] = []
    top = data.get("mcpServers")
    if isinstance(top, dict):
        for key in list(top):
            if str(key).lower().startswith("mangome"):
                removed.append(f"mcpServers.{key}")
                del top[key]
    projects = data.get("projects")
    if isinstance(projects, dict):
        for project_key, project_data in projects.items():
            try:
                same_project = Path(str(project_key)).expanduser().resolve() == workspace
            except OSError:
                same_project = False
            if not same_project or not isinstance(project_data, dict):
                continue
            servers = project_data.get("mcpServers")
            if isinstance(servers, dict):
                for key in list(servers):
                    if str(key).lower().startswith("mangome"):
                        removed.append(f"projects.{project_key}.mcpServers.{key}")
                        del servers[key]
    if removed and not dry_run:
        _backup_once(path)
        _atomic_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return removed


def _remove_codex_mangome_shadows(path: Path, *, dry_run: bool) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(text) if text.strip() else {}
    except tomllib.TOMLDecodeError as exc:
        raise OperabilityError("CLIENT_CONFIGURATION_AMBIGUOUS", f"cannot safely parse {path}") from exc
    servers = data.get("mcp_servers") or {}
    if not isinstance(servers, dict):
        return []
    names = [str(name) for name in servers if str(name).lower().startswith("mangome")]
    if not names:
        return []
    updated = text
    for name in names:
        updated = _strip_toml_section_family(updated, f"mcp_servers.{name}")
    if not dry_run:
        _backup_once(path)
        _atomic_text(path, updated)
    return [f"mcp_servers.{name}" for name in names]



def _merge_managed_instruction(path: Path, *, dry_run: bool) -> dict[str, Any]:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    start = existing.find(_MANGOME_INSTRUCTION_BEGIN)
    end = existing.find(_MANGOME_INSTRUCTION_END)
    if (start >= 0) != (end >= 0) or (start >= 0 and end < start):
        raise OperabilityError("CLIENT_CONFIGURATION_AMBIGUOUS", f"malformed MangoMe managed instruction in {path}")
    if start >= 0:
        end += len(_MANGOME_INSTRUCTION_END)
        before = existing[:start].rstrip()
        after = existing[end:].lstrip("\n")
        pieces = [piece for piece in (before, _MANGOME_ALWAYS_ON_INSTRUCTION, after.rstrip()) if piece]
        updated = "\n\n".join(pieces) + "\n"
    else:
        prefix = existing.rstrip()
        updated = (prefix + "\n\n" if prefix else "") + _MANGOME_ALWAYS_ON_INSTRUCTION + "\n"
    changed = updated != existing
    backup = None
    if changed and not dry_run:
        backup = _backup_once(path)
        _atomic_text(path, updated)
    return {"path": str(path), "changed": changed, "backup": backup}


def _managed_instruction_current(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    start = text.find(_MANGOME_INSTRUCTION_BEGIN)
    end = text.find(_MANGOME_INSTRUCTION_END)
    if start < 0 or end < start:
        return False
    end += len(_MANGOME_INSTRUCTION_END)
    return text[start:end].strip() == _MANGOME_ALWAYS_ON_INSTRUCTION.strip()

def _claude_server_config(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "stdio",
        "command": entry["command"],
        "args": entry["args"],
        "env": entry["env"],
    }


def _clean_claude_project_config(config_path: Path, *, dry_run: bool) -> tuple[dict[str, Any], list[str], str | None]:
    data = _json_load(config_path)
    servers = data.get("mcpServers")
    if servers is None:
        servers = {}
        data["mcpServers"] = servers
    if not isinstance(servers, dict):
        raise OperabilityError("CLIENT_CONFIGURATION_AMBIGUOUS", ".mcp.json mcpServers is not an object")
    removed: list[str] = []
    for key in list(servers):
        if str(key).lower().startswith("mangome"):
            removed.append(f"{config_path}:mcpServers.{key}")
            del servers[key]
    backup = None
    if removed and not dry_run:
        backup = _backup_once(config_path)
        _atomic_text(config_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return data, removed, backup


def _write_claude_local_server(
    home: Path, workspace: Path, server: dict[str, Any], *, dry_run: bool
) -> tuple[str, str | None]:
    path = home / ".claude.json"
    data = _json_load(path)
    projects = data.get("projects")
    if projects is None:
        projects = {}
        data["projects"] = projects
    if not isinstance(projects, dict):
        raise OperabilityError("CLIENT_CONFIGURATION_AMBIGUOUS", f"projects is not an object in {path}")
    project = projects.get(str(workspace))
    if project is None:
        project = {}
        projects[str(workspace)] = project
    if not isinstance(project, dict):
        raise OperabilityError("CLIENT_CONFIGURATION_AMBIGUOUS", f"project entry is not an object in {path}")
    servers = project.get("mcpServers")
    if servers is None:
        servers = {}
        project["mcpServers"] = servers
    if not isinstance(servers, dict):
        raise OperabilityError("CLIENT_CONFIGURATION_AMBIGUOUS", f"project mcpServers is not an object in {path}")
    servers["mangome"] = _claude_server_config(server)
    backup = None
    if not dry_run:
        backup = _backup_once(path)
        _atomic_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return str(path), backup


def configure_claude_code(
    workspace_root: str,
    *,
    backend: str = "mongo",
    database: str = "mangome",
    dry_run: bool = False,
    home: str | None = None,
    scope: str = "local",
) -> dict[str, Any]:
    """Configure Claude Code with zero-touch LOCAL scope by default.

    LOCAL scope is private to the current workspace and does not trigger Claude Code's
    project-MCP trust approval. PROJECT scope remains an explicit opt-in for teams that
    intentionally commit `.mcp.json` and accept Claude Code's approval boundary.
    """
    workspace = resolve_workspace_root(workspace_root)
    home_path = Path(home).expanduser().resolve() if home else Path.home().resolve()
    normalized_scope = str(scope or "local").strip().lower()
    if normalized_scope not in {"local", "project"}:
        raise OperabilityError("UNSUPPORTED_SCOPE", "Claude Code scope must be 'local' or 'project'")

    removed_shadows = _remove_claude_mangome_shadows(home_path, workspace, dry_run=dry_run)
    config_path = workspace / ".mcp.json"
    project_data, removed_project, project_backup = _clean_claude_project_config(config_path, dry_run=dry_run)
    removed_shadows.extend(removed_project)

    entry = _server_identity(workspace, backend=backend, database=database)
    backups: list[str] = []
    if project_backup:
        backups.append(project_backup)

    local_config_path: str | None = None
    if normalized_scope == "project":
        servers = project_data.setdefault("mcpServers", {})
        servers["mangome"] = _claude_server_config(entry)
        if not dry_run:
            backup = _backup_once(config_path)
            if backup and backup not in backups:
                backups.append(backup)
            _atomic_text(config_path, json.dumps(project_data, indent=2, ensure_ascii=False) + "\n")
    else:
        local_config_path, backup = _write_claude_local_server(
            home_path, workspace, entry, dry_run=dry_run
        )
        if backup:
            backups.append(backup)

    skill_source = _skill_source()
    skill_target = workspace / ".claude" / "skills" / "mangome" / "SKILL.md"
    instruction_target = workspace / ".claude" / "rules" / "mangome.md"
    if not dry_run:
        backup = _backup_once(skill_target)
        if backup:
            backups.append(backup)
        skill_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_source, skill_target)
    instruction = _merge_managed_instruction(instruction_target, dry_run=dry_run)
    if instruction.get("backup"):
        backups.append(str(instruction["backup"]))

    return {
        "client": "claude-code",
        "scope": normalized_scope,
        "workspace_root": str(workspace),
        "changed": True,
        "dry_run": dry_run,
        "config_path": str(config_path) if normalized_scope == "project" else local_config_path,
        "project_config_path": str(config_path),
        "skill_path": str(skill_target),
        "instruction_path": str(instruction_target),
        "server": entry,
        "backups": list(dict.fromkeys(backups)),
        "removed_shadow_entries": list(dict.fromkeys(removed_shadows)),
        "note": (
            "LOCAL scope is the default zero-touch path. PROJECT scope is opt-in and may require "
            "Claude Code trust approval by design."
        ),
    }


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: Iterable[str]) -> str:
    return "[" + ", ".join(_toml_string(v) for v in values) + "]"


def _strip_toml_section_family(text: str, section: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped in {"# BEGIN MANGOME MANAGED MCP", "# END MANGOME MANAGED MCP"}:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            header = stripped.strip("[]").strip()
            normalized_header = ".".join(part.strip().strip('"').strip("'") for part in header.split("."))
            if normalized_header == section or normalized_header.startswith(section + "."):
                skipping = True
                continue
            skipping = False
        if not skipping:
            output.append(line)
    while output and not output[-1].strip():
        output.pop()
    return "\n".join(output) + ("\n" if output else "")


def _codex_block(workspace: Path, *, backend: str, database: str) -> str:
    entry = _server_identity(workspace, backend=backend, database=database)
    lines = [
        "# BEGIN MANGOME MANAGED MCP",
        "[mcp_servers.mangome]",
        f"command = {_toml_string(entry['command'])}",
        f"args = {_toml_array(entry['args'])}",
        f"cwd = {_toml_string(entry['cwd'])}",
        "enabled = true",
        "startup_timeout_sec = 20",
        "",
        "[mcp_servers.mangome.env]",
    ]
    for key, value in sorted(entry["env"].items()):
        lines.append(f"{key} = {_toml_string(value)}")
    lines.extend(["# END MANGOME MANAGED MCP", ""])
    return "\n".join(lines)


def configure_codex(
    workspace_root: str,
    *,
    backend: str = "mongo",
    database: str = "mangome",
    dry_run: bool = False,
    home: str | None = None,
) -> dict[str, Any]:
    workspace = resolve_workspace_root(workspace_root)
    home_path = Path(home).expanduser().resolve() if home else Path.home().resolve()
    user_config = home_path / ".codex" / "config.toml"
    removed_shadows = []
    # Project config is the managed source for this workspace. Remove only MangoMe-named
    # user-level MCP entries so stale launchers cannot remain active in parallel.
    if user_config.resolve() != (workspace / ".codex" / "config.toml").resolve():
        removed_shadows = _remove_codex_mangome_shadows(user_config, dry_run=dry_run)
    config_path = workspace / ".codex" / "config.toml"
    instruction_target = workspace / "AGENTS.md"
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    project_data: dict[str, Any] = {}
    try:
        if existing.strip():
            project_data = tomllib.loads(existing)
    except tomllib.TOMLDecodeError as exc:
        raise OperabilityError("CLIENT_CONFIGURATION_AMBIGUOUS", f"cannot safely parse {config_path}") from exc
    project_servers = project_data.get("mcp_servers") or {}
    project_names = [
        str(name) for name in project_servers
        if isinstance(project_servers, dict) and str(name).lower().startswith("mangome")
    ]
    base = existing
    for name in project_names:
        if name != "mangome":
            removed_shadows.append(f"{config_path}:mcp_servers.{name}")
        base = _strip_toml_section_family(base, f"mcp_servers.{name}")
    if "mangome" not in project_names:
        base = _strip_toml_section_family(base, "mcp_servers.mangome")
    updated = base + ("\n" if base and not base.endswith("\n\n") else "") + _codex_block(
        workspace, backend=backend, database=database
    )
    backups: list[str] = []
    if not dry_run:
        backup = _backup_once(config_path)
        if backup:
            backups.append(backup)
        _atomic_text(config_path, updated)
    instruction = _merge_managed_instruction(instruction_target, dry_run=dry_run)
    if instruction.get("backup"):
        backups.append(str(instruction["backup"]))
    return {
        "client": "codex",
        "workspace_root": str(workspace),
        "changed": True,
        "dry_run": dry_run,
        "config_path": str(config_path),
        "instruction_path": str(instruction_target),
        "server": _server_identity(workspace, backend=backend, database=database),
        "backups": backups,
        "removed_shadow_entries": removed_shadows,
    }


def _compare_server_entry(actual: dict[str, Any] | None, expected: dict[str, Any]) -> list[str]:
    if not isinstance(actual, dict):
        return ["MCP_NOT_REGISTERED"]
    reasons: list[str] = []
    if str(actual.get("command") or "") != expected["command"]:
        reasons.append("WRONG_MCP_TARGET")
    if list(actual.get("args") or []) != expected["args"]:
        reasons.append("WRONG_MCP_TARGET")
    cwd = actual.get("cwd")
    if cwd is not None and str(Path(str(cwd)).expanduser().resolve()) != expected["cwd"]:
        reasons.append("WRONG_MCP_TARGET")
    env = actual.get("env") or {}
    if not isinstance(env, dict):
        reasons.append("CLIENT_CONFIGURATION_AMBIGUOUS")
    else:
        for key, value in expected["env"].items():
            if str(env.get(key) or "") != value:
                reasons.append("WRONG_MANGOME_VERSION" if key == "MANGOME_EXPECTED_VERSION" else "WRONG_MCP_TARGET")
    return list(dict.fromkeys(reasons))


def _client_list_attestation(executable: str, workspace: Path, *, client: str) -> dict[str, Any]:
    binary = shutil.which(executable)
    if binary is None:
        return {
            "available": False, "checked": False, "server_visible": None,
            "connection_state": "CLIENT_NOT_INSTALLED", "returncode": None,
        }
    try:
        proc = subprocess.run(
            [binary, "mcp", "list"], cwd=str(workspace), capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return {
            "available": True, "checked": True, "server_visible": False,
            "connection_state": "CHECK_FAILED", "returncode": None,
        }
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    lines = [line.strip() for line in combined.splitlines() if "mangome" in line.lower()]
    visible = bool(lines)
    lower = "\n".join(lines).lower()
    if not visible:
        state = "NOT_REGISTERED"
    elif "pending approval" in lower or "pending" in lower and "approval" in lower:
        state = "PENDING_APPROVAL"
    elif any(token in lower for token in ("connected", "✓", "ready")):
        state = "CONNECTED"
    elif any(token in lower for token in ("disconnected", "failed", "error", "unreachable")):
        state = "DISCONNECTED"
    else:
        # A name appearing in `mcp list` is not proof of an effective connection.
        state = "VISIBLE_UNCONFIRMED"
    return {
        "available": True,
        "checked": True,
        "server_visible": visible,
        "connection_state": state,
        "returncode": proc.returncode,
        "matched_lines": lines[:5],
        "client": client,
    }


def _claude_static_entry(home: Path, workspace: Path, *, scope: str) -> tuple[dict[str, Any] | None, Path]:
    if scope == "project":
        path = workspace / ".mcp.json"
        data = _json_load(path)
        servers = data.get("mcpServers") or {}
        return (servers.get("mangome") if isinstance(servers, dict) else None), path
    path = home / ".claude.json"
    data = _json_load(path)
    projects = data.get("projects") or {}
    project = projects.get(str(workspace)) if isinstance(projects, dict) else None
    servers = project.get("mcpServers") if isinstance(project, dict) else None
    return (servers.get("mangome") if isinstance(servers, dict) else None), path


def attest_client(
    client: str,
    workspace_root: str,
    *,
    backend: str = "mongo",
    database: str = "mangome",
    home: str | None = None,
    check_client: bool = True,
    claude_scope: str = "local",
) -> dict[str, Any]:
    workspace = resolve_workspace_root(workspace_root)
    expected = _server_identity(workspace, backend=backend, database=database)
    home_path = Path(home).expanduser().resolve() if home else Path.home().resolve()
    reasons: list[str] = []
    shadows: list[str] = []

    normalized = client.lower().replace("_", "-")
    if normalized in {"claude", "claude-code"}:
        normalized = "claude-code"
        scope = str(claude_scope or "local").strip().lower()
        if scope not in {"local", "project"}:
            raise OperabilityError("UNSUPPORTED_SCOPE", "Claude Code scope must be 'local' or 'project'")
        actual, path = _claude_static_entry(home_path, workspace, scope=scope)
        reasons.extend(_compare_server_entry(actual, expected))

        # The non-selected scope may contain an old MangoMe entry. Report it as shadowing
        # rather than pretending static configuration is unambiguous.
        if scope == "local":
            project_path = workspace / ".mcp.json"
            project_data = _json_load(project_path)
            project_servers = project_data.get("mcpServers") or {}
            if isinstance(project_servers, dict):
                for key in project_servers:
                    if str(key).lower().startswith("mangome"):
                        shadows.append(f"{project_path}:mcpServers.{key}")
        else:
            local_actual, local_path = _claude_static_entry(home_path, workspace, scope="local")
            if isinstance(local_actual, dict):
                shadows.append(f"{local_path}:projects.{workspace}.mcpServers.mangome")

        skill = workspace / ".claude" / "skills" / "mangome" / "SKILL.md"
        if not skill.is_file():
            reasons.append("SKILL_NOT_INSTALLED")
        elif skill.read_bytes() != _skill_source().read_bytes():
            reasons.append("SKILL_VERSION_MISMATCH")
        instruction = workspace / ".claude" / "rules" / "mangome.md"
        if not _managed_instruction_current(instruction):
            reasons.append("AUTOMATIC_INSTRUCTIONS_MISSING")
        cli = _client_list_attestation("claude", workspace, client=normalized) if check_client else {"checked": False}
        if check_client and cli.get("available"):
            state = cli.get("connection_state")
            if state != "CONNECTED":
                reasons.append("CONFIGURATION_NOT_EFFECTIVE")
                if state == "PENDING_APPROVAL":
                    reasons.append("PROJECT_MCP_APPROVAL_REQUIRED")
    elif normalized == "codex":
        path = workspace / ".codex" / "config.toml"
        actual = None
        if path.exists():
            try:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError:
                reasons.append("CLIENT_CONFIGURATION_AMBIGUOUS")
                data = {}
            project_servers = data.get("mcp_servers") or {}
            actual = project_servers.get("mangome") if isinstance(project_servers, dict) else None
            if isinstance(project_servers, dict):
                for key in project_servers:
                    if str(key).lower().startswith("mangome") and key != "mangome":
                        shadows.append(f"{path}:mcp_servers.{key}")
        reasons.extend(_compare_server_entry(actual, expected))
        user_config = home_path / ".codex" / "config.toml"
        if user_config.exists() and user_config.resolve() != path.resolve():
            try:
                user_data = tomllib.loads(user_config.read_text(encoding="utf-8"))
                servers = user_data.get("mcp_servers") or {}
                if isinstance(servers, dict):
                    for key, value in servers.items():
                        if str(key).lower().startswith("mangome") and key != "mangome":
                            shadows.append(f"{user_config}:mcp_servers.{key}")
                        elif key == "mangome" and isinstance(value, dict) and _compare_server_entry(value, expected):
                            shadows.append(f"{user_config}:mcp_servers.mangome")
            except tomllib.TOMLDecodeError:
                shadows.append(str(user_config) + ":UNPARSEABLE")
        instruction = workspace / "AGENTS.md"
        if not _managed_instruction_current(instruction):
            reasons.append("AUTOMATIC_INSTRUCTIONS_MISSING")
        cli = _client_list_attestation("codex", workspace, client=normalized) if check_client else {"checked": False}
        if check_client and cli.get("available") and (cli.get("returncode") != 0 or not cli.get("server_visible")):
            reasons.append("MCP_NOT_VISIBLE")
    else:
        raise OperabilityError("UNSUPPORTED_CLIENT", f"unsupported client: {client}")

    if shadows:
        reasons.append("CONFIGURATION_SHADOWING")
    reasons = list(dict.fromkeys(reasons))
    if reasons:
        status = "CLIENT_READINESS_FAILED"
    elif check_client and cli.get("available"):
        status = "PASS"
    else:
        status = "STATIC_PASS"
    return {
        "client": normalized,
        "status": status,
        "reasons": reasons,
        "workspace_root": str(workspace),
        "expected_server": expected,
        "shadow_candidates": shadows,
        "client_check": cli,
        "claude_scope": (str(claude_scope or "local").lower() if normalized == "claude-code" else None),
    }


def setup_clients(
    workspace_root: str,
    *,
    clients: Iterable[str] | None = None,
    backend: str = "mongo",
    database: str = "mangome",
    dry_run: bool = False,
    home: str | None = None,
    claude_scope: str = "local",
) -> dict[str, Any]:
    workspace = resolve_workspace_root(workspace_root)
    requested = list(clients or [])
    if not requested or requested == ["auto"]:
        requested = []
        if shutil.which("claude"):
            requested.append("claude-code")
        if shutil.which("codex"):
            requested.append("codex")
    expanded: list[str] = []
    for value in requested:
        normalized = value.lower().replace("_", "-")
        if normalized == "all":
            expanded.extend(["claude-code", "codex"])
        else:
            expanded.append(normalized)
    expanded = list(dict.fromkeys(expanded))
    results: list[dict[str, Any]] = []
    for client in expanded:
        if client in {"claude", "claude-code"}:
            change = configure_claude_code(
                str(workspace), backend=backend, database=database, dry_run=dry_run, home=home,
                scope=claude_scope,
            )
            normalized = "claude-code"
        elif client == "codex":
            change = configure_codex(
                str(workspace), backend=backend, database=database, dry_run=dry_run, home=home
            )
            normalized = "codex"
        else:
            results.append({"client": client, "status": "UNSUPPORTED_CLIENT"})
            continue
        attestation = None if dry_run else attest_client(
            normalized, str(workspace), backend=backend, database=database, home=home, check_client=True,
            claude_scope=claude_scope,
        )
        results.append({"client": normalized, "change": change, "attestation": attestation})
    return {
        "workspace_root": str(workspace),
        "installation": installation_identity(),
        "clients": results,
        "dry_run": dry_run,
        "rule": "Safe managed configuration drift is repaired without requiring the user to know MangoMe internals.",
    }


def doctor(
    workspace_root: str | None = None,
    *,
    clients: Iterable[str] = ("claude-code", "codex"),
    backend: str = "mongo",
    database: str = "mangome",
    repair: bool = False,
    home: str | None = None,
    claude_scope: str = "local",
) -> dict[str, Any]:
    workspace = resolve_workspace_root(workspace_root)
    before = [
        attest_client(
            client, str(workspace), backend=backend, database=database, home=home, check_client=True,
            claude_scope=claude_scope,
        )
        for client in clients
    ]
    repair_result = None
    if repair:
        failing = [row["client"] for row in before if row["status"] == "CLIENT_READINESS_FAILED"]
        if failing:
            repair_result = setup_clients(
                str(workspace), clients=failing, backend=backend, database=database, dry_run=False, home=home,
                claude_scope=claude_scope,
            )
    after = [
        attest_client(
            client, str(workspace), backend=backend, database=database, home=home, check_client=True,
            claude_scope=claude_scope,
        )
        for client in clients
    ] if repair else before
    return {
        "installation": installation_identity(),
        "workspace_root": str(workspace),
        "before": before,
        "repair": repair_result,
        "after": after,
    }
