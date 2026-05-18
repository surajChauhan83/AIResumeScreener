"""
embeddings.py — nomic-embed-text via Ollama for semantic similarity.
"""
from langchain_ollama import OllamaEmbeddings
from app.config import OLLAMA_BASE, EMBED_MODEL

embeddings = OllamaEmbeddings(
    model=EMBED_MODEL,
    base_url=OLLAMA_BASE,
)
