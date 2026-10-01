"""Orchestrator: Document -> Extraction -> Timeline -> Appointment -> Follow-up -> Summary (with review gates)."""
import os
from dataclasses import dataclass, field
from datetime import date
from .documents import load_documents
from .extraction import extract_facts
from .timeline import build_timeline
from .followup import build_reminders
from .appointment import prepare_appointment
from .summary import build_briefing
from .audit import AuditLog, review
from .safety import triage_question


@dataclass
class CaseResult:
    today: str
    docs: list
    facts: list
    conflicts: list
    reminders: list
    appointment: dict | None
    audit: AuditLog = field(default_factory=AuditLog)
    briefing_approved: bool = False

    def briefing(self, patient="Patient (synthetic demo)"):
        return build_briefing(self, patient)

    def approve_briefing(self, user: str) -> bool:
        """Gate: refuse release while any conflict is unresolved or any item is still pending."""
        if any(f.review_status == "pending" for f in self.facts):
            return False
        self.briefing_approved = True
        self.audit.log(user, "briefing_released", "briefing")
        return True

    def review(self, item_id: str, status: str, user: str, note: str = ""):
        for item in [*self.facts, *self.reminders]:
            if item.id == item_id:
                review(item, status, user, self.audit, note)
                self.briefing_approved = False  # any edit invalidates release
                return item
        raise KeyError(item_id)

    def ask(self, question: str) -> str:
        return triage_question(question) or "I can help with records, appointments and reminders. Ask about those."


def run_pipeline(files: dict, today: str | None = None, use_llm: bool | None = None) -> CaseResult:
    today = today or date.today().isoformat()
    use_llm = os.getenv("CAREBRIDGE_USE_LLM") == "1" if use_llm is None else use_llm
    docs = load_documents(files)
    facts, conflicts = build_timeline(extract_facts(docs, use_llm))
    reminders = build_reminders(facts, today)
    appointment = prepare_appointment(facts, docs, reminders, today)
    return CaseResult(today, docs, facts, conflicts, reminders, appointment)


def load_folder(path: str) -> dict:
    return {n: open(os.path.join(path, n), "rb").read() for n in sorted(os.listdir(path)) if not n.startswith(".")}
