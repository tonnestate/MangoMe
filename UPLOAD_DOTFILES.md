# MangoMe dotfile upload note

The canonical repository tree must contain:

```text
.github/workflows/ci.yml
.github/skills/mangome/SKILL.md
.gitignore
```

v0.1.9rc1 requires these paths in the published repository in `make check`; a package/repository check now fails if they are absent. The canonical Skill, packaged Skill, and GitHub mirror must remain byte-identical.

If a browser/file manager hides dot-prefixed paths during a manual ZIP upload, verify those three paths explicitly after upload. They are part of the release, not optional documentation.

For v0.1.9rc1, extract the delta into a Git working tree and commit with Git so dot-prefixed paths are preserved. After push, verify all three paths exist on `main` and confirm the GitHub Actions workflow actually starts.
