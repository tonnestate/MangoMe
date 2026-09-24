# Uploading MangoMe dotfiles through GitHub Web

The current repository tree is missing `.github/...` and `.gitignore` because the previous browser upload did not include dot-prefixed paths.

Use GitHub's **Add file → Create new file** flow and type the complete path into the filename field.

Create these exact files:

```text
.github/workflows/ci.yml
.github/skills/mangome/SKILL.md
.gitignore
```

Copy the content from this review pack into those paths.

Afterward verify that the repository tree visibly contains `.github` and that the Actions tab starts the `CI` workflow.

Do not rename `.github` to `github`; GitHub only recognizes the dot-prefixed directory for workflows and repository metadata.
