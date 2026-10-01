# CareBridge: AI Care-Navigation Agent

Turns scattered patient paperwork (reports, prescriptions, discharge notes, appointment slips) into a
**verified timeline** and an **admin checklist**. It coordinates; it never diagnoses or recommends treatment.

## Pipeline
`Document -> Extraction -> Timeline -> Appointment -> Follow-up -> Summary`, with human review gates.

| Agent | File | Job |
|---|---|---|
| 1 Document | `documents.py` | load txt/PDF, OCR scans, classify type, find date |
| 2 Extraction | `extraction.py`, `llm.py` | structured facts, each with a verbatim quote (rules by default, Claude optional) |
| 3 Timeline | `timeline.py` | order, de-duplicate, flag conflicts side by side |
| 4 Appointment | `appointment.py` | prep checklist + missing-document detection |
| 5 Follow-up | `followup.py` | reminders only from instructions a clinician wrote |
| 6 Summary | `summary.py` | one-page briefing, DRAFT until released |

## Facts vs assumptions
Every item has a label: **Extracted** (verbatim + citation), **Inferred** (system-derived, e.g. "6 weeks after 10 Aug"),
or **Needs confirmation** (conflict / missing). Conflicts are shown together; the system never chooses.

## Safety and control
- `safety.py`: citations are re-verified against the source page (un-cited facts are dropped, including LLM output);
  blocked-phrase output filter; clinical questions ("What disease do I have?") are refused; PHI redaction before any LLM call.
- `audit.py` + `pipeline.py`: every approve/reject is logged; the briefing cannot be released while items are pending;
  any later edit re-locks it.

## Coordinator experience
- Evidence-first dashboard with searchable/filterable timeline and cited page previews; the source quote is highlighted.
- Human review queue keeps conflicting source records side by side and logs each decision.
- Reviewers can attach a short rationale to approve/reject decisions; notes are retained in the audit export.
- Appointment checklist items can be checked off in the current browser session.
- Download a filtered timeline as CSV with source citations, review status, confidence, and conflict metadata.
- Export the appointment and non-overdue follow-ups to an all-day calendar file (.ics), retaining source evidence in event descriptions.
- Briefing and progress snapshot (review decisions, task completion, and audit events) can be downloaded.
- Review and task state is kept in Streamlit session memory; it is not a secure or durable patient-record store.

## Run
```bash
pip install -r requirements.txt
python run_demo.py              # CLI briefing for the synthetic patient
streamlit run app.py            # evidence dashboard, review queue, prep tasks, reminders, briefing, audit
python -m pytest -q tests       # 10 tests
```
Optional LLM extraction: `export ANTHROPIC_API_KEY=...  CAREBRIDGE_USE_LLM=1` (uses `CAREBRIDGE_MODEL`, default `claude-sonnet-5-5`).

## Demo story (`sample_data/`)
Five synthetic documents -> timeline; **Metformin 500 mg BD vs 1000 mg BD** flagged for confirmation;
**ophthalmology referral with no report** listed as missing; **review after 6 weeks** shown overdue;
**repeat HbA1c** reminder dated 20 Dec 2026; appointment checklist for 15 Oct; briefing released only after review.

## Limits / next steps
Rule-based extraction covers common formats only (use the LLM mode or add rules for others); no real auth or
encryption yet (add role-based access, encrypted storage, on-prem model for real PHI); reminders are shown in the UI
(add APScheduler + SMS/email). Review decisions and task completion are session-scoped; export a progress snapshot
to preserve a handoff. Use synthetic data only until a security and compliance review is done.
