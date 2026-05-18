# 🧠 AIResumeScreener

> AI-powered resume screener that runs **entirely on your machine** — no cloud API, no cost, no data leaving your system.
---

## What is AIResumeScreener?

AIResumeScreener takes a **job description** and a **candidate's resume** (PDF or DOCX), and instantly tells you:

- ✅ How well the candidate matches the role (0–100 score)
- 🎯 Which required skills they have and which they're missing
- 📅 Their total work experience
- 🤖 A 2-sentence AI recruiter summary

Everything runs locally using [Ollama](https://ollama.com) — your resume data never touches the internet.

---

## Features

| Feature 		  | Details 								|
|------------------------|----------------------------------------------------------------	|
| Resume parsing         | PDF and DOCX supported 						|
| Skill extraction 	  | LLM extracts skills from both JD and resume 			|
| Experience calculation | Regex scans date ranges (Jan 2020 – Present) 			|
| Semantic matching      | `nomic-embed-text` cosine similarity 				|
| Match score            | 0–100 (70% semantic + 30% skill coverage) 			|
| AI explanation         | 2-sentence recruiter summary 					|
| Speed 		  | Parallel async execution — JD + resume processed simultaneously 	|
| GPU auto-detect 	  | Picks `llama3` (GPU) or `phi3:mini` (CPU) automatically		|
| Privacy 		  | 100% local — no API keys, no data sent to cloud			|

---

## Demo

```
Input:  Job Description (text) + Resume (PDF/DOCX)
Output:
  {
    "match_score": 78.4,
    "matched_skills": ["python", "fastapi", "docker"],
    "missing_skills": ["kubernetes", "terraform"],
    "experience": {
      "display": "3 years 6 months"
    },
    "explanation": "The candidate demonstrates strong backend skills with 3+ years experience.
                    Key gaps in infrastructure tooling may require upskilling."
  }
```

---

## Local Setup

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) installed and running

### 1. Pull Ollama models

```bash
# Full quality (needs GPU or 8GB+ RAM)
ollama pull llama3
ollama pull nomic-embed-text

# Lightweight alternative (CPU / low RAM — ~4GB)
ollama pull phi3:mini
ollama pull nomic-embed-text
```

### 2. Clone and set up Python environment

```bash
git clone https://github.com/surajChauhan83/AIResumeScreener.git
cd AIResumeScreener

python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env if needed — defaults work out of the box with local Ollama
```

### 4. Run

```bash
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Docker Setup

```bash
docker-compose up --build

# Pull models into the container (first time only)
docker exec -it ollama ollama pull llama3
docker exec -it ollama ollama pull nomic-embed-text
```

---

## API Reference

### `POST /screen`

Screen a resume against a job description.

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

Returns the current model name and GPU status.

```json
{ "status": "ok", "model": "llama3", "gpu": true, "embed": "nomic-embed-text" }
```

---

## How It Works

### Why semantic embeddings over TF-IDF?

TF-IDF treats "ReactJS" and "React" as completely different terms. Embeddings capture **meaning** — so "Node.js backend" correctly matches "Express API development."

### Scoring formula

```
Final Score = (Semantic Similarity × 70%) + (Skill Coverage × 30%)
```

Skill coverage goes to 0 if no skills match at all — preventing a falsely inflated score from semantic similarity alone.

### Pipeline

```
Resume PDF/DOCX
      │
      ├── extract_experience()   ← regex only, no LLM, instant
      │
      └── extract_skills_ai()  ──┐
                                 │  PARALLEL (asyncio)
    JD text                      │
      │                          │
      └── extract_skills_ai()  ──┘
                │
                ▼
      _match_skills()
      3-stage: exact → substring → cosine similarity
                │
                ▼
      Whole-doc semantic similarity
      (embed_query × 2, parallel)
                │
                ▼
      Final score = 70% semantic + 30% skill coverage
                │
                ▼
      _generate_explanation()  ← 2-sentence LLM summary
```

### Speed optimisations

- JD and resume skill extraction run in **parallel threads**
- All skills batch-embedded in **2 calls** (not N×M)
- Experience extracted with **regex only** — no LLM needed
- `temperature=0` on skill extraction — faster, deterministic
- `num_predict` capped to avoid runaway generation

---

## Project Structure

```
AIResumeScreener/
├── app/
│   ├── main.py          # FastAPI entry point, /screen and /health routes
│   ├── config.py        # Env config, GPU auto-detect, model selection
│   ├── parser.py        # PDF + DOCX resume text extractor
│   ├── embeddings.py    # nomic-embed-text via LangChain
│   ├── skills.py        # LLM skill extraction + regex experience parser
│   └── matcher.py       # Core scoring pipeline (semantic + skill match)
├── static/
│   ├── app.js           # Frontend JS
│   └── style.css        # Styles
├── templates/
│   └── index.html       # Web UI
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Troubleshooting

| Problem                     | Fix                                                               |
|-----------------------------|-------------------------------------------------------------------|
| `ModuleNotFoundError`       | `source venv/bin/activate` then `pip install -r requirements.txt` |
| Connection refused `:11434` | Start Ollama: `ollama serve`                                      |
| Empty skills list           | Model not pulled yet: `ollama pull llama3`                        |
| Slow on CPU                 | Switch to `phi3:mini`: set `OLLAMA_MODEL=phi3:mini` in `.env`     |
| Scanned PDF returns no text | Use a text-based PDF — scanned images are not supported           |

---

## Tech Stack

- **Backend** — FastAPI, Python asyncio
- **LLM** — Ollama (`llama3` / `phi3:mini`)
- **Embeddings** — `nomic-embed-text` via LangChain
- **Similarity** — scikit-learn cosine similarity
- **Resume parsing** — pypdf, python-docx
- **Containerisation** — Docker + docker-compose

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---
