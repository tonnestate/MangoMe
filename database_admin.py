from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .storage.mongo import MongoStore
from .zero_touch import (
    ZeroTouchBootstrapError,
    _assert_local_provision_safety,
    _free_loopback_port,
    _mongod_config_path,
    _mongod_service_name,
    _parse_simple_mongod_config,
    _probe_uri,
    _secure_managed_credential_file,
    _secure_managed_database_binding,
)


DATABASE_RESET_CONFIRMATION = "TOTAL-RESET-MANGOME-DATABASES"
CANONICAL_DATABASE = "mangome"
RUNTIME_USER = "mangome_runtime"


class DatabaseResetError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def database_reset_warning() -> dict[str, Any]:
    return {
        "ok": False,
        "warning": "DESTRUCTIVE_DATABASE_RESET",
        "message": (
            "This permanently deletes all MangoMe-owned MongoDB databases and all "
            "users defined in those databases. Non-MangoMe databases are not touched."
        ),
        "database_scope": {
            "deleted": ["mangome", "mangome_*"],
            "preserved": ["admin", "config", "local", "all non-MangoMe databases"],
        },
        "recreated": {
            "database": CANONICAL_DATABASE,
            "runtime_user": RUNTIME_USER,
            "roles": [{"role": "readWrite", "db": CANONICAL_DATABASE}],
            "credential_file": "~/.config/mangome/mongodb-uri",
            "database_binding": "~/.config/mangome/database-binding.json",
        },
        "not_affected": [
            "Git repository",
            "MangoMe source code",
            "Python/venv/package installation",
            "Skills",
            "workspaces and project files",
            "Git history",
            "non-MangoMe MongoDB databases",
        ],
        "confirmation_required": DATABASE_RESET_CONFIRMATION,
        "example": (
            "mangome database-reset --confirm "
            + DATABASE_RESET_CONFIRMATION
        ),
    }


def _is_mangome_database(name: str) -> bool:
    return name == CANONICAL_DATABASE or name.startswith("mangome_")


def _normal_port(config: dict[str, str]) -> int:
    raw = str(config.get("net.port") or "27017").strip()
    try:
        port = int(raw)
    except ValueError as exc:
        raise DatabaseResetError("DATABASE_RESET_CONFIG_INVALID", "MongoDB net.port is invalid") from exc
    if not 1 <= port <= 65535:
        raise DatabaseResetError("DATABASE_RESET_CONFIG_INVALID", "MongoDB net.port is outside the valid range")
    return port


