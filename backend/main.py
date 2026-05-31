import json
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .url_fetcher import read_url

from .config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
from .database import (
    init_db, save_analysis, update_match, get_analysis, get_all_analyses,
    delete_analysis, create_user, get_user_by_username, get_user_by_id,
)
from .parser import parse_resume
from .privacy import mask_resume
from .ai_service import analyze_resume, match_job, recommend_jobs
from .auth import hash_password, verify_password, create_token, verify_token

app = FastAPI(title="AI Resume Analyzer")

# Ensure DB is initialized immediately (belt and suspenders)
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent.parent / "static"


@app.on_event("startup")
def startup():
    init_db()


# ── Auth dependency ─────────────────────────────────────────────


def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    token = authorization.split(" ", 1)[1]
    user_id = verify_token(token)
    if user_id is None:
        raise HTTPException(401, "登录已过期，请重新登录")
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(401, "用户不存在")
    return user


# ── Pydantic models ─────────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    resume_text: str
    filename: str = "unknown"
    save: bool = True


class MatchRequest(BaseModel):
    resume_text: str
    job_text: str
    analysis_id: Optional[int] = None


class FetchJdRequest(BaseModel):
    url: str


class AuthRequest(BaseModel):
    username: str
    password: str


# ── Static files ────────────────────────────────────────────────


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Auth endpoints ──────────────────────────────────────────────


@app.post("/api/register")
def api_register(data: AuthRequest):
    username = data.username.strip()
    password = data.password.strip()

    if len(username) < 2 or len(username) > 30:
        raise HTTPException(400, "用户名需 2-30 个字符")
    if len(password) < 4:
        raise HTTPException(400, "密码至少 4 个字符")

    uid = create_user(username, hash_password(password))
    if uid is None:
        raise HTTPException(400, "用户名已被占用")

    token = create_token(uid)
    return {"token": token, "username": username}


@app.post("/api/login")
def api_login(data: AuthRequest):
    user = get_user_by_username(data.username.strip())
    if user is None or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")

    token = create_token(user["id"])
    return {"token": token, "username": user["username"]}


@app.get("/api/me")
def api_me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "username": user["username"]}


# ── Protected API endpoints ─────────────────────────────────────


@app.post("/api/parse")
async def api_parse(file: UploadFile = File(...), user=Depends(get_current_user)):
    ext = Path(file.filename or "unknown").suffix.lower()
    if ext not in (".pdf", ".docx", ".doc"):
        raise HTTPException(400, f"不支持的文件类型: {ext}")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        raw_text = parse_resume(tmp_path)
        text = mask_resume(raw_text)
        return {
            "filename": file.filename,
            "text": text,
            "char_count": len(text),
            "masked": True,
        }
    except Exception as e:
        raise HTTPException(500, f"解析失败: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/api/analyze")
async def api_analyze(data: AnalyzeRequest, user=Depends(get_current_user)):
    if not data.resume_text.strip():
        raise HTTPException(400, "简历文本为空")

    result = analyze_resume(data.resume_text)
    analysis_id = None

    if data.save and "error" not in result:
        analysis_id = save_analysis(
            user["id"], data.filename, data.resume_text,
            json.dumps(result, ensure_ascii=False),
        )

    return {"analysis_id": analysis_id, "result": result}


@app.post("/api/match")
async def api_match(data: MatchRequest, user=Depends(get_current_user)):
    if not data.resume_text.strip() or not data.job_text.strip():
        raise HTTPException(400, "简历文本或职位描述为空")

    result = match_job(data.resume_text, data.job_text)

    if data.analysis_id and "error" not in result:
        update_match(data.analysis_id, user["id"], data.job_text,
                     json.dumps(result, ensure_ascii=False))

    return {"result": result}


@app.get("/api/history")
def api_history(user=Depends(get_current_user)):
    return get_all_analyses(user["id"])


@app.get("/api/history/{analysis_id}")
def api_history_detail(analysis_id: int, user=Depends(get_current_user)):
    record = get_analysis(analysis_id, user["id"])
    if record is None:
        raise HTTPException(404, "记录不存在")
    return record


@app.delete("/api/history/{analysis_id}")
def api_history_delete(analysis_id: int, user=Depends(get_current_user)):
    if not delete_analysis(analysis_id, user["id"]):
        raise HTTPException(404, "记录不存在")
    return {"ok": True}


@app.post("/api/recommend-jobs")
async def api_recommend_jobs(data: AnalyzeRequest, user=Depends(get_current_user)):
    if not data.resume_text.strip():
        raise HTTPException(400, "简历文本为空")

    # First do quick analysis to get education info
    analysis = analyze_resume(data.resume_text)
    edu_analysis = analysis.get("education_analysis") if "error" not in analysis else None

    result = recommend_jobs(data.resume_text, edu_analysis)
    return {"result": result, "education_analysis": edu_analysis}


@app.post("/api/fetch-jd")
async def api_fetch_jd(data: FetchJdRequest):
    url = data.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(400, "请输入有效的网址")
    try:
        text = read_url(url)
        if not text or text.startswith("[错误]"):
            raise HTTPException(500, text or "抓取失败，网页无内容")
        return {"url": url, "text": text, "char_count": len(text)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"抓取失败: {e}")


@app.get("/api/health")
def api_health():
    has_key = bool(OPENAI_API_KEY and OPENAI_API_KEY != "your-api-key-here")
    key_preview = ""
    if has_key:
        k = OPENAI_API_KEY
        key_preview = k[:4] + "****" + k[-4:] if len(k) > 8 else "****"
    from .config import AI_PROVIDER, OLLAMA_AVAILABLE
    return {
        "status": "ok",
        "api_configured": has_key,
        "api_provider": AI_PROVIDER,
        "key_preview": key_preview,
        "model": OPENAI_MODEL,
        "base_url": OPENAI_BASE_URL,
        "ollama_available": OLLAMA_AVAILABLE,
    }
