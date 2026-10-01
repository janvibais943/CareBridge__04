import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from carebridge.pipeline import run_pipeline, load_folder
from carebridge.exports import calendar_ics, timeline_csv
from carebridge.safety import triage_question, guard_output, enforce_citations
from carebridge.models import Fact, Source, NEEDS, INFERRED

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data")
TODAY = "2026-10-01"


def case():
    return run_pipeline(load_folder(DATA), today=TODAY, use_llm=False)


def test_every_fact_has_verifiable_quote():
    r = case()
    pages = {d.name: d.pages for d in r.docs}
    assert r.facts
    for f in r.facts:
        assert f.source.quote in pages[f.source.file][f.source.page - 1]


def test_uncited_fact_is_dropped():
    r = case()
    fake = Fact("x", "lab_result", "2026-01-01", "HbA1c 5.0 %", "extracted", Source(r.docs[0].name, 1, "HbA1c 5.0 %"))
    assert enforce_citations([fake], r.docs) == []


def test_document_classification():
    types = {d.name: d.doc_type for d in case().docs}
    assert types["lab_report_2026-09-14.txt"] == "lab_report"
    assert types["discharge_summary_2026-08-10.txt"] == "discharge_summary"
    assert types["appointment_slip_scan.txt"] == "appointment_letter"
    assert types["prescription_drrao_2026-09-20.txt"] == "prescription"


def test_metformin_conflict_flagged_not_resolved():
    r = case()
    assert len(r.conflicts) == 1 and r.conflicts[0]["subject"] == "metformin"
    flagged = [f for f in r.facts if f.data.get("drug") == "Metformin"]
    assert flagged and all(f.label == NEEDS for f in flagged)
    assert all(f.review_status == "pending" for f in flagged)


def test_missing_eye_report_detected():
    r = case()
    topics = [f.data["topic"] for f in r.appointment["missing_documents"]]
    assert any("Ophthalmology" in t for t in topics)


def test_reminders_inferred_and_dated():
    r = case()
    by_due = {x.due: x for x in r.reminders}
    assert "2026-12-20" in by_due and by_due["2026-12-20"].label == INFERRED      # repeat HbA1c, 3 months
    assert by_due["2026-09-21"].status == "overdue"                                # review after 6 weeks
    assert "2026-10-20" in by_due                                                  # 30-day supply


def test_appointment_checklist_contents():
    r = case()
    assert r.appointment["appointment"].date == "2026-10-15"
    text = " ".join(i.text for i in r.appointment["checklist"])
    assert "Confirm Metformin dose" in text and "Missing document" in text and "Has my metformin dose" in text


def test_clinical_questions_refused():
    assert triage_question("What disease do I have?")
    assert triage_question("Should I increase my metformin?")
    assert triage_question("When is my next appointment?") is None


def test_output_filter():
    assert "blocked" in guard_output("You should take 2 tablets")
    assert "blocked" in guard_output("You may have diabetes")


def test_briefing_gate_and_audit():
    r = case()
    assert "DRAFT" in r.briefing()
    assert r.approve_briefing("coordinator1") is False        # pending items block release
    for f in r.facts:
        r.review(f.id, "approved", "coordinator1")
    assert r.approve_briefing("coordinator1") is True
    assert "RELEASED" in r.briefing()
    assert r.audit.entries[-1]["action"] == "briefing_released"
    r.review(r.facts[0].id, "rejected", "coordinator1")       # any edit re-locks the briefing
    assert r.briefing_approved is False


def test_timeline_csv_preserves_source_and_review_fields():
    r = case()
    exported = timeline_csv(r.facts)
    assert "source_file,source_page,source_quote" in exported
    assert "prescription_drrao_2026-09-20.txt" in exported
    assert "Metformin 1000 mg BD" in exported
    assert "needs_confirmation" in exported


def test_calendar_export_contains_appointment_and_future_reminders_only():
    r = case()
    exported = calendar_ics(r)
    assert exported.startswith("BEGIN:VCALENDAR\r\n")
    assert "DTSTART;VALUE=DATE:20261015" in exported
    assert "DTSTART;VALUE=DATE:20261220" in exported
    assert "DTSTART;VALUE=DATE:20260921" not in exported  # overdue follow-ups are omitted
    assert "Source: appointment_slip_scan.txt" in exported
    assert "not medical advice" in exported
    assert exported.endswith("END:VCALENDAR\r\n")
    assert all(len(line.encode("utf-8")) <= 75 for line in exported.split("\r\n") if line)


def test_reviewer_note_is_preserved_in_audit_log():
    r = case()
    fact = next(f for f in r.facts if not f.conflict_group)
    r.review(fact.id, "approved", "coordinator1", "Checked against the signed source page.")
    assert r.audit.entries[-1]["detail"] == "Checked against the signed source page."
