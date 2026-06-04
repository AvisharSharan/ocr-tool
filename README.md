# OCR Tool

Python/FastAPI OCR app with EasyOCR and a local Qwen model through Ollama.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull qwen2.5:7b
```

This project uses EasyOCR. PaddleOCR and Tesseract are not used.

## Run

```powershell
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Features

- Upload images or PDFs for OCR.
- Optional image preprocessing.
- OCR text cleanup, summarization, field extraction, PII detection, and document Q&A using `qwen2.5:7b` via Ollama.
- JSON validation/retry for structured extraction.

## API

- `GET /health`
- `POST /api/ocr`
- `POST /api/ai/clean`
- `POST /api/ai/summarize`
- `POST /api/ai/extract`
- `POST /api/ai/pii`
- `POST /api/ai/ask`
