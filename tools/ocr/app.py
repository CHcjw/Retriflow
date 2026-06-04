from io import BytesIO

import pytesseract
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError


app = FastAPI(title="RetriFlow OCR Service", version="0.2.0")

IMAGE_CAPTION_PREFIXES = ("图", "表", "figure", "fig.", "image")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ocr/captions")
async def extract_captions(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    content_type = (file.content_type or "").lower()
    pages = _extract_pages_from_payload(content=content, content_type=content_type)

    results: list[dict] = []
    for page_number, image in pages:
        text = pytesseract.image_to_string(
            image,
            lang="eng+chi_sim",
            config="--oem 3 --psm 6",
            timeout=20,
        )
        captions = _extract_caption_candidates(text)
        if captions:
            results.append({"page_number": page_number, "captions": captions})

    return {"pages": results}


def _extract_pages_from_payload(content: bytes, content_type: str) -> list[tuple[int, Image.Image]]:
    if content_type.startswith("image/"):
        return [(1, _load_image_payload(content))]
    if content_type == "application/pdf":
        return _extract_pdf_page_images(content)
    return []


def _load_image_payload(content: bytes) -> Image.Image:
    try:
        image = Image.open(BytesIO(content))
        image.load()
        return image
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Unsupported image payload for OCR service.") from exc


def _extract_pdf_page_images(content: bytes) -> list[tuple[int, Image.Image]]:
    try:
        import pypdfium2 as pdfium
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail="PDF OCR support requires pypdfium2.") from exc

    try:
        document = pdfium.PdfDocument(content)
    except Exception as exc:  # pragma: no cover - library-specific parse failures
        raise HTTPException(status_code=400, detail="Unsupported PDF payload for OCR service.") from exc

    pages: list[tuple[int, Image.Image]] = []
    try:
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=2, rev_byteorder=True)
            image = bitmap.to_pil()
            image.load()
            pages.append((index + 1, image))
            bitmap.close()
            page.close()
    finally:
        document.close()

    return pages


def _extract_caption_candidates(text: str) -> list[str]:
    results: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith(IMAGE_CAPTION_PREFIXES) or line.startswith(("图", "表")):
            results.append(line)
    return results
