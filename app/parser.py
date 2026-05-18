"""
parser.py — Extract plain text from PDF or DOCX resumes.
"""
import os
from pathlib import Path


def load_resume(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        return _load_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return _load_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use PDF or DOCX.")


def _load_pdf(path: str) -> str:
    from langchain_community.document_loaders import PyPDFLoader
    loader = PyPDFLoader(path)
    docs = loader.load()
    text = "\n".join(d.page_content for d in docs).strip()
    if not text:
        raise ValueError("PDF has no extractable text. Use a non-scanned PDF.")
    return text


def _load_docx(path: str) -> str:
    try:
        import docx
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        raise ImportError("Install python-docx: pip install python-docx")
