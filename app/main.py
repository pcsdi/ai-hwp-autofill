from __future__ import annotations
import shutil
import tempfile
import uuid
from pathlib import Path
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.services.document_reader import read_document
from app.services.matcher import build_matches
from app.services.hwpx_editor import apply_text_matches, insert_images_near_photo_labels

BASE = Path(__file__).resolve().parent
DATA = Path(tempfile.gettempdir()) / "ai_hwp_autofill"
DATA.mkdir(exist_ok=True)

app = FastAPI(title="AI 한글문서 자동작성기")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

SESSIONS: dict[str, dict] = {}

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/analyze")
async def analyze(document: UploadFile = File(...), content: str = Form(""), photos: list[UploadFile] = File(default=[])):
    sid = uuid.uuid4().hex
    sdir = DATA / sid
    sdir.mkdir(parents=True, exist_ok=True)
    doc_path = sdir / Path(document.filename or "document.hwpx").name
    with doc_path.open("wb") as f:
        shutil.copyfileobj(document.file, f)

    photo_paths = []
    for ph in photos:
        if ph.filename:
            pp = sdir / Path(ph.filename).name
            with pp.open("wb") as f:
                shutil.copyfileobj(ph.file, f)
            photo_paths.append(str(pp))

    parsed = read_document(str(doc_path))
    matches = build_matches(parsed.get("text", ""), parsed.get("tables", []), content)
    SESSIONS[sid] = {"doc": str(doc_path), "photos": photo_paths, "parsed": parsed, "matches": matches, "content": content}
    return {"session_id": sid, "document": parsed, "matches": matches, "photo_count": len(photo_paths),
            "notice": "HWP는 분석 중심, HWPX는 자동작성까지 지원합니다."}

@app.post("/api/generate/{session_id}")
async def generate(session_id: str, payload: dict):
    sess = SESSIONS.get(session_id)
    if not sess:
        return JSONResponse({"error": "세션을 찾을 수 없습니다."}, status_code=404)
    doc = Path(sess["doc"])
    if doc.suffix.lower() != ".hwpx":
        return JSONResponse({"error": "v1에서는 HWP 파일을 읽고 분석할 수 있지만 자동작성 출력은 HWPX가 필요합니다. 한글에서 HWPX로 저장 후 다시 올려주세요."}, status_code=400)
    matches = payload.get("matches") or sess["matches"]
    out = doc.with_name(doc.stem + "_completed.hwpx")
    report = apply_text_matches(str(doc), str(out), matches)
    photo_report = {"inserted": 0, "mode": "none"}
    if sess.get("photos"):
        photo_out = doc.with_name(doc.stem + "_completed_with_photos.hwpx")
        photo_report = insert_images_near_photo_labels(str(out), str(photo_out), sess["photos"])
        out = photo_out
    sess["out"] = str(out)
    return {"ok": True, "report": report, "photo_report": photo_report, "download_url": f"/api/download/{session_id}"}

@app.get("/api/download/{session_id}")
def download(session_id: str):
    sess = SESSIONS.get(session_id)
    if not sess or not sess.get("out"):
        return JSONResponse({"error": "생성된 파일이 없습니다."}, status_code=404)
    out = Path(sess["out"])
    return FileResponse(out, filename=out.name, media_type="application/octet-stream")
