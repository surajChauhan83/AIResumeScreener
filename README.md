# Smart Resume Screening System

AI-powered resume screener using local LLMs — no cloud API, no cost.

---

## What it does

| Feature                 | Details                                                         |
|-------------------------|-----------------------------------------------------------------|
| Resume parsing          | PDF and DOCX supported                                          |
| Skill extraction        | LLM extracts skills from both JD and resume                     |
| Experience calculation  | Regex scans date ranges (Jan 2020 – Present)                    |
| Semantic matching       | nomic-embed-text cosine similarity                              |
| Match score             | 0–100 (70% semantic + 30% skill coverage)                       |
| AI explanation          | 2-sentence recruiter summary                                    |
| Speed                   | Parallel async execution — JD + resume processed simultaneously |
| GPU auto-detect         | Picks llama3 (GPU) or phi3:mini (CPU) automatically             |

---

## Local Setup

### 1. Install Ollama

Download from https://ollama.com, then pull models:

```bash
# Full quality (needs GPU or 8GB+ RAM)
ollama pull llama3
ollama pull nomic-embed-text

# Lightweight (CPU / low RAM — ~4GB)
ollama pull phi3:mini
ollama pull nomic-embed-text
```

### 2. Python environment

```bash
cd smart-resume-screening
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env if needed (default works for local Ollama)
```

### 4. Run

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000

---

## Docker Setup

```bash
docker-compose up --build

# Pull models into the container (first time only)
docker exec -it ollama ollama pull llama3
docker exec -it ollama ollama pull nomic-embed-text
```

---

## API

### `POST /screen`

```
Content-Type: multipart/form-data

jd   : string  — job description text
file : file    — PDF or DOCX resume
```

**Response:**
```json
{
  "match_score": 78.4,
  "matched_skills": ["python", "fastapi", "docker"],
  "missing_skills": ["kubernetes", "terraform"],
  "experience": {
    "total_years": 3.5,
    "total_months": 42,
    "ranges_found": ["Jan 2021 – Present", "Jun 2019 – Dec 2020"],
    "display": "3 years 6 months"
  },
  "explanation": "The candidate demonstrates strong backend skills with 3+ years experience. Key gaps in infrastructure tooling may require upskilling."
}
```

### `GET /health`

Returns current model and GPU status.

---

## Approach

This system uses **semantic embeddings** over TF-IDF because:
- TF-IDF treats "ReactJS" and "React" as completely different
- Embeddings capture meaning — "Node.js backend" matches "Express API development"

### Pipeline

```
Resume PDF/DOCX
      │
      ├── extract_experience()   ← regex, instant, no LLM
      │
      └── extract_skills_ai()  ──┐
                                 │  PARALLEL (asyncio)
JD text                          │
      │                          │
      └── extract_skills_ai()  ──┘
                │
                ▼
      _match_skills()
      (batch embed → cosine matrix)
                │
                ▼
      Whole-doc similarity
      (embed_query × 2, parallel)
                │
                ▼
      Final score = 70% semantic + 30% skill coverage
                │
                ▼
      _generate_explanation()  ← constrained LLM prompt
```

### Speed optimisations
- JD and resume skill extraction run in **parallel threads**
- All skills batch-embedded in **2 calls** (not N×M)
- Experience extracted with **regex only** — no LLM
- `temperature=0` on skill extraction — faster, no retries needed
- `num_predict` capped to avoid runaway generation

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | `source venv/bin/activate` then `pip install -r requirements.txt` |
| Connection refused :11434 | Start Ollama: `ollama serve` |
| Empty skills list | Model not pulled yet: `ollama pull llama3` |
| Slow on CPU | Use `phi3:mini`: set `OLLAMA_MODEL=phi3:mini` in `.env` |
| Scanned PDF = no text | Use a text-based PDF, not a scan |
