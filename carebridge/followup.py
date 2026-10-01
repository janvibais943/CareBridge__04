"""Agent 5: Follow-up Agent - reminders only from instructions a clinician already wrote."""
from datetime import date
from .models import Reminder, INFERRED
from .utils import add_duration


def _status(due: str, today: str) -> str:
    delta = (date.fromisoformat(due) - date.fromisoformat(today)).days
    return "overdue" if delta < 0 else "due_soon" if delta <= 14 else "upcoming"


def build_reminders(facts: list, today: str) -> list:
    out, seen = [], set()
    for f in facts:
        if not f.date:
            continue
        if f.kind == "instruction":
            due = add_duration(f.date, f.data["n"], f.data["unit"])
            title = f"{f.data['action'][0].upper() + f.data['action'][1:]} (as written by clinician)"
        elif f.kind == "medication" and f.data.get("duration"):
            n, unit = f.data["duration"]
            due = add_duration(f.date, n, unit)
            title = f"Supply of {f.data['drug']} {f.data['dose']} may run out; check refill with prescriber"
        else:
            continue
        if (title, due) in seen:
            continue
        seen.add((title, due))
        out.append(Reminder(id=f"rem_{len(out) + 1:03d}", title=title, due=due, label=INFERRED,
                            basis=f.source, status=_status(due, today)))
    return sorted(out, key=lambda r: r.due)
