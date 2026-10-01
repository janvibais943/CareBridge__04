"""Agent 6: Summary Agent - one-page doctor briefing. Marked DRAFT until a human releases it."""
from .safety import guard_output

TAG = {"extracted": "Extracted", "inferred": "Inferred", "needs_confirmation": "NEEDS CONFIRMATION"}


def build_briefing(res, patient: str = "Patient (synthetic demo)") -> str:
    L = []
    pending = sum(1 for f in res.facts if f.review_status == "pending")
    unresolved = sum(1 for c in res.conflicts for f in c["items"] if f.review_status == "pending")
    status = "RELEASED (approved by coordinator)" if res.briefing_approved else "DRAFT - not reviewed, do not release"
    L += [f"# Doctor Briefing: {patient}", f"*Status: {status} | Generated for {res.today} | "
          f"{pending} extracted items pending review*", "",
          "> Administrative summary compiled from submitted documents. It contains no diagnosis or treatment advice. "
          "Items marked Inferred / NEEDS CONFIRMATION are not established facts.", ""]
    if res.appointment:
        a = res.appointment["appointment"]
        L += ["## Upcoming appointment", f"- {a.description} [{TAG[a.label]}; {a.source.file} p{a.source.page}]", ""]
    L += ["## Timeline", "| Date | Event | Label | Source |", "|---|---|---|---|"]
    for f in res.facts:
        if f.kind == "patient_question" or f.review_status == "rejected":
            continue
        L.append(f"| {f.date or '?'} | {f.description} | {TAG[f.label]} | {f.source.file} p{f.source.page}: \"{f.source.quote}\" |")
    L += ["", "## Medications as documented (not a prescription list)"]
    seen = set()
    for f in res.facts:
        if f.kind == "medication" and f.review_status != "rejected":
            k = (f.data["drug"], f.data["dose"], f.data["freq"])
            if k not in seen:
                seen.add(k)
                flag = " **<- documents disagree, see below**" if f.conflict_group else ""
                L.append(f"- {f.description} ({f.date}, {f.source.file}){flag}")
    L += ["", "## Needs confirmation"]
    if not res.conflicts and not (res.appointment and res.appointment["missing_documents"]):
        L.append("- None")
    for c in res.conflicts:
        vals = " vs ".join(dict.fromkeys(f"{f.description} (e.g. {f.source.file}, {f.date})" for f in c["items"]))
        L.append(f"- **Conflict, {c['subject']}:** {vals}. {'(resolved by reviewer)' if not any(f.review_status == 'pending' for f in c['items']) else 'Unresolved.'}")
    if res.appointment:
        for f in res.appointment["missing_documents"]:
            L.append(f"- **Missing document:** nothing on file for '{f.data['topic']}' (mentioned in {f.source.file}).")
    L += ["", "## Follow-ups written in the record (dates calculated by system, Inferred)"]
    L += [f"- {r.due}: {r.title} [{r.status}]. Basis: \"{r.basis.quote}\" ({r.basis.file})" for r in res.reminders] or ["- None"]
    if res.appointment:
        L += ["", "## Appointment prep checklist"]
        L += [f"- [{TAG[i.label]}] {i.text}" for i in res.appointment["checklist"]]
    L += ["", f"*Unresolved conflicts awaiting a human decision: {unresolved}*"]
    return guard_output("\n".join(L))
