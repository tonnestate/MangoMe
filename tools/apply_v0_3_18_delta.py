#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

EXPECTED_BASE = "1924e87d22b99acae1108391a0a8898d831531a5"
TARGET_VERSION = "0.3.18"

OLD_BLOCK = """    # First admission may trust the current client-relayed user intent. Once canonical
    # workspace state already exists, minting additional durable work authority requires
    # the external control plane instead of letting a recovered worker self-authorize.
    restored = session_restore_snapshot()
    if restored and str(restored.get("restore_state") or "") == "STATE_FOUND":
        blocked = _controller_gate("enter_work(existing workspace)", controller_actor_id, controller_token)
        if blocked:
            return blocked
"""

NEW_BLOCK = """    # v0.3.18 bounded current-user intent admission:
    # An explicit current user request may admit ordinary EXECUTE work even when the
    # workspace already contains canonical MangoMe state. The domain service creates
    # or reuses only the task-specific WorkIdentity and binds an EXECUTE WorkTurn with
    # authority provenance USER_INTENT_RELAYED_BY_CLIENT. This does not grant VERIFY,
    # MODIFY, CONTROL, OWNER/ACCEPT or ROUTER authority; those capability boundaries
    # remain unchanged. Recovered state is still context, never authority for a new
    # privileged transition.
"""

README_MARKER = "# v0.3.17 — KeyFile-Safe Zero-Touch LOCAL_HOST"

README_SECTION = """# v0.3.18 — Bounded User-Intent Execution Authority

v0.3.18 removes an over-strict control-plane dependency discovered by the EV-U01 utility pilot.

The v0.3.17 MCP wrapper required a separate CONTROL capability before `enter_work` could admit a new task inside a workspace that already contained MangoMe state. That was stricter than the underlying governed service and made ordinary current-user work impossible without an external controller, even though the service already creates only a task-specific WorkIdentity and an `EXECUTE` WorkTurn.

v0.3.18 aligns the MCP boundary with that existing domain rule:

```text
explicit current user request
        ↓
same managed workspace
        ↓
ENTER_WORK
        ↓
task-specific WorkIdentity
        ↓
EXECUTE WorkTurn
authorized_by = USER_INTENT_RELAYED_BY_CLIENT
```

This bounded authority is intentionally narrow. It does **not** authorize `VERIFY`, `MODIFY`, `CONTROL`, `OWNER/ACCEPT` or `ROUTER` operations. Existing verification, normative-mutation, acceptance and routing capability boundaries remain unchanged.

The result is a simpler ordinary-work path without weakening the assurance boundary:

```text
current user intent → EXECUTE
worker claim        → still UNVERIFIED
independent proof   → still requires VERIFIER authority
acceptance          → still requires OWNER authority
```

The change is specifically intended to let EV-U01 and normal agent work measure MangoMe utility rather than external controller availability.

---

"""

CHANGELOG_ENTRY = """## 0.3.18 - 2026-10-01

- Relaxed the ordinary-work admission boundary: explicit current user intent may now create/reuse task-specific WorkIdentity and an EXECUTE WorkTurn inside an already-admitted workspace without requiring a separate host CONTROL runtime.
- Kept privileged boundaries unchanged: VERIFY, MODIFY, CONTROL, OWNER/ACCEPT and ROUTER authority are still capability protected.
- Added regression coverage proving that bounded user-intent admission works in STATE_FOUND while VERIFY turn minting still requires control-plane authority.
- This change was driven by EV-U01 pilot evidence: the previous wrapper was measuring controller availability instead of MangoMe utility.

"""


def fail(msg: str) -> None:
    raise SystemExit(msg)


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing required file: {path}")
    return path.read_text(encoding="utf-8")


def write(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def main() -> None:
    repo = Path.cwd().resolve()
    required = [
        repo / "src/mangome/mcp_server.py",
        repo / "src/mangome/__init__.py",
        repo / "pyproject.toml",
        repo / "README.md",
        repo / "CHANGELOG.md",
    ]
    for path in required:
        if not path.is_file():
            fail(f"run from MangoMe repository root; missing {path.relative_to(repo)}")

    # Fail closed against an unexpected source baseline.
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        head = ""
    if head and head != EXPECTED_BASE:
        fail(f"unexpected Git HEAD {head}; expected exact v0.3.17 base {EXPECTED_BASE}")

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, check=False
    )
    if status.returncode == 0 and status.stdout.strip():
        fail("working tree is not clean; refusing to patch")

    mcp_path = repo / "src/mangome/mcp_server.py"
    mcp = read(mcp_path)
    if OLD_BLOCK not in mcp:
        fail("v0.3.17 controller-gate block not found; refusing non-deterministic patch")
    mcp = mcp.replace(OLD_BLOCK, NEW_BLOCK, 1)
    if 'enter_work(existing workspace)' in mcp:
        fail("stale enter_work controller gate remains after patch")
    write(mcp_path, mcp)

    py = read(repo / "pyproject.toml")
    if 'version = "0.3.17"' not in py:
        fail("pyproject version is not 0.3.17")
    write(repo / "pyproject.toml", py.replace('version = "0.3.17"', 'version = "0.3.18"', 1))

    init_path = repo / "src/mangome/__init__.py"
    init = read(init_path)
    if '__version__ = "0.3.17"' not in init:
        fail("__init__ version is not 0.3.17")
    write(init_path, init.replace('__version__ = "0.3.17"', '__version__ = "0.3.18"', 1))

    readme_path = repo / "README.md"
    readme = read(readme_path)
    readme = readme.replace("version-0.3.17-yellow", "version-0.3.18-yellow", 1)
    if README_MARKER not in readme:
        fail("README v0.3.17 marker not found")
    write(readme_path, readme.replace(README_MARKER, README_SECTION + README_MARKER, 1))

    changelog_path = repo / "CHANGELOG.md"
    changelog = read(changelog_path)
    first_nl = changelog.find("\n")
    if first_nl < 0:
        fail("unexpected CHANGELOG format")
    write(changelog_path, changelog[: first_nl + 1] + "\n" + CHANGELOG_ENTRY + changelog[first_nl + 1 :])

    # Copy release artifacts from delta package.
    here = Path(__file__).resolve().parent.parent
    for rel in [
        Path("tests/test_v0318_bounded_user_intent.py"),
        Path("docs/v0.3.18-release-notes.md"),
    ]:
        src = here / rel
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())

    print("Applied MangoMe v0.3.18 bounded-user-intent delta.")
    print("No VERIFY/MODIFY/CONTROL/OWNER/ROUTER capability rule was changed.")
    print("Run the focused regression test and inspect git diff before committing.")


if __name__ == "__main__":
    main()
