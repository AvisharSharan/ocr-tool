import json
import re
from typing import Any

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:7b"
DIRECTIVE = (
    "Be concise and direct. Answer only what was asked. "
    "Do not add follow-up questions, recommendations, disclaimers, or extra commentary."
)


def ask_llm(prompt: str, *, temperature: float = 0.1) -> str:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=180,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not reach Ollama. Make sure Ollama is running and {MODEL} is pulled."
        ) from exc

    return response.json().get("response", "").strip()


def clean_text(text: str) -> str:
    prompt = f"""
{DIRECTIVE}

Clean this OCR text. Fix obvious OCR mistakes while preserving meaning, names,
numbers, dates, line breaks, and document structure.

Return only the cleaned text.

OCR text:
{text}
"""
    return ask_llm(prompt)


def summarize_text(text: str) -> str:
    prompt = f"""
{DIRECTIVE}

Summarize this OCR text in at most 5 short bullets. Include only important
dates, amounts, names, and action items present in the text.

OCR text:
{text}
"""
    return ask_llm(prompt)


def extract_fields(text: str) -> dict[str, Any]:
    schema = {
        "document_type": "",
        "date": "",
        "vendor_or_sender": "",
        "recipient": "",
        "invoice_or_reference_number": "",
        "total_amount": "",
        "currency": "",
        "emails": [],
        "phone_numbers": [],
        "addresses": [],
        "line_items": [],
        "summary": "",
    }
    prompt = f"""
{DIRECTIVE}

Extract structured fields from this OCR text.

Return only valid JSON. Do not wrap it in markdown.
Use this exact schema and keep missing values as empty strings or empty arrays:
{json.dumps(schema, indent=2)}

OCR text:
{text}
"""
    return _json_from_model(prompt, schema)


def detect_sensitive_info(text: str) -> dict[str, Any]:
    schema = {
        "people": [],
        "emails": [],
        "phone_numbers": [],
        "addresses": [],
        "government_ids": [],
        "bank_or_card_numbers": [],
        "medical_info": [],
        "recommended_redactions": [],
    }
    prompt = f"""
{DIRECTIVE}

Find sensitive information in this OCR text for redaction.

Return only valid JSON. Do not wrap it in markdown.
Use this exact schema:
{json.dumps(schema, indent=2)}

OCR text:
{text}
"""
    return _json_from_model(prompt, schema)


def answer_question(
    text: str, question: str, history: list[dict[str, str]] | None = None
) -> str:
    chat_context = _format_history(history or [])
    context = _relevant_context(text, question)
    prompt = f"""
{DIRECTIVE}

Answer the question using the document excerpts below.
OCR may contain broken lines, missing punctuation, or confused characters.
Use approximate matches when the meaning is clear.
Only say "Not found in the document." when no excerpt supports an answer.

Recent chat:
{chat_context}

Document excerpts:
{context}

Question:
{question}
"""
    return ask_llm(prompt)


def _json_from_model(prompt: str, fallback: dict[str, Any]) -> dict[str, Any]:
    for attempt in range(2):
        response = ask_llm(prompt if attempt == 0 else _repair_prompt(response))
        try:
            parsed = json.loads(_strip_json_noise(response))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {"error": "Model did not return valid JSON.", "raw": response, "fallback": fallback}


def _repair_prompt(response: str) -> str:
    return f"""
{DIRECTIVE}

Convert this into valid JSON only. No markdown, no explanation.

Text:
{response}
"""


def _strip_json_noise(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _format_history(history: list[dict[str, str]]) -> str:
    if not history:
        return "None"

    lines = []
    for item in history[-8:]:
        role = item.get("role", "user")
        content = item.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content[:800]}")
    return "\n".join(lines) if lines else "None"


def _relevant_context(text: str, question: str, *, max_chars: int = 7000) -> str:
    normalized = text.strip()
    if len(normalized) <= max_chars:
        return normalized

    chunks = _chunk_text(normalized)
    terms = _terms(question)
    if not terms:
        return normalized[:max_chars]

    scored = []
    for index, chunk in enumerate(chunks):
        chunk_terms = _terms(chunk)
        overlap = len(terms & chunk_terms)
        phrase_bonus = sum(1 for term in terms if term in chunk.lower())
        score = overlap * 3 + phrase_bonus
        if score:
            scored.append((score, index, chunk))

    if not scored:
        return normalized[:max_chars]

    selected = []
    total = 0
    for _, index, chunk in sorted(scored, key=lambda item: (-item[0], item[1])):
        expanded = _expand_chunk(chunks, index)
        if total + len(expanded) > max_chars and selected:
            continue
        selected.append(expanded)
        total += len(expanded)
        if total >= max_chars:
            break

    return "\n\n---\n\n".join(selected)[:max_chars]


def _chunk_text(text: str, *, chunk_size: int = 1200) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        if current and current_len + len(line) > chunk_size:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line) + 1

    if current:
        chunks.append("\n".join(current))
    return chunks or [text[:chunk_size]]


def _expand_chunk(chunks: list[str], index: int) -> str:
    start = max(0, index - 1)
    end = min(len(chunks), index + 2)
    return "\n".join(chunks[start:end])


def _terms(value: str) -> set[str]:
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
    }
    return {
        term
        for term in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9._/-]*", value.lower())
        if len(term) > 1 and term not in stop_words
    }
