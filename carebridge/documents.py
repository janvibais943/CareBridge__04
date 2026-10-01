"""Agent 1: Document Agent - load files, OCR scans, classify document type."""
import io
import re
from .models import Document
from .utils import parse_date

TYPE_RULES = [
    ("discharge_summary", r"discharge summary"),
    ("prescription", r"\bRx\b|prescription"),
    ("appointment_letter", r"appointment (slip|letter|confirmation)"),
    ("imaging_report", r"\b(MRI|CT|X-?RAY|ULTRASOUND)\b.*\breport\b"),
    ("specialist_report", r"fundus|retinopathy|ophthalmology report"),
    ("lab_report", r"lab(oratory)? report|reference range"),
    ("clinical_note", r"clinical note|progress note|consultation note"),
]
DATE_LINE = re.compile(r"^\s*(?:Date|Report Date)\s*:\s*(.+)$", re.I | re.M)


def classify(text: str) -> str:
    head = text[:400]
    for doc_type, pattern in TYPE_RULES:
        if re.search(pattern, head, re.I | re.S):
            return doc_type
    return "unknown"


def _pdf_pages(data: bytes) -> list:
    import fitz  # PyMuPDF
    pages = []
    with fitz.open(stream=data, filetype="pdf") as pdf:
        for page in pdf:
            text = page.get_text().strip()
            if not text:  # scanned page -> OCR (optional dependency)
                try:
                    import pytesseract
                    from PIL import Image
                    pix = page.get_pixmap(dpi=200)
                    text = pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes("png"))))
                except Exception:
                    text = ""
            pages.append(text)
    return pages


def load_document(name: str, data) -> Document:
    if isinstance(data, bytes) and name.lower().endswith(".pdf"):
        pages = _pdf_pages(data)
    else:
        text = data.decode("utf-8", "ignore") if isinstance(data, bytes) else data
        pages = [p for p in re.split(r"\f|^-{3,}\s*page break\s*-{3,}$", text, flags=re.M | re.I) if p.strip()] or [text]
    doc = Document(name=name, pages=pages)
    doc.doc_type = classify(doc.text)
    m = DATE_LINE.search(doc.text)
    doc.doc_date = parse_date(m.group(1)) if m else parse_date(name)
    return doc


def load_documents(files: dict) -> list:
    return [load_document(n, d) for n, d in files.items()]
