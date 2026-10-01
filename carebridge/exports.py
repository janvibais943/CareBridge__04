"""Interoperable, administrative exports for a reviewed CareBridge case."""
import csv
import hashlib
import io
from datetime import date, datetime, timedelta, timezone


def timeline_csv(facts: list) -> str:
    """Return timeline rows with provenance, review state, and conflict metadata."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "date", "type", "description", "evidence_label", "review_status",
        "source_file", "source_page", "source_quote", "confidence", "conflict_group",
    ])
    for fact in facts:
        writer.writerow([
            fact.date or "", fact.kind, fact.description, fact.label, fact.review_status,
            fact.source.file, fact.source.page, fact.source.quote,
            f"{fact.confidence:.2f}", fact.conflict_group or "",
        ])
    return output.getvalue()


def _ical_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def _fold(line: str) -> list[str]:
    """Fold a content line at the RFC 5545 75-octet limit without splitting UTF-8."""
    parts, current, size = [], [], 0
    for char in line:
        encoded_size = len(char.encode("utf-8"))
        if size + encoded_size > 75:
            parts.append("".join(current))
            current, size = [" "], 1  # continuation whitespace counts as an octet
        current.append(char)
        size += encoded_size
    parts.append("".join(current))
    return parts


def _event(uid_seed: str, event_date: str, summary: str, description: str) -> list[str]:
    parsed = date.fromisoformat(event_date)
    uid = hashlib.sha256(uid_seed.encode("utf-8")).hexdigest()[:24] + "@carebridge"
    return [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;VALUE=DATE:{parsed.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{(parsed + timedelta(days=1)).strftime('%Y%m%d')}",
        f"SUMMARY:{_ical_escape(summary)}",
        f"DESCRIPTION:{_ical_escape(description)}",
        "END:VEVENT",
    ]


def calendar_ics(case) -> str:
    """Export the appointment and non-overdue administrative reminders as all-day events."""
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CareBridge//Care Coordination//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:CareBridge follow-ups",
    ]
    if case.appointment:
        appointment = case.appointment["appointment"]
        citation = (f"Source: {appointment.source.file}, page {appointment.source.page}. "
                    f"Quote: {appointment.source.quote}")
        lines.extend(_event(
            f"appointment|{appointment.id}|{appointment.source.file}", appointment.date,
            appointment.description, "Administrative appointment entry. Verify details with the original record. " + citation,
        ))
    for reminder in case.reminders:
        if reminder.status == "overdue":
            continue
        citation = f"Source: {reminder.basis.file}, page {reminder.basis.page}. Quote: {reminder.basis.quote}"
        lines.extend(_event(
            f"reminder|{reminder.id}|{reminder.due}", reminder.due,
            "Care coordination: " + reminder.title,
            "Administrative follow-up only; this is not medical advice. Verify with the care team. " + citation,
        ))
    lines.append("END:VCALENDAR")
    return "\r\n".join(part for line in lines for part in _fold(line)) + "\r\n"
