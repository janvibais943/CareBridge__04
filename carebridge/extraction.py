"""Agent 2: Extraction Agent - rule-based by default, optional Claude. Every fact must carry a verbatim quote."""
import re
from .models import Fact, Source, EXTRACTED
from .safety import enforce_citations
from .utils import parse_date

MED_RE = re.compile(
    r"\b([A-Z][a-z]{2,})\s+(\d+(?:\.\d+)?)\s?(mg|mcg|g|IU|units)\s+"
    r"((?i:OD|BD|TDS|QID|HS|once daily|twice daily|daily))\b"
    r"(?:\s+(?i:for)\s+(\d+)\s+(?i:(day|week|month))s?)?")
LAB_RE = re.compile(
    r"\b(HbA1c|Fasting Glucose|Creatinine|LDL|HDL|Total Cholesterol|Triglycerides|TSH|Hemoglobin)\b"
    r"\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(%|mg/dL|mmol/L|mIU/L|g/dL)")
INSTR_RE = re.compile(
    r"\b((?i:review|follow[- ]?up|repeat [A-Za-z0-9 ]{2,30}?|recheck [A-Za-z0-9 ]{2,30}?))\s+"
    r"(?i:(?:visit\s+)?(?:after|in|within))\s+(\d+)\s*(?i:(day|week|month))s?\b")
REF_RE = re.compile(r"\b(?i:refer(?:red)?\s+to)\s+([^.\n]+)")
ADV_RE = re.compile(r"\b(?i:advised|ordered|recommended)\s*:?\s+((?:MRI|CT scan|ultrasound|X-?ray)[^.\n]*)")
APPT_RE = re.compile(r"^\s*Appointment\s*:\s*(.+)$", re.I)
VISIT_RE = re.compile(r"Date of (admission|discharge)\s*:\s*(.+)", re.I)
QUESTION_RE = re.compile(r"(?:Patient question|Question for doctor)\s*:\s*(.+)", re.I)


def extract_facts(docs: list, use_llm: bool = False) -> list:
    facts, counter = [], [0]

    def add(doc, page, kind, date, desc, quote, data=None, conf=0.9):
        counter[0] += 1
        facts.append(Fact(id=f"evt_{counter[0]:03d}", kind=kind, date=date, description=desc, label=EXTRACTED,
                          source=Source(doc.name, page, quote.strip()), data=data or {}, confidence=conf))

    for doc in docs:
        for pno, text in enumerate(doc.pages, 1):
            for line in text.splitlines():
                for m in MED_RE.finditer(line):
                    drug, dose, unit, freq = m.group(1), m.group(2), m.group(3), m.group(4).upper()
                    dur = (int(m.group(5)), m.group(6)) if m.group(5) else None
                    add(doc, pno, "medication", doc.doc_date, f"{drug} {dose} {unit} {freq}", m.group(0),
                        {"drug": drug, "dose": f"{dose} {unit}", "freq": freq, "duration": dur})
                for m in LAB_RE.finditer(line):
                    add(doc, pno, "lab_result", doc.doc_date, f"{m.group(1)} {m.group(2)} {m.group(3)}", m.group(0),
                        {"test": m.group(1), "value": float(m.group(2)), "unit": m.group(3)})
                for m in INSTR_RE.finditer(line):
                    add(doc, pno, "instruction", doc.doc_date, f"Clinician instruction: {m.group(0)}", m.group(0),
                        {"action": m.group(1).strip(), "n": int(m.group(2)), "unit": m.group(3).lower()})
                for rx in (REF_RE, ADV_RE):
                    for m in rx.finditer(line):
                        add(doc, pno, "referral", doc.doc_date, f"Referral/advice: {m.group(1).strip()}", m.group(0),
                            {"topic": m.group(1).strip()})
                m = APPT_RE.match(line)
                if m:
                    t = re.search(r"\b(\d{1,2}:\d{2})\b", m.group(1))
                    dr = re.search(r"Dr\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", m.group(1))
                    add(doc, pno, "appointment", parse_date(m.group(1)), f"Appointment {m.group(1).strip()}", line,
                        {"time": t.group(1) if t else None, "doctor": dr.group(0) if dr else None}, conf=0.85)
                m = VISIT_RE.search(line)
                if m:
                    add(doc, pno, "visit", parse_date(m.group(2)), f"Hospital {m.group(1).lower()}", m.group(0))
                m = QUESTION_RE.search(line)
                if m:
                    add(doc, pno, "patient_question", doc.doc_date, m.group(1).strip(), m.group(0))
    if use_llm:
        from .llm import extract_with_claude
        for doc in docs:
            facts.extend(extract_with_claude(doc, start_id=len(facts) + 1))
    return enforce_citations(facts, docs)  # un-cited facts never survive
