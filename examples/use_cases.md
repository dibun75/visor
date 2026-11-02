# V.I.S.O.R. — Example Use Cases

Illustrative workflows for using V.I.S.O.R. with coding agents. Results depend on the indexed repository and retrieval mode.

---

## 1. Fix a Bug

**Scenario:** Your app crashes when a user logs in with a null email.

```bash
uv run visor fix "login crash when email is null"
```

**What V.I.S.O.R. does:**
- Detects `BUG_FIX` intent and applies its ranking profile
- Ranks lexical results using exact-name, same-file, dependency, and recency signals
- Returns snippets within the configured local token budget

**What your AI gets:** ranked candidate symbols, source snippets, and a reason for each selection. V.I.S.O.R. does not diagnose or fix the bug itself.

---

## 2. Understand a Module

**Scenario:** You're new to the codebase and need to understand the database layer.

```bash
uv run visor explain "database client module"
```

**What V.I.S.O.R. does:**
- Detects `EXPLAIN` intent and applies its ranking profile
- Uses lexical retrieval by default; optional semantic mode adds embedding similarity
- Returns ranked symbols and their graph relationships

**What your AI gets:** the most relevant indexed symbols V.I.S.O.R. can find. Names shown here are examples, not guaranteed output.

---

## 3. Trace a Request Flow

**Scenario:** You need to understand how a request flows from the API layer to the database.

```bash
uv run visor trace src/api/routes.py src/db/client.py
```

**What V.I.S.O.R. does:**
- Queries the dependency graph for the shortest path
- Returns every file in the chain

**Illustrative output:**
```json
{
  "source": "src/api/routes.py",
  "target": "src/db/client.py",
  "path": [
    "src/api/routes.py",
    "src/services/user_service.py",
    "src/repositories/user_repo.py",
    "src/db/client.py"
  ],
  "hops": 3
}
```

---

## 4. Detect Impact of a Change

**Scenario:** You're about to refactor `src/db/client.py` and want to know what else might break.

```bash
# Via MCP tool (in your AI session):
# impact_analysis("src/db/client.py")
```

**Illustrative return shape:**
```json
{
  "target": "src/db/client.py",
  "blast_radius": [
    "src/repositories/user_repo.py",
    "src/services/user_service.py",
    "src/api/routes.py",
    "src/workers/email_worker.py"
  ]
}
```

**Why this matters:** The graph provides candidates to inspect; it is not a guarantee that every listed file will break or that no unlisted file can be affected.

---

## 5. Safe Refactoring

**Scenario:** You want to refactor the authentication module.

```bash
uv run visor context "refactor auth module" --skill refactor-assistant
```

**What V.I.S.O.R. does:**
- Detects **REFACTOR** intent → activates `refactor-assistant` skill
- Boosts dependency weight (1.5×) to map the full graph
- Boosts exact match weight (1.5×) to catch all `auth` references
- Returns a ranked, token-budgeted view of matching symbols and graph neighbors

---

## 6. Check for Stale Context

**Scenario:** You've been working on a bug for 30 minutes. Have any files changed since your AI loaded context?

```bash
uv run visor drift
```

**Illustrative output:**
```
============================================================
  V.I.S.O.R. Drift Monitor — Recent Changes
============================================================
  2026-04-13T01:02:15  src/auth/jwt.py
  2026-04-13T00:58:42  src/models/user.py
============================================================
```

**Why this matters:** If your AI is still working with the old version of `jwt.py`, it might hallucinate a fix that's already been applied.

---

## 7. Create a Custom Skill

**Scenario:** Your team has a specific debugging workflow for database issues.

```python
# Via MCP tool:
add_custom_skill(
    name="db-debugger",
    description="Database issue investigation",
    content="Focus on connection pools, query timeouts, and transaction locks.",
    strategy='{"intent_override": "BUG_FIX", "scoring_bias": {"dep": 2.0, "recency": 1.8}}'
)
```

Then use it:
```bash
uv run visor context "connection pool exhaustion" --skill db-debugger
```
