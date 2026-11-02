from app.api.webhooks import webhook_headers

original = {"Content-Type": "application/json", "X-Signature": "stale"}
updated = webhook_headers("fresh", original)
assert updated["X-Signature"] == "fresh"
assert updated["Content-Type"] == "application/json"
assert original["X-Signature"] == "stale"
print("webhook checks passed")
