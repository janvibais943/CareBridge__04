"""Append-only audit log + human review actions."""
import json
import time


class AuditLog:
    def __init__(self, path=None):
        self.path, self.entries = path, []

    def log(self, user: str, action: str, item_id: str, detail: str = ""):
        e = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "user": user, "action": action, "item": item_id, "detail": detail}
        self.entries.append(e)
        if self.path:
            with open(self.path, "a") as fh:
                fh.write(json.dumps(e) + "\n")


def review(item, status: str, user: str, audit: AuditLog, note: str = ""):
    assert status in ("approved", "rejected", "pending")
    item.review_status = status
    audit.log(user, status, item.id, note)
