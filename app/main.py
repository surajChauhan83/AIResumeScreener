"""
main.py — FastAPI app entry point.
"""
import os
import shutil

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import HAS_GPU, OLLAMA_MODEL, EMBED_MODEL
from app.parser import load_resume
from app.matcher import calculate_match_async

app = FastAPI(title="Smart Resume Screening")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "..", "static")),
    name="static",
)
templates = Jinja2Templates(
    directory=os.path.join(BASE_DIR, "..", "templates")
)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
TEMP_DIR = os.path.join(BASE_DIR, "..", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "model":   OLLAMA_MODEL,
            "gpu":     HAS_GPU,
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "model": OLLAMA_MODEL, "gpu": HAS_GPU, "embed": EMBED_MODEL}


@app.post("/screen")
async def screen_resume(
    request: Request,
    jd:   str        = Form(...),
    file: UploadFile = File(...),
):
    # ── Validate ──────────────────────────────────────────────────────────────
    if not jd.strip():
        raise HTTPException(400, "Job description cannot be empty.")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Only PDF and DOCX files are supported. Got: {ext or 'unknown'}")

    # ── Save uploaded file ────────────────────────────────────────────────────
    safe_name = os.path.basename(file.filename)
    file_path = os.path.join(TEMP_DIR, safe_name)

    with open(file_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    # ── Parse + Match ─────────────────────────────────────────────────────────
    try:
        resume_text = load_resume(file_path)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Could not read resume: {e}")

    try:
        result = await calculate_match_async(jd, resume_text)
    except Exception as e:
        raise HTTPException(500, f"Matching failed: {e}")

    return JSONResponse(result)
