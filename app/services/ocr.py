from io import BytesIO
from pathlib import Path
from typing import Any

import fitz
import numpy as np
from PIL import Image

from app.models import OcrBox, OcrPage, OcrResponse

_READER: Any | None = None
_MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "easyocr"


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

        try:
            result = reader.readtext(np_image, detail=1, paragraph=False)
            boxes = _parse_easyocr_result(result)
        except Exception as exc:
            raise RuntimeError(f"EasyOCR failed while reading page {index}: {exc}") from exc

        page_text = "\n".join(box.text for box in boxes)
        pages.append(OcrPage(page=index, text=page_text, boxes=boxes))

    return OcrResponse(
        filename=filename,
        page_count=len(pages),
        text="\n\n".join(page.text for page in pages),
        pages=pages,
    )


def _get_reader() -> Any:
    global _READER
    if _READER is not None:
        return _READER

    try:
        import easyocr
    except ImportError as exc:
        raise RuntimeError(
            "EasyOCR is not installed. Run `python -m pip install easyocr ninja --no-deps`."
        ) from exc

    try:
        _MODEL_DIR.mkdir(parents=True, exist_ok=True)
        _READER = easyocr.Reader(
            ["en"],
            gpu=False,
            model_storage_directory=str(_MODEL_DIR),
            user_network_directory=str(_MODEL_DIR),
            verbose=False,
        )
        return _READER
    except Exception as exc:
        raise RuntimeError(f"EasyOCR is installed but could not initialize: {exc}") from exc


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


def _parse_easyocr_result(result: list[Any]) -> list[OcrBox]:
    boxes: list[OcrBox] = []
    for item in result or []:
        if len(item) < 3:
            continue
        box, text, confidence = item
        boxes.append(
            OcrBox(
                text=str(text),
                confidence=float(confidence),
                box=[[float(x), float(y)] for x, y in _to_list(box)],
            )
        )
    return boxes


def _to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)
