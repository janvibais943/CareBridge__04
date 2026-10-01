"""Agent 3: Timeline Agent - order events, merge duplicates, surface conflicts (never pick a winner)."""
from collections import defaultdict
from .models import NEEDS
from .utils import norm


def build_timeline(facts: list):
    seen, merged = {}, []
    for f in facts:
        key = (f.kind, norm(f.description), f.date)
        if key in seen:
            seen[key].data.setdefault("also_in", []).append(f.source.file)
            continue
        seen[key] = f
        merged.append(f)
    conflicts = _flag_conflicts(merged)
    merged.sort(key=lambda f: (f.date or "9999-12-31", f.kind, f.id))
    return merged, conflicts


def _flag_conflicts(facts: list) -> list:
    groups = defaultdict(list)
    for f in facts:
        if f.kind == "medication":
            groups[("med", f.data["drug"].lower())].append(f)
        elif f.kind == "lab_result":
            groups[("lab", f.data["test"].lower(), f.date)].append(f)
    conflicts = []
    for key, items in groups.items():
        variants = {(f.data["dose"], f.data["freq"]) if key[0] == "med" else (f.data["value"], f.data["unit"])
                    for f in items}
        if len(variants) < 2:
            continue
        gid = f"conflict_{len(conflicts) + 1}"
        note = ("Different values documented for the same item. This may be an intentional change "
                "by a clinician or an error; the system cannot tell. Please confirm with the prescriber/lab.")
        for f in items:
            f.label, f.conflict_group = NEEDS, gid
            f.data["conflict_note"] = note
        conflicts.append({"id": gid, "subject": key[1], "type": key[0],
                          "items": sorted(items, key=lambda f: f.date or "")})
    return conflicts
