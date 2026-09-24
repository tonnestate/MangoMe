# MangoMe dotfile upload note

The earlier browser-upload gap is resolved by the v0.1.7.1 hardening delta.

The canonical repository tree should contain these paths:

```text
.github/workflows/ci.yml
.github/skills/mangome/SKILL.md
.gitignore
```

`skill/mangome/SKILL.md` and `.github/skills/mangome/SKILL.md` must remain byte-identical; CI and `make check` enforce that invariant.

If a browser or file manager hides dot-prefixed paths during a manual upload, create the missing path explicitly in GitHub rather than renaming `.github` or `.gitignore`.
