"""
experience.py — Calculate total work experience from date ranges in resume text.

Handles many real-world resume formats:
  Feb 2024 – Present
  Jan 2020 - Mar 2023
  June 2018 to December 2021
  03/2017 – 08/2019
  2019 - Current
  Feb 2024 - Present | Some Company
"""
import re
from datetime import datetime

try:
    from dateutil import parser as dateparser
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False


# ── Regex ─────────────────────────────────────────────────────────────────────

_MONTHS = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)

_DATE = (
    rf"(?:{_MONTHS}\.?\s+\d{{4}}"   # Feb 2024 / February 2024
    rf"|\d{{1,2}}/\d{{4}}"          # 02/2024
    rf"|\d{{4}})"                   # 2024
)

# All dash/hyphen variants: -, –, —, and unicode variants
_SEP = r"\s*(?:\u2013|\u2014|\u2012|\u2010|-|to|till|until)\s*"

_PRESENT = r"(?:Present|Current|Now|Till\s*[Dd]ate|Ongoing|Today)"
_END = rf"(?:{_DATE}|{_PRESENT})"

RANGE_RE = re.compile(
    rf"({_DATE})\s*{_SEP}\s*({_END})",
    re.IGNORECASE | re.UNICODE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(raw: str) -> datetime | None:
    raw = raw.strip()
    if re.match(r"present|current|now|till\s*date|ongoing|today", raw, re.IGNORECASE):
        return datetime.today()
    if not HAS_DATEUTIL:
        return None
    try:
        return dateparser.parse(raw, default=datetime(2000, 1, 1))
    except Exception:
        return None


def _months_between(a: datetime, b: datetime) -> int:
    return max(0, (b.year - a.year) * 12 + (b.month - a.month))


# ── Public API ────────────────────────────────────────────────────────────────

def extract_experience(text: str) -> dict:
    """
    Scan resume text for date ranges and sum total work experience.
    Deduplicates overlapping ranges.
    """
    ranges = []

    for m in RANGE_RE.finditer(text):
        raw_start = m.group(1).strip()
        raw_end   = m.group(2).strip()

        start = _parse_date(raw_start)
        end   = _parse_date(raw_end)

        if not start or not end or end < start:
            continue

        months = _months_between(start, end)
        if months == 0 or months > 480:   # skip 0-month or >40yr (bad parse)
            continue

        ranges.append({
            "start":   start,
            "end":     end,
            "months":  months,
            "label":   f"{raw_start} – {raw_end}",
        })

    # Deduplicate by (start_month, end_month)
    seen = set()
    unique = []
    for r in ranges:
        key = (r["start"].year, r["start"].month, r["end"].year, r["end"].month)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    total_months = sum(r["months"] for r in unique)
    years  = total_months // 12
    months = total_months % 12

    if total_months == 0:
        display = "Not detected"
    elif years == 0:
        display = f"{months} month{'s' if months != 1 else ''}"
    elif months == 0:
        display = f"{years} year{'s' if years != 1 else ''}"
    else:
        display = f"{years} year{'s' if years != 1 else ''} {months} month{'s' if months != 1 else ''}"

    return {
        "total_years":  round(total_months / 12, 1),
        "total_months": total_months,
        "ranges_found": [r["label"] for r in unique],
        "display":      display,
    }
