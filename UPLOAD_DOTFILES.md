# MangoMe dotfile upload note

The canonical repository tree must contain:

```text
.github/workflows/ci.yml
.github/skills/mangome/SKILL.md
.gitignore
```

v0.1.8.1 makes these paths mandatory in `make check`; a package/repository check now fails if they are absent. The canonical Skill, packaged Skill, and GitHub mirror must remain byte-identical.

If a browser/file manager hides dot-prefixed paths during a manual ZIP upload, verify those three paths explicitly after upload. They are part of the release, not optional documentation.
