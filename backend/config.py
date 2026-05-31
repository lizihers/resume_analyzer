import os
import subprocess
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ── API Provider Selection ──────────────────────────────────────────
# Priority: env var > auto-detect Ollama > DeepSeek default

_provider = os.getenv("AI_PROVIDER", "auto").lower()

def _detect_ollama() -> bool:
    """Check if Ollama is installed and running."""
    if shutil.which("ollama") is None:
        return False
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        urllib.request.urlopen(req, timeout=3)
        return True
    except Exception:
        return False

OLLAMA_AVAILABLE = _detect_ollama()

if _provider == "ollama" or (_provider == "auto" and OLLAMA_AVAILABLE):
    # ── Ollama (Free, Local) ─────────────────────────────────────
    OPENAI_API_KEY = "ollama"  # required by SDK but not validated
    OPENAI_BASE_URL = "http://localhost:11434/v1"
    OPENAI_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    AI_PROVIDER = "ollama"
elif _provider == "siliconflow":
    # ── 硅基流动 (Free tier available) ────────────────────────────
    OPENAI_API_KEY = os.getenv("SF_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    OPENAI_BASE_URL = "https://api.siliconflow.cn/v1"
    OPENAI_MODEL = os.getenv("SF_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    AI_PROVIDER = "siliconflow"
else:
    # ── DeepSeek (Paid, cheap ~¥1/M tokens) ──────────────────────
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
    AI_PROVIDER = "deepseek"

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
