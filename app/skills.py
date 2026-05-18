"""
skills.py — LLM for skills + Python for experience.

Fixes in this version:
  - Spaced PDF headers: "E DUCATION", "P ROFESSIONAL E XPERIENCE" now detected
  - ci/cd no longer split into "ci" and "cd" — only splits on " or ", not "/"
  - Summary LLM fallback: if Python finds no dates, ask LLM to read summary
  - Phone numbers no longer matched as date ranges (_STRICT_START fix)
  - Skill alias matching: "gen ai" matches "generative ai", etc.
"""
import json
import re
from datetime import datetime

import ollama

from app.config import OLLAMA_HOST, OLLAMA_PORT, OLLAMA_MODEL

client = ollama.Client(host=f"http://{OLLAMA_HOST}:{OLLAMA_PORT}")


# ═════════════════════════════════════════════════════════════════════════════
# PART 1 — EXPERIENCE  (Python regex + optional LLM summary fallback)
# ═════════════════════════════════════════════════════════════════════════════

_MON = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE    = rf"(?:{_MON}\.?\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
_SEP     = r"\s*(?:\u2013|\u2014|\u2012|\u2010|-|to|till|until)\s*"
_PRESENT = r"(?:Present|Current|Now|Ongoing|Today|Till\s*[Dd]ate)"

# FIX: range START must be "Month YYYY" or "MM/YYYY" — never bare digits.
# This prevents phone numbers like "+91 7389317720" matching as date ranges.
_STRICT_START = rf"(?:{_MON}\.?\s+\d{{4}}|\d{{1,2}}/\d{{4}})"
_RANGE_RE = re.compile(
    rf"({_STRICT_START})\s*{_SEP}\s*({_DATE}|{_PRESENT})",
    re.IGNORECASE | re.UNICODE,
)

# Matches both normal and spaced PDF headers: "EDUCATION" or "E DUCATION"
_EDU_RE = re.compile(
    r"E\s*D\s*U\s*C\s*A\s*T\s*I\s*O\s*N"
    r"|A\s*C\s*A\s*D\s*E\s*M\s*I\s*C"
    r"|Q\s*U\s*A\s*L\s*I\s*F\s*I\s*C\s*A\s*T\s*I\s*O\s*N"
    r"|C\s*E\s*R\s*T\s*I\s*F\s*I\s*C\s*A\s*T\s*I\s*O\s*N",
    re.IGNORECASE,
)

_SUMMARY_YEARS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\+?\s*years?\s+of\s+(?:professional\s+|work\s+)?experience",
    re.IGNORECASE,
)

_MON_MAP = {
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
    "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
}


def _parse_date(raw: str) -> datetime | None:
    raw = raw.strip().lower()
    if re.match(r"present|current|now|ongoing|today|till\s*date", raw):
        return datetime.now()
    m = re.match(r"([a-z]+)\.?\s+(\d{4})", raw)
    if m:
        mon = _MON_MAP.get(m.group(1)[:3])
        if mon:
            return datetime(int(m.group(2)), mon, 1)
    m = re.match(r"^(\d{4})$", raw.strip())
    if m:
        return datetime(int(m.group(1)), 1, 1)
    m = re.match(r"(\d{1,2})/(\d{4})", raw)
    if m:
        return datetime(int(m.group(2)), int(m.group(1)), 1)
    return None


def _build_display(months: int) -> str:
    if months <= 0:
        return "Not detected"
    y, m = months // 12, months % 12
    if y == 0:
        return f"{m} month{'s' if m!=1 else ''}"
    if m == 0:
        return f"{y} year{'s' if y!=1 else ''}"
    return f"{y} year{'s' if y!=1 else ''} {m} month{'s' if m!=1 else ''}"


