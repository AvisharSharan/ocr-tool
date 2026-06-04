from io import BytesIO
from pathlib import Path
import shutil
from typing import Any

import fitz
import numpy as np
from PIL import Image

from app.models import OcrBox, OcrPage, OcrResponse


def run_ocr(
    *,
    filename: str,
    content_type: str,
    data: bytes,
    preprocess: bool,
) -> OcrResponse:
    images = _load_images(filename, content_type, data)
    reader = _get_reader()

    pages: list[OcrPage] = []
    for index, image in enumerate(images, start=1):
        np_image = np.array(image.convert("RGB"))
        if preprocess:
            np_image = _preprocess_image(np_image)

        if reader["engine"] == "paddle":
            result = reader["client"].ocr(np_image, cls=True)
            boxes = _parse_paddle_result(result)
        else:
            boxes = _run_tesseract(np_image)
        page_text = "\n".join(box.text for box in boxes)
        pages.append(OcrPage(page=index, text=page_text, boxes=boxes))

    return OcrResponse(
        filename=filename,
        page_count=len(pages),
        text="\n\n".join(page.text for page in pages),
        pages=pages,
    )


def _get_reader() -> Any:
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        try:
            import pytesseract  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "No OCR engine is installed. Install PaddleOCR in Python 3.10-3.12 "
                "or install Tesseract plus pytesseract."
            ) from exc
        return {"engine": "tesseract", "client": None}
    except Exception:
        try:
            import pytesseract  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCR failed to load and pytesseract is not installed."
            ) from exc
        return {"engine": "tesseract", "client": None}

    try:
        return {"engine": "paddle", "client": PaddleOCR(use_angle_cls=True, lang="en", show_log=False)}
    except Exception as exc:
        raise RuntimeError(
            "PaddleOCR is installed but could not initialize. Check PaddlePaddle compatibility."
        ) from exc


def _load_images(filename: str, content_type: str, data: bytes) -> list[Image.Image]:
    suffix = Path(filename).suffix.lower()
    if content_type == "application/pdf" or suffix == ".pdf":
        return _pdf_to_images(data)

    try:
        image = Image.open(BytesIO(data))
        return [image.convert("RGB")]
    except Exception as exc:
        raise RuntimeError("Unsupported or unreadable file. Upload an image or PDF.") from exc


def _pdf_to_images(data: bytes) -> list[Image.Image]:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise RuntimeError("Could not read PDF.") from exc

    images: list[Image.Image] = []
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
        images.append(image)
    return images


def _preprocess_image(image: np.ndarray) -> np.ndarray:
    try:
        import cv2
    except ImportError:
        return image

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    normalized = cv2.normalize(denoised, None, 0, 255, cv2.NORM_MINMAX)
    return cv2.cvtColor(normalized, cv2.COLOR_GRAY2RGB)


def _parse_paddle_result(result: list[Any]) -> list[OcrBox]:
    boxes: list[OcrBox] = []
    for page_result in result or []:
        for line in page_result or []:
            if len(line) < 2:
                continue
            box, recognition = line
            text, confidence = recognition
            boxes.append(
                OcrBox(
                    text=str(text),
                    confidence=float(confidence),
                    box=[[float(x), float(y)] for x, y in box],
                )
            )
    return boxes


def _run_tesseract(image: np.ndarray) -> list[OcrBox]:
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("pytesseract is not installed.") from exc

    tesseract_cmd = _find_tesseract_binary()
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except Exception as exc:
        raise RuntimeError(
            "Tesseract OCR failed. Install the Tesseract binary and ensure it is on PATH."
        ) from exc

    boxes: list[OcrBox] = []
    for index, text in enumerate(data.get("text", [])):
        cleaned = str(text).strip()
        if not cleaned:
            continue
        confidence = _safe_confidence(data.get("conf", ["0"])[index])
        x = float(data.get("left", [0])[index])
        y = float(data.get("top", [0])[index])
        w = float(data.get("width", [0])[index])
        h = float(data.get("height", [0])[index])
        boxes.append(
            OcrBox(
                text=cleaned,
                confidence=confidence,
                box=[[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
            )
        )
    return boxes


def _safe_confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(parsed / 100.0, 1.0))


def _find_tesseract_binary() -> str | None:
    path_value = shutil.which("tesseract")
    if path_value:
        return path_value

    common_paths = [
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)
    return None
