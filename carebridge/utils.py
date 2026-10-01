import calendar
import re
from datetime import date, timedelta
from typing import Optional

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
DATE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2})\b"
    r"|\b(\d{1,2})[ \-]([A-Za-z]{3})[a-z]*[ ,\-]*(\d{4})\b"
    r"|\b(\d{1,2})/(\d{1,2})/(\d{4})\b"
)


def parse_date(s: str) -> Optional[str]:
    m = DATE_RE.search(s or "")
    if not m:
        return None
    try:
        if m.group(1):
            return date.fromisoformat(m.group(1)).isoformat()
        if m.group(2):
            return date(int(m.group(4)), MONTHS[m.group(3).lower()], int(m.group(2))).isoformat()
        return date(int(m.group(7)), int(m.group(6)), int(m.group(5))).isoformat()  # DD/MM/YYYY
    except (ValueError, KeyError):
        return None


def add_duration(iso: str, n: int, unit: str) -> str:
    d = date.fromisoformat(iso)
    unit = unit.lower().rstrip("s")
    if unit == "day":
        return (d + timedelta(days=n)).isoformat()
    if unit == "week":
        return (d + timedelta(weeks=n)).isoformat()
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1])).isoformat()


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()
