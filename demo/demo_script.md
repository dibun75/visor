# V.I.S.O.R. Demo Script

> Reproduce this demo in under 60 seconds to show clear value.

## Setup

```bash
git clone https://github.com/dibun75/visor.git
cd visor && uv sync
```

---

## Demo 1: Fix a Bug

```bash
uv run visor fix "login crash on null user"
```

**Expected output:**

```
============================================================
  V.I.S.O.R. Context Intelligence Engine
============================================================
  Query:  login crash on null user
  Intent: BUG_FIX
  Skill:  bug-fixer
────────────────────────────────────────────────────────────
  Tokens without V.I.S.O.R.: 11,400
  Tokens with V.I.S.O.R.:    2,180
  Reduction:                  80.9%
────────────────────────────────────────────────────────────
  Selected 4 nodes (truncated=False):

  [2.8500]  src/auth/jwt.py:verify_token
            → Matched query token in symbol name
            → Co-located in same file as top semantic hit
            → Recently modified file (boosted)

  [2.1200]  src/auth/middleware.py:auth_guard
            → Reachable via dependency chain
            → Semantic similarity (score: 0.375)

  [1.4500]  src/models/user.py:User
            → Matched query token in symbol name
            → Semantic similarity (score: 0.42)

  [0.8700]  src/db/session.py:get_session
            → Reachable via dependency chain

============================================================
```

---

## Demo 2: Explain Architecture

```bash
uv run visor explain "database client module"
```

---

## Demo 3: Trace a Request

```bash
uv run visor trace src/api/routes.py src/db/client.py
```

---

## Demo 4: Check for Drift

```bash
uv run visor drift
```

---

## Demo 5: Raw JSON Output

```bash
uv run visor fix "login crash" --json
```

Shows the full structured response with `debug`, `metrics`, `reasoning`, and `prompt_ready` fields.

---

## Key Talking Points

1. **"80% token reduction"** — V.I.S.O.R. sends only the exact code your AI needs
2. **"Every selection is explainable"** — human-readable reasoning for why each node was chosen
3. **"Intent-aware"** — automatically detects if you're debugging, refactoring, or exploring
4. **"Skill-driven"** — pre-loaded strategies that change scoring behavior
5. **"Works everywhere"** — Antigravity, VS Code, Cursor, Claude Code via MCP
