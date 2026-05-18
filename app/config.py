"""
config.py — single source of truth for all settings.
Auto-detects GPU via nvidia-smi and picks the right model tier.
"""
import os
import subprocess


def _has_gpu() -> bool:
    try:
        subprocess.run(
            ["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
        return True
    except Exception:
        return False


OLLAMA_HOST  = os.getenv("OLLAMA_HOST",  "localhost")
OLLAMA_PORT  = os.getenv("OLLAMA_PORT",  "11434")
OLLAMA_BASE  = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"

# GPU → llama3  |  CPU → phi3:mini  (user can always override via env)
# _default_model = "llama3" if _has_gpu() else "phi3:mini"
_default_model = "llama3:latest"

OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", _default_model)

EMBED_MODEL  = os.getenv("EMBED_MODEL", "nomic-embed-text")

HAS_GPU = _has_gpu()
