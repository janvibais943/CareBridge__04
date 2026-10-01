"""Safety layer: citation enforcement, output filter, clinical-question triage, PHI redaction."""
import re
from .models import Fact
from .utils import norm

BLOCKED_OUTPUT = [
    r"\byou (may|might|probably|likely) have\b",
    r"\byou (should|must) (take|stop|start|increase|reduce)\b",
    r"\b(increase|decrease|reduce|double|skip|stop) (the |your )?(dose|dosage|medication|medicine)\b",
    r"\bi recommend\b",
    r"\b(this|which) (indicates|suggests|means) (you|the patient) ha(s|ve)\b",
    r"\bstart taking\b",
]
CLINICAL_INTENT = [
    r"what (disease|condition|illness|disorder)", r"\bdo i have\b", r"\bdiagnos",
    r"should i (take|stop|increase|skip|start|reduce)", r"which (medicine|drug|dose|tablet)",
    r"is it (cancer|serious|dangerous)", r"what (treatment|medicine) ",
]
REFUSAL = ("I can't diagnose conditions or advise on treatment. CareBridge only organises records and "
           "admin tasks. Please raise this with your doctor; it can be added to the questions list for your appointment.")


def guard_output(text: str) -> str:
    """Replace any generated phrase that sounds like diagnosis/treatment advice."""
    for pat in BLOCKED_OUTPUT:
        text = re.sub(pat, "[blocked by safety filter]", text, flags=re.I)
    return text


def triage_question(question: str):
    """Return a refusal if the question is clinical, else None."""
    if any(re.search(p, question, re.I) for p in CLINICAL_INTENT):
        return REFUSAL
    return None


def verify_citation(fact: Fact, page_texts: dict) -> bool:
    """A fact is only valid if its quote really appears on the cited page."""
    pages = page_texts.get(fact.source.file)
    if not pages or not (1 <= fact.source.page <= len(pages)):
        return False
    return bool(fact.source.quote) and norm(fact.source.quote) in norm(pages[fact.source.page - 1])


def enforce_citations(facts: list, docs: list) -> list:
    """Drop facts with no verifiable source span (never trust un-cited claims)."""
    page_texts = {d.name: d.pages for d in docs}
    return [f for f in facts if verify_citation(f, page_texts)]


_PHI = [(r"[\w.+-]+@[\w-]+\.[\w.]+", "[EMAIL]"), (r"\+?\d[\d\s\-]{8,}\d", "[PHONE/ID]")]


def redact(text: str) -> str:
    """Strip obvious identifiers before any external model call."""
    for pat, rep in _PHI:
        text = re.sub(pat, rep, text)
    return text
