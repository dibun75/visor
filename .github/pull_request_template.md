## What does this PR do?

<!-- Brief description of the change and why it is needed. -->

## Related issue

Fixes #

## Type of Change

- [ ] 🐛 Bug fix
- [ ] ✨ New feature
- [ ] 🌐 New language support
- [ ] 📝 Documentation
- [ ] ♻️ Refactor
- [ ] 🧪 Tests

## Checklist

- [ ] Tests cover the change
- [ ] Public documentation is updated when behavior changes
- [ ] Unrelated changes are left out
- [ ] Python checks pass for Python changes:

```bash
uv sync --dev
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
uv build
```

- [ ] HUD checks pass when `src/visor/hud` changes:

```bash
cd src/visor/hud
npm ci
npm run lint
npm run build
npx playwright test
```

- [ ] Extension checks pass when `src/visor/extension` changes:

```bash
cd src/visor/extension
npm ci
npm run check-types
npm run compile
npx --yes @vscode/vsce package --no-dependencies --out /tmp/visor-hud-audit.vsix
```
