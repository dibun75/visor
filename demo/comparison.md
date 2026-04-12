# V.I.S.O.R. — Before vs After Comparison

## The Scenario

A developer asks their AI agent: **"Fix the login crash when user is null"**

---

## ❌ Without V.I.S.O.R.

The AI agent begins its search:

```
Agent: Searching for "login" in codebase...
→ grep hits 47 files containing "login"
→ Agent reads src/routes/login.tsx (380 lines)           — ❌ frontend, irrelevant
→ Agent reads src/i18n/en.json containing "login_btn"    — ❌ translation file
→ Agent reads tests/test_auth.py (200 lines)             — ❌ test file
→ Agent reads src/auth/jwt.py (90 lines)                 — ✅ relevant, but read in full
→ Agent reads src/auth/middleware.py (150 lines)          — ✅ relevant, but read in full
→ Agent reads src/config/settings.py (120 lines)         — ❌ config, irrelevant
→ Agent reads src/models/user.py (80 lines)              — ✅ relevant
→ Agent reads src/models/product.py (200 lines)          — ❌ wrong model
```

**Result:**
- 📄 8 files read
- 🔥 ~12,000 tokens burned on context
- ⏱️ 3 search rounds before finding relevant code
- 🤷 No explanation of why these files were chosen
- 💰 $0.036 per query at GPT-4 rates

---

## ✅ With V.I.S.O.R.

The AI agent calls one MCP tool:

```
Agent: build_context("login crash when user is null", skill="bug-fixer")
```

V.I.S.O.R. responds instantly:

```
  Intent: BUG_FIX  |  Skill: bug-fixer

  [2.8500]  src/auth/jwt.py:verify_token (lines 15-34)
            → Matched query token in symbol name
            → Recently modified file (boosted)

  [2.1200]  src/auth/middleware.py:auth_guard (lines 8-22)
            → Reachable via dependency chain
            → Semantic similarity (0.42)

  [1.4500]  src/models/user.py:User (lines 5-18)
            → Matched query token in symbol name

  [0.8700]  src/db/session.py:get_session (lines 12-19)
            → Reachable via dependency chain
```

**Result:**
- 📄 4 precise code snippets (not full files)
- 🔥 ~2,180 tokens — **80.9% reduction**
- ⏱️ 1 tool call, instant response
- 🧠 Human-readable reasoning for every selection
- 💰 $0.007 per query — **5x cheaper**

---

## Side-by-Side

| Metric | Without V.I.S.O.R. | With V.I.S.O.R. |
|--------|------|------|
| Files searched | 8 (blind grep) | 4 (ranked + scored) |
| Tokens consumed | ~12,000 | ~2,180 |
| Search rounds | 3 | 1 |
| Explainability | None | Per-node reasoning |
| Relevant code ratio | ~37% | ~100% |
| Cost per query (GPT-4) | $0.036 | $0.007 |

---

## The Difference

Without V.I.S.O.R., AI agents play a guessing game — reading file after file hoping to find what's relevant. Each wrong file burns tokens and money.

With V.I.S.O.R., the agent gets **exactly the right code, in one call**, with a clear explanation of why each piece was selected. The AI spends its token budget on *solving your problem*, not *finding your code*.