def _extract_experience_python(text: str) -> dict:
    """
    Step 1: Cut at education section (handles spaced PDF headers like 'E DUCATION').
    Step 2: Regex scan for job date ranges.
    Step 3: Fallback — check summary for 'X+ years of experience'.
    Step 4: Fallback — ask LLM to read summary/experience section directly.
    """
    _fallback = {
        "total_years": 0.0, "total_months": 0,
        "ranges_found": [], "display": "Not detected",
    }

    # Step 1: cut at education section
    edu = _EDU_RE.search(text)
    scan_text = text[:edu.start()] if edu else text

    # Step 2: find date ranges in work section
    seen, ranges = set(), []
    for m in _RANGE_RE.finditer(scan_text):
        s_raw, e_raw = m.group(1).strip(), m.group(2).strip()
        start = _parse_date(s_raw)
        end   = _parse_date(e_raw)
        if not start or not end or end < start:
            continue
        months = (end.year - start.year) * 12 + (end.month - start.month)
        if months <= 0 or months > 600:
            continue
        key = (start.year, start.month, end.year, end.month)
        if key in seen:
            continue
        seen.add(key)
        ranges.append({"label": f"{s_raw} \u2013 {e_raw}", "months": months})

    if ranges:
        total = sum(r["months"] for r in ranges)
        return {
            "total_years":  round(total / 12, 1),
            "total_months": total,
            "ranges_found": [r["label"] for r in ranges],
            "display":      _build_display(total),
        }

    # Step 3: "X+ years of experience" in summary text
    m = _SUMMARY_YEARS_RE.search(text)
    if m:
        yrs   = float(m.group(1))
        total = int(round(yrs * 12))
        return {
            "total_years":  yrs,
            "total_months": total,
            "ranges_found": [],
            "display":      _build_display(total),
        }

    # Step 4: LLM fallback — only triggered if Python found nothing
    return _extract_experience_llm_fallback(text)


def _extract_experience_llm_fallback(text: str) -> dict:
    """
    Last resort: ask LLM to find experience from summary or experience section.
    Only called when Python regex finds no dates and no 'X years' phrase.
    """
    _fallback = {
        "total_years": 0.0, "total_months": 0,
        "ranges_found": [], "display": "Not detected",
    }
    system = (
        "You are a resume parser. Return ONLY valid JSON. No markdown. No explanation."
    )
    prompt = f"""\
Read this resume and extract total professional work experience.
Look in the SUMMARY section for mentions like "X years of experience".
Look in the EXPERIENCE section for job date ranges.
IGNORE all education dates (degrees, universities, colleges).
"Present" or "Current" = May 2025.

Return ONLY this JSON:
{{
  "ranges_found": ["start - end", ...],
  "total_months": <integer>,
  "total_years": <float 1 decimal>,
  "display": "<e.g. 2 years 3 months>"
}}

If nothing found: {{"ranges_found": [], "total_months": 0, "total_years": 0.0, "display": "Not detected"}}

RESUME:
{text[:3000]}

JSON:"""
    try:
        resp = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            options={"temperature": 0, "num_predict": 250},
        )
        raw = resp["message"]["content"].strip()
        raw = re.sub(r"```(?:json)?|```", "", raw).strip()
        m   = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data         = json.loads(m.group(0))
            total_months = int(data.get("total_months", 0))
            display      = data.get("display") or _build_display(total_months)
            if total_months > 0 and display == "Not detected":
                display = _build_display(total_months)
            return {
                "total_years":  round(total_months / 12, 1),
                "total_months": total_months,
                "ranges_found": data.get("ranges_found", []),
                "display":      display,
            }
    except Exception as e:
        print(f"[skills] LLM experience fallback failed: {e}")
    return _fallback


# ═════════════════════════════════════════════════════════════════════════════
# PART 2 — SKILLS  (LLM)
# ═════════════════════════════════════════════════════════════════════════════

def _llm(system: str, user: str, num_predict: int = 500) -> str:
    resp = client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        options={"temperature": 0, "num_predict": num_predict},
    )
    return resp["message"]["content"].strip()


