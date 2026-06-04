from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.models import AiTextRequest, AskRequest, OcrResponse
from app.services.ai import (
    clean_text,
    detect_sensitive_info,
    extract_fields,
    summarize_text,
    answer_question,
)
from app.services.ocr import run_ocr

app = FastAPI(title="OCR Tool", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    with open("app/static/index.html", "r", encoding="utf-8") as html:
        return html.read()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ocr", response_model=OcrResponse)
async def ocr_endpoint(
    file: UploadFile = File(...),
    preprocess: bool = Form(default=True),
) -> OcrResponse:
    if not file.content_type:
        raise HTTPException(status_code=400, detail="Could not determine file type.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        return run_ocr(
            filename=file.filename or "upload",
            content_type=file.content_type,
            data=data,
            preprocess=preprocess,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/ai/clean")
def clean_endpoint(request: AiTextRequest) -> dict[str, str]:
    return {"text": clean_text(request.text)}


@app.post("/api/ai/summarize")
def summarize_endpoint(request: AiTextRequest) -> dict[str, str]:
    return {"summary": summarize_text(request.text)}


@app.post("/api/ai/extract")
def extract_endpoint(request: AiTextRequest) -> dict:
    return extract_fields(request.text)


@app.post("/api/ai/pii")
def pii_endpoint(request: AiTextRequest) -> dict:
    return detect_sensitive_info(request.text)


@app.post("/api/ai/ask")
def ask_endpoint(request: AskRequest) -> dict[str, str]:
    return {
        "answer": answer_question(
            request.text,
            request.question,
            [{"role": item.role, "content": item.content} for item in request.history],
        )
    }
