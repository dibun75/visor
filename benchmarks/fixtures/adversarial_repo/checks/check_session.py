from app.api.sessions import session_permissions

assert session_permissions(["admin", "read"], ["read"]) == ["read"]
assert session_permissions([], ["read", "write"]) == ["read", "write"]
print("session checks passed")
