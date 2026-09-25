# MangoMe dotfile upload note

The canonical repository tree for v0.1.9rc3 must contain:

```text
.github/workflows/ci.yml
.github/skills/mangome/SKILL.md
.claude/skills/mangome/SKILL.md
.gitignore
```

The public `main` tree inspected before rc3 did **not** contain those dotfile surfaces even though rc2 documentation referenced them. rc3 therefore carries them again explicitly in the complete repository upload.

The canonical Skill and all mirrors must remain byte-identical:

```text
skill/mangome/SKILL.md
src/mangome/skill/SKILL.md
.github/skills/mangome/SKILL.md
.claude/skills/mangome/SKILL.md
```

`make check`, pytest surface regression coverage, and GitHub Actions fail when a required Skill surface is missing or drifts.

For manual upload, do not rely on a file picker that hides dot-prefixed directories. The provided rc3 ZIP is a complete repository tree (without `.git`, caches, or build artifacts), not merely a patch. Extract it into the target Git working tree, verify `.github`, `.claude`, and `.gitignore` exist, then commit/push the resulting tree. After push, verify `.github/workflows/ci.yml` exists on `main` and that GitHub Actions starts.