def _parse_skills(raw: str) -> list[str]:
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    try:
        items = json.loads(raw)
        seen, out = set(), []
        for s in items:
            if not isinstance(s, str) or not s.strip():
                continue
            k = s.lower().strip()
            if k not in seen:
                seen.add(k)
                out.append(k)
        return out
    except Exception as e:
        print(f"[skills] parse error: {e} | raw[:200]: {raw[:200]}")
        return []


def _expand_or(skills: list[str]) -> list[str]:
    """
    Split ONLY on ' or ' — NOT on '/'.
    'redux or context api' → ['redux', 'context api']
    'ci/cd' stays as 'ci/cd'
    'aws/azure' stays as 'aws/azure'
    """
    out = []
    for s in skills:
        for part in re.split(r"\s+or\s+", s, flags=re.IGNORECASE):
            part = part.strip()
            if part:
                out.append(part)
    return out



# ═════════════════════════════════════════════════════════════════════════════
# PART 3 — SEMANTIC SKILL MATCHING  (LLM-powered common sense)
# ═════════════════════════════════════════════════════════════════════════════
#
# No hardcoded alias table. The LLM decides if two skills mean the same thing.
# "gen ai" == "generative ai", "k8s" == "kubernetes", "ml" == "machine learning"
# — the LLM already knows all of this. We just ask it.
#
# Public function: match_skills_semantic(jd_skills, resume_skills)
#   → { "matched": [...], "missing": [...] }

_MATCH_SYS = (
    "You are a senior technical recruiter with expertise across ALL technology domains — "
    "web, mobile, AI/ML, DevOps, backend, frontend, data engineering, embedded, and more. "
    "Return ONLY valid JSON. No explanation, no markdown."
)

_MATCH_USR = """\
Decide which JD skills are covered by the candidate's resume skills.
Use your technical knowledge — the skill domain could be anything: Ruby, PHP, iOS, DevOps, AI, etc.

MATCHING LOGIC — a JD skill is MATCHED when ANY of these are true:
1. SAME THING, different spelling/casing/version suffix:
   e.g. "javascript" == "js", "postgresql" == "postgres", "kubernetes" == "k8s"
   e.g. "ruby on rails" == "rails", "react.js" == "react", "node.js" == "node"
2. ABBREVIATION of the full name (or vice versa):
   e.g. "ml" == "machine learning", "nlp" == "natural language processing"
   e.g. "oop" == "object oriented programming", "tdd" == "test driven development"
3. A SPECIFIC TOOL that belongs to the required skill category:
   e.g. JD says "version control"    → resume has "git"              → MATCHED
   e.g. JD says "relational database" → resume has "mysql/postgresql" → MATCHED
   e.g. JD says "cloud platform"     → resume has "aws/azure/gcp"    → MATCHED
   e.g. JD says "unit testing"       → resume has "rspec/jest/pytest" → MATCHED
4. A CAPABILITY demonstrated by a related tool or framework:
   e.g. JD says "rest apis"       → resume has fastapi/express/rails/laravel → MATCHED
   e.g. JD says "cms development" → resume has wordpress/drupal              → MATCHED
   e.g. JD says "orm"             → resume has activerecord/sqlalchemy       → MATCHED

A JD skill is MISSING only when the resume has NO evidence of that concept or capability whatsoever.

JD SKILLS (from job description):
{jd_skills}

RESUME SKILLS (what candidate has):
{resume_skills}

Return ONLY this JSON — every JD skill must appear in exactly one list:
{{
  "matched": ["jd skill that resume covers", ...],
  "missing": ["jd skill not found on resume", ...]
}}

JSON:"""


