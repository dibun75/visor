"""Quick HTTP wrapper to test VISOR telemetry via curl.
Simulates the real daemon lifecycle: prune old changelog → then serve fresh queries.
"""
import json
import sqlite3
import sqlite_vec
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_PATH = "visor_memory.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn

# ── Boot-time prune (simulates what index_workspace now does) ──
print("[boot] Pruning stale file_changelog entries...")
boot_conn = get_conn()
boot_conn.execute(
    "DELETE FROM file_changelog WHERE datetime(changed_at) < datetime('now', '-300 seconds')"
)
boot_conn.commit()
c = boot_conn.cursor()
c.execute("SELECT COUNT(*) FROM file_changelog")
print(f"[boot] Remaining changelog rows after prune: {c.fetchone()[0]}")
boot_conn.close()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        conn = get_conn()
        conn.commit()  # flush read snapshot
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM code_nodes")
        nodes = c.fetchone()[0]

        c.execute("SELECT IFNULL(SUM(length(content)), 0) FROM agent_memory")
        burn = c.fetchone()[0]

        # Fixed drift query
        c.execute(
            "SELECT COUNT(*) FROM file_changelog "
            "WHERE datetime(changed_at) > datetime('now', '-60 seconds')"
        )
        drift_count = c.fetchone()[0]

        # Old broken query for comparison
        c.execute(
            "SELECT COUNT(*) FROM file_changelog "
            "WHERE changed_at > datetime('now', '-60 seconds')"
        )
        drift_old = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM file_changelog")
        total = c.fetchone()[0]

        data = {
            "graph_nodes": nodes,
            "context_burn": burn,
            "drift_alert": drift_count > 0,
            "debug": {
                "drift_fixed_count": drift_count,
                "drift_old_broken_count": drift_old,
                "total_changelog_rows": total,
            }
        }
        conn.close()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

print("Serving on http://localhost:9999 — curl http://localhost:9999")
HTTPServer(("", 9999), Handler).serve_forever()
