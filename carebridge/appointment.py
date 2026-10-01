"""Agent 4: Appointment Agent - prep checklist + missing-document detection (admin only)."""
import re
from .models import ChecklistItem, EXTRACTED, INFERRED, NEEDS

REPORT_TYPES = {"specialist_report", "imaging_report"}
TOPIC_KEYWORDS = [
    (r"ophthal|eye|retina", ["ophthal", "fundus", "retinopathy"]),
    (r"\bmri\b", ["mri"]),
    (r"\bct\b|ct scan", ["ct scan", "computed tomography"]),
    (r"ultrasound|usg", ["ultrasound", "usg"]),
    (r"x-?ray", ["x-ray", "xray"]),
    (r"cardio|ecg|echo", ["ecg", "echocardiogram", "cardiolog"]),
    (r"nephro|kidney", ["nephrolog"]),
]


def _keywords(topic: str) -> list:
    for pat, kws in TOPIC_KEYWORDS:
        if re.search(pat, topic, re.I):
            return kws
    return [topic.split()[0].lower()]


def find_missing_documents(facts: list, docs: list) -> list:
    missing = []
    for f in facts:
        if f.kind != "referral":
            continue
        kws = _keywords(f.data["topic"])
        covered = any(d.name != f.source.file and d.doc_type in REPORT_TYPES
                      and any(k in d.text.lower() for k in kws) for d in docs)
        if not covered:
            missing.append(f)
    return missing


def prepare_appointment(facts: list, docs: list, reminders: list, today: str):
    upcoming = [f for f in facts if f.kind == "appointment" and f.date and f.date >= today]
    if not upcoming:
        return None
    appt = min(upcoming, key=lambda f: f.date)
    items = [ChecklistItem("Bring original copies of: " + ", ".join(d.name for d in docs), EXTRACTED, category="bring")]

    # Medications as documented (conflicts go to confirmation, never silently resolved)
    meds = {}
    for f in facts:
        if f.kind == "medication":
            meds.setdefault(f.data["drug"], []).append(f)
    for drug, fs in meds.items():
        if any(f.conflict_group for f in fs):
            detail = "; ".join(dict.fromkeys(f"{f.data['dose']} {f.data['freq']} ({f.source.file}, {f.date})" for f in fs))
            items.append(ChecklistItem(f"Confirm {drug} dose with the prescriber. Documents disagree: {detail}",
                                       NEEDS, fs[-1].source, "confirm"))
        else:
            latest = max(fs, key=lambda f: f.date or "")
            items.append(ChecklistItem(f"Bring medication / strips: {latest.description}", EXTRACTED, latest.source, "bring"))

    labs = [f for f in facts if f.kind == "lab_result"]
    if labs:
        newest = max(f.date or "" for f in labs)
        items.append(ChecklistItem("Bring latest lab report(s) dated " + newest, EXTRACTED,
                                   [f for f in labs if (f.date or "") == newest][0].source, "bring"))

    missing = find_missing_documents(facts, docs)
    for f in missing:
        items.append(ChecklistItem(f"Missing document: no report on file for '{f.data['topic']}' "
                                   f"(mentioned in {f.source.file}). Obtain it, or confirm it was not done.",
                                   NEEDS, f.source, "missing"))
    for r in reminders:
        if r.status in ("overdue", "due_soon"):
            items.append(ChecklistItem(f"Follow-up {r.status.replace('_', ' ')}: {r.title} (due ~{r.due})",
                                       INFERRED, r.basis, "followup"))
    for f in facts:
        if f.kind == "patient_question":
            items.append(ChecklistItem(f"Patient's own question for the doctor: {f.description}", EXTRACTED, f.source, "question"))
    return {"appointment": appt, "checklist": items, "missing_documents": missing}
