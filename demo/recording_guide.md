# V.I.S.O.R. Demo Recording Guide

> Step-by-step instructions for creating a terminal demo GIF/video.

---

## Tools Needed

- [**asciinema**](https://asciinema.org/) — terminal recorder
- [**agg**](https://github.com/asciinema/agg) — convert to GIF
- Or **VHS** from Charm: `go install github.com/charmbracelet/vhs@latest`

---

## Option A: asciinema + agg (Recommended)

### 1. Install

```bash
pip install asciinema
# For GIF conversion:
cargo install agg  # or download binary from GitHub
```

### 2. Record

```bash
asciinema rec demo.cast -c "bash demo/record_session.sh"
```

### 3. Convert to GIF

```bash
agg demo.cast demo.gif --font-size 16 --cols 100 --rows 30
```

---

## Option B: VHS Tape (Auto-animated)

Create `demo/demo.tape`:

```tape
Output demo.gif
Set FontSize 16
Set Width 1200
Set Height 600
Set Theme "Catppuccin Mocha"

Type "uv run visor fix 'login crash on null user'"
Enter
Sleep 3s

Type "uv run visor explain 'database client'"
Enter
Sleep 3s

Type "uv run visor trace src/auth/jwt.py src/db/client.py"
Enter
Sleep 2s
```

Run: `vhs demo/demo.tape`

---

## Recording Script

Save as `demo/record_session.sh`:

```bash
#!/bin/bash
echo ""
echo "  🔍 Finding context for a bug..."
echo ""
sleep 1

uv run visor fix "login crash on null user"
sleep 2

echo ""
echo "  🧠 Explaining a module..."
echo ""
sleep 1

uv run visor explain "database client"
sleep 2

echo ""
echo "  🗺️  Tracing request path..."
echo ""
sleep 1

uv run visor trace src/api/routes.py src/db/client.py
sleep 2

echo ""
echo "  ✅ Done. V.I.S.O.R. — precise context, every time."
echo ""
```

---

## Key Frames to Capture

1. **The hook** — `visor fix "login crash"` typed and executed
2. **Token reduction** — the metrics line showing 80% reduction
3. **Reasoning** — the "→ Matched query token..." explanations
4. **Speed** — instant single-call response vs multi-grep
5. **Skill badge** — "Intent: BUG_FIX | Skill: bug-fixer"

---

## Formatting Tips

- Use a dark terminal theme (Catppuccin Mocha, Dracula, or Tokyo Night)
- Set terminal width to 100+ columns
- Use a monospace font at 16px+
- Record at 1200×600 minimum for clarity on GitHub
