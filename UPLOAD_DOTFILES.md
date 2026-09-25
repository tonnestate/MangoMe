# MangoMe dotfile upload note

The canonical repository tree for v0.1.9rc2 must contain:

```text
.github/workflows/ci.yml
.github/skills/mangome/SKILL.md
.claude/skills/mangome/SKILL.md
.gitignore
```

The canonical Skill and all repository/package mirrors must remain byte-identical:

```text
skill/mangome/SKILL.md
src/mangome/skill/SKILL.md
.github/skills/mangome/SKILL.md
.claude/skills/mangome/SKILL.md
```

`make check` and GitHub Actions fail when any required Skill surface is missing or drifts. The `.claude` path is not merely documentation: it is the native Claude Code discovery surface in the repository, while managed setup continues to copy the packaged Skill into target workspaces.

If a browser/file manager hides dot-prefixed paths during a manual ZIP upload, verify all four dot-prefixed paths explicitly after upload. They are part of the release.

Extract the delta into a Git working tree and commit with Git so dot-prefixed paths are preserved. After push, verify the `.github` and `.claude` trees exist on `main`, run `make check`, and confirm GitHub Actions starts.