def _service_user(systemctl: str, service: str) -> str:
    result = subprocess.run(
        [systemctl, "show", service, "--property=User", "--value"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )
    value = result.stdout.strip() if result.returncode == 0 else ""
    return value or "mongodb"


def _wait_for_temp_store(uri: str, process: subprocess.Popen[Any], timeout: float = 20.0) -> MongoStore:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise DatabaseResetError(
                "DATABASE_RESET_TEMP_MONGOD_FAILED",
                "temporary MongoDB reset process exited before becoming ready",
            )
        store: MongoStore | None = None
        try:
            store = MongoStore(uri, "admin")
            store.client.admin.command("ping")
            return store
        except Exception as exc:
            last_error = exc
            if store is not None:
                try:
                    store.client.close()
                except Exception:
                    pass
            time.sleep(0.25)
    raise DatabaseResetError(
        "DATABASE_RESET_TEMP_MONGOD_TIMEOUT",
        f"temporary MongoDB reset process did not become ready ({type(last_error).__name__ if last_error else 'timeout'})",
    )


def _stop_temp_process(process: subprocess.Popen[Any] | None, store: MongoStore | None) -> None:
    if store is not None:
        try:
            store.client.admin.command({"shutdown": 1, "force": True})
        except Exception:
            pass
        try:
            store.client.close()
        except Exception:
            pass
    if process is None or process.poll() is not None:
        return
    try:
        process.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        pass
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _verify_fresh_runtime(uri: str, timeout: float = 20.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            probe = _probe_uri(uri, CANONICAL_DATABASE)
            store = MongoStore(uri, CANONICAL_DATABASE)
            try:
                status = store.db.command("connectionStatus")
                roles = [
                    {"role": str(row.get("role")), "db": str(row.get("db"))}
                    for row in ((status.get("authInfo") or {}).get("authenticatedUserRoles") or [])
                    if isinstance(row, dict)
                ]
            finally:
                store.client.close()
            expected = {"role": "readWrite", "db": CANONICAL_DATABASE}
            if expected not in roles:
                raise DatabaseResetError(
                    "DATABASE_RESET_ROLE_VERIFY_FAILED",
                    "fresh MangoMe runtime user does not have readWrite on mangome",
                )
            return {
                "database_ready": bool(probe.get("database_ready")),
                "canonical_indexes_ready": bool(probe.get("canonical_indexes_ready")),
                "runtime_role_verified": True,
                "runtime_roles": roles,
            }
        except DatabaseResetError:
            raise
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise DatabaseResetError(
        "DATABASE_RESET_VERIFY_FAILED",
        f"fresh MangoMe runtime could not be verified ({type(last_error).__name__ if last_error else 'timeout'})",
    )


def total_reset_database(
    *,
    confirmation: str,
    home: str | None = None,
) -> dict[str, Any]:
    if confirmation != DATABASE_RESET_CONFIRMATION:
        raise DatabaseResetError(
            "DATABASE_RESET_CONFIRMATION_REQUIRED",
            f"exact confirmation required: {DATABASE_RESET_CONFIRMATION}",
        )
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise DatabaseResetError(
            "DATABASE_RESET_ROOT_REQUIRED",
            "database total reset requires local root authority",
        )

    home_path = Path(home).expanduser().resolve() if home else Path.home().resolve()

    try:
        service = _mongod_service_name()
        config_path = _mongod_config_path()
        config = _parse_simple_mongod_config(config_path)
        _assert_local_provision_safety(config)
    except ZeroTouchBootstrapError as exc:
        raise DatabaseResetError(exc.code, str(exc)) from exc

    systemctl = shutil.which("systemctl")
    mongod = shutil.which("mongod") or ("/usr/bin/mongod" if Path("/usr/bin/mongod").is_file() else None)
    runuser = shutil.which("runuser")
    if not systemctl or not mongod or not runuser:
        raise DatabaseResetError(
            "DATABASE_RESET_UNSUPPORTED",
            "required local MongoDB service-management tools are unavailable",
        )

    active = subprocess.run(
        [systemctl, "is-active", "--quiet", service],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    ).returncode == 0
    if not active:
        raise DatabaseResetError(
            "DATABASE_RESET_SERVICE_NOT_ACTIVE",
            "MongoDB systemd service must be active before total reset",
        )

    port = _normal_port(config)
    service_user = _service_user(systemctl, service)
    temp_port = _free_loopback_port()
    temp_uri = f"mongodb://127.0.0.1:{temp_port}"
    temp_process: subprocess.Popen[Any] | None = None
    temp_store: MongoStore | None = None

    password = secrets.token_urlsafe(36)
    encoded_user = quote(RUNTIME_USER, safe="")
    encoded_password = quote(password, safe="")
    encoded_db = quote(CANONICAL_DATABASE, safe="")
    runtime_uri = (
        f"mongodb://{encoded_user}:{encoded_password}@127.0.0.1:{port}/"
        f"{encoded_db}?authSource={encoded_db}"
    )

    dropped_databases: list[str] = []
    service_restart_error: Exception | None = None

    subprocess.run(
        [systemctl, "stop", service],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )

    try:
        env = dict(os.environ)
        env.pop("MONGODB_CONFIG_OVERRIDE_NOFORK", None)
        temp_process = subprocess.Popen(
            [
                runuser, "-u", service_user, "--",
                mongod, "--config", str(config_path),
                "--noauth",
                "--bind_ip", "127.0.0.1",
                "--port", str(temp_port),
                "--nounixsocket",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        temp_store = _wait_for_temp_store(temp_uri, temp_process)

        discovered = set(temp_store.client.list_database_names())
        targets = sorted(
            {name for name in discovered if _is_mangome_database(name)}
            | {CANONICAL_DATABASE, "mangome_uai_eval"}
        )

        for name in targets:
            db = temp_store.client[name]
            # dropDatabase intentionally does not delete DB users; remove those
            # first so no legacy/eval MangoMe principal survives the total reset.
            db.command({"dropAllUsersFromDatabase": 1})
            db.command({"dropDatabase": 1})
            if name in discovered:
                dropped_databases.append(name)

        fresh = temp_store.client[CANONICAL_DATABASE]
        fresh.command({
            "createUser": RUNTIME_USER,
            "pwd": password,
            "roles": [{"role": "readWrite", "db": CANONICAL_DATABASE}],
        })

        # Persist only the scoped runtime credential; never an admin/no-auth secret.
        credential_path = _secure_managed_credential_file(home_path, runtime_uri)
        _secure_managed_database_binding(
            home_path,
            database=CANONICAL_DATABASE,
            source="DATABASE_TOTAL_RESET",
            adopted_existing=False,
        )

        _stop_temp_process(temp_process, temp_store)
        temp_process = None
        temp_store = None
    finally:
        _stop_temp_process(temp_process, temp_store)
        try:
            subprocess.run(
                [systemctl, "start", service],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
        except Exception as exc:
            service_restart_error = exc

    if service_restart_error is not None:
        raise DatabaseResetError(
            "DATABASE_RESET_SERVICE_RESTART_FAILED",
            "database reset completed but the normal authenticated MongoDB service could not be restarted",
        ) from service_restart_error

    verification = _verify_fresh_runtime(runtime_uri)

    os.environ["MANGOME_MONGODB_URI_FILE"] = str(credential_path)
    os.environ.pop("MANGOME_MONGODB_URI", None)
    os.environ["MANGOME_DATABASE"] = CANONICAL_DATABASE
    os.environ["MANGOME_EXPECTED_DATABASE"] = CANONICAL_DATABASE
    os.environ.pop("MANGOME_ALLOW_EVAL_DATABASE", None)
    os.environ.pop("MANGOME_ADOPT_EXISTING_DATABASE", None)

    return {
        "ok": True,
        "operation": "DATABASE_TOTAL_RESET",
        "destructive": True,
        "scope": "MANGOME_DATABASES_ONLY",
        "dropped_databases": dropped_databases,
        "database": CANONICAL_DATABASE,
        "legacy_eval_database_removed": "mangome_uai_eval" in dropped_databases,
        "runtime_user": RUNTIME_USER,
        "runtime_role": {"role": "readWrite", "db": CANONICAL_DATABASE},
        "credential_file": str(credential_path),
        "database_binding": str(home_path / ".config" / "mangome" / "database-binding.json"),
        "database_migration_performed": False,
        "non_mangome_databases_touched": False,
        "mongodb_service_restarted": True,
        "mcp_restart_required": True,
        **verification,
    }