def match_skills_semantic(
    jd_skills: list[str],
    resume_skills: list[str],
) -> dict[str, list[str]]:
    """
    LLM-powered semantic skill matching.
    Returns { "matched": [...], "missing": [...] } using original JD skill names.
    Falls back to exact lowercase match if the LLM call fails.

    Usage:
        from app.skills import match_skills_semantic
        result  = match_skills_semantic(jd_skills, resume_skills)
        matched = result["matched"]
        missing = result["missing"]
    """
    if not jd_skills:
        return {"matched": [], "missing": []}

    # Fast path: exact lowercase match — no LLM needed for obvious hits
    resume_lower  = {s.lower().strip() for s in resume_skills}
    exact_matched = [s for s in jd_skills if s.lower().strip() in resume_lower]
    needs_llm     = [s for s in jd_skills if s.lower().strip() not in resume_lower]

    matched = list(exact_matched)
    missing = []

    if needs_llm:
        try:
            raw = _llm(
                _MATCH_SYS,
                _MATCH_USR.format(
                    jd_skills=json.dumps(needs_llm),
                    resume_skills=json.dumps(resume_skills),
                ),
                num_predict=400,
            )
            raw = re.sub(r"```(?:json)?|```", "", raw).strip()
            m   = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                data     = json.loads(m.group(0))
                matched += data.get("matched", [])
                missing  = data.get("missing", [])
            else:
                missing = needs_llm
        except Exception as e:
            print(f"[skills] semantic match failed: {e}")
            missing = needs_llm

    return {"matched": matched, "missing": missing}

# ── JD ────────────────────────────────────────────────────────────────────────

_JD_SYS = (
    "You are a technical skill extractor. "
    "Return ONLY a JSON array of skill strings. No explanation, no markdown."
)
_JD_USR = """\
From the JOB DESCRIPTION below extract only actual technical skills: \
languages, frameworks, libraries, tools, platforms, databases, methodologies.

Rules:
- SKILLS ONLY — not job duties, not soft skills, not task descriptions
- "Redux or Context API" → two items: "redux" and "context api"
- "Git and GitHub" → just "git"
- Keep compound skills intact: "ci/cd", "rest api", "react.js", "aws ec2"
- Lowercase everything
- Do NOT extract: "responsive web design", "frontend architecture",
  "api integration", "clean code", "reusable components" — these are tasks
- Do NOT invent skills not in the text
- Return ONLY a valid JSON array

JOB DESCRIPTION:
{text}

JSON array:"""


def extract_skills_ai(text: str) -> list[str]:
    text = text[:4000].strip()
    if not text:
        return []
    try:
        raw    = _llm(_JD_SYS, _JD_USR.format(text=text), num_predict=400)
        skills = _expand_or(_parse_skills(raw))
        seen, out = set(), []
        for s in skills:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out
    except Exception as e:
        print(f"[skills] JD error: {e}")
        return []


# ── Resume ────────────────────────────────────────────────────────────────────

_RES_SYS = (
    "You are a resume parser. "
    "Return ONLY a JSON array of technical skill strings. No explanation, no markdown."
)
_RES_USR = """\
From the RESUME below extract every technical skill the candidate knows.
Include: languages, frameworks, libraries, tools, platforms, databases, concepts.

Rules:
- Lowercase, short names: "react.js", "python", "docker", "ci/cd"
- Keep compound names intact: "ci/cd", "rest api", "node.js"
- Include skills from ALL sections: Summary, Skills, Experience, Projects
- Do NOT invent skills absent from the resume
- Return ONLY a valid JSON array

RESUME:
{resume_text}

JSON array:"""


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═════════════════════════════════════════════════════════════════════════════

def extract_resume_data_ai(resume_text: str) -> dict:
    """
    1 LLM call  → skills
    Python      → experience (with LLM fallback if Python finds nothing)
    """
    resume_text = resume_text[:5000].strip()
    if not resume_text:
        return {"skills": [], "experience": {
            "total_years": 0.0, "total_months": 0,
            "ranges_found": [], "display": "Not detected"}}

    skills = []
    try:
        raw    = _llm(_RES_SYS, _RES_USR.format(resume_text=resume_text), num_predict=500)
        skills = _parse_skills(raw)
        print(f"[skills] resume skills: {skills}")
    except Exception as e:
        print(f"[skills] skills failed: {e}")

    experience = _extract_experience_python(resume_text)
    print(f"[skills] experience: {experience}")

    return {"skills": skills, "experience": experience}