"""
matcher.py — Core matching pipeline.
 
Score: 70% whole-doc semantic similarity + 30% skill coverage
Skill matching: 3-stage (exact norm → substring → embedding cosine sim)
"""
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
 
from sklearn.metrics.pairwise import cosine_similarity
 
from app.config import OLLAMA_MODEL
from app.embeddings import embeddings
from app.skills import extract_skills_ai, extract_resume_data_ai, client
 
_pool = ThreadPoolExecutor(max_workers=4)
 
_EXPLAIN_SYSTEM = (
    "You are a professional recruiter. "
    "Reply with exactly 2 short sentences only. "
    "No bullet points, no lists, no code blocks."
)
 
 
# ── normalisation ─────────────────────────────────────────────────────────────
 
def _norm(s: str) -> str:
    """Lowercase + strip punctuation/symbols for fair string comparison."""
    s = s.lower().strip()
    s = re.sub(r"[.\-_/]", " ", s)   # react.js → react js
    s = re.sub(r"\s+", " ", s)
    return s.strip()
 
 
# ── skill matching ────────────────────────────────────────────────────────────
 
def _keyword_match(jd_skill: str, resume_skills: list[str]) -> bool:
    """
    3-stage string match before falling back to embeddings.
    Stage 1: exact normalised string match
    Stage 2: substring  (react ⊂ react.js,  git ⊂ git and github)
    Stage 3: token overlap ≥ 60% of JD skill tokens
    """
    j     = _norm(jd_skill)
    j_tok = set(j.split())
 
    for rs in resume_skills:
        r     = _norm(rs)
        r_tok = set(r.split())
 
        if j == r:                              # stage 1: exact
            return True
        if j in r or r in j:                   # stage 2: substring
            return True
        overlap = j_tok & r_tok
        if overlap and len(overlap) / max(len(j_tok), 1) >= 0.6:   # stage 3: token
            return True
 
    return False
 
 
def _match_skills(
    jd_skills: list[str],
    resume_skills: list[str],
    threshold: float = 0.70,
) -> tuple[list[str], list[str]]:
    """
    For each JD skill:
      Try string match first (fast, handles react.js/reactjs/react js)
      Fall back to embedding cosine similarity (catches semantic synonyms)
    """
    if not jd_skills:
        return [], []
    if not resume_skills:
        return [], list(jd_skills)
 
    matched, to_embed = [], []
 
    for skill in jd_skills:
        if _keyword_match(skill, resume_skills):
            matched.append(skill)
        else:
            to_embed.append(skill)
 
    missing = []
    if to_embed:
        try:
            jd_vecs     = embeddings.embed_documents(to_embed)
            resume_vecs = embeddings.embed_documents(resume_skills)
            scores      = cosine_similarity(jd_vecs, resume_vecs)
            for i, skill in enumerate(to_embed):
                if scores[i].max() >= threshold:
                    matched.append(skill)
                else:
                    missing.append(skill)
        except Exception as e:
            print(f"[matcher] embedding error: {e}")
            missing.extend(to_embed)
 
    return matched, missing
 
 
# ── explanation ───────────────────────────────────────────────────────────────
 
def _generate_explanation(
    score: float,
    matched: list[str],
    missing: list[str],
    experience: str,
) -> str:
    prompt = (
        f"Candidate facts:\n"
        f"- Match score: {score:.1f}%\n"
        f"- Experience: {experience}\n"
        f"- Skills the candidate HAS: {', '.join(matched) or 'none'}\n"
        f"- Skills the candidate is MISSING: {', '.join(missing) or 'none'}\n\n"
        f"Write exactly 2 sentences summarising this candidate for the role."
    )
    try:
        resp = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": _EXPLAIN_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            options={"temperature": 0.1, "num_predict": 150},
        )
        raw   = resp["message"]["content"].strip().replace("\n", " ")
        parts = [s.strip() for s in raw.split(".") if s.strip()]
        return ". ".join(parts[:2]) + "."
    except Exception as e:
        print(f"[matcher] explanation error: {e}")
        m_str = ", ".join(matched[:5]) or "none"
        x_str = ", ".join(missing[:5]) or "none"
        return (
            f"The candidate scored {score:.1f}% with {len(matched)} matched skills "
            f"including {m_str}. Key gaps: {x_str}."
        )
 
 
# ── public API ────────────────────────────────────────────────────────────────
 
async def calculate_match_async(job_description: str, resume_text: str) -> dict:
    """
    Parallel pipeline:
      JD    → extract_skills_ai()       1 LLM call  (skills only)
      Resume → extract_resume_data_ai() 2 LLM calls (skills + experience)
      Both run in parallel.
    """
    loop = asyncio.get_event_loop()
 
    jd_future     = loop.run_in_executor(_pool, extract_skills_ai,      job_description)
    resume_future = loop.run_in_executor(_pool, extract_resume_data_ai, resume_text)
 
    jd_skills, resume_data = await asyncio.gather(jd_future, resume_future)
 
    resume_skills = resume_data["skills"]
    experience    = resume_data["experience"]
 
    print(f"[matcher] JD skills:     {jd_skills}")
    print(f"[matcher] Resume skills: {resume_skills}")
    print(f"[matcher] Experience:    {experience}")
 
    matched_skills, missing_skills = await loop.run_in_executor(
        _pool, _match_skills, jd_skills, resume_skills
    )
 
    print(f"[matcher] Matched: {matched_skills}")
    print(f"[matcher] Missing: {missing_skills}")
 
    jd_vec, resume_vec = await asyncio.gather(
        loop.run_in_executor(_pool, embeddings.embed_query, job_description),
        loop.run_in_executor(_pool, embeddings.embed_query, resume_text),
    )
    semantic_score = float(cosine_similarity([jd_vec], [resume_vec])[0][0]) * 100
 
    skill_score = (len(matched_skills) / max(len(jd_skills), 1)) * 100
 
    # If no skills matched at all → score must be 0, not inflated by semantic similarity
    if skill_score == 0:
        final_score = 0.0
    else:
        final_score = round(semantic_score * 0.7 + skill_score * 0.3, 1)
 
    # If experience was not detected, label candidate as "Fresher" instead of "Not detected"
    if experience.get("display") == "Not detected":
        experience["display"] = "Fresher"
 
    explanation = await loop.run_in_executor(
        _pool, _generate_explanation,
        final_score, matched_skills, missing_skills, experience["display"]
    )
 
    return {
        "match_score":    final_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "experience":     experience,
        "explanation":    explanation,
    }