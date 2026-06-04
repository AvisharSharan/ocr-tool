# OCR Tool

Python/FastAPI OCR app with PaddleOCR and a local Gemma model through Ollama.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull gemma3:1b
```

PaddleOCR may also require a compatible PaddlePaddle install for your machine. If OCR import fails, install the PaddlePaddle wheel recommended for your Python/CUDA/CPU setup.

Recommended OCR environment:

```text
Python 3.10-3.12 for PaddleOCR
Python 3.13 can run the FastAPI app, but will usually need Tesseract OCR as fallback.
```

For fallback OCR, install the Tesseract desktop binary and make sure `tesseract` is on your PATH.

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
- OCR text cleanup, summarization, field extraction, PII detection, and document Q&A using `gemma3:1b` via Ollama.
- JSON validation/retry for structured extraction.

## API

- `GET /health`
- `POST /api/ocr`
- `POST /api/ai/clean`
- `POST /api/ai/summarize`
- `POST /api/ai/extract`
- `POST /api/ai/pii`
- `POST /api/ai/ask`
