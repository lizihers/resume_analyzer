import sys
from pathlib import Path

sys.path.insert(0, str(Path.home()))
from read_anything import read_pdf, read_docx


def parse_resume(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return read_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return read_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
