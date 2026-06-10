#pdf extractor file 

import logging
import io
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> dict:
  
    result = {
        "text": "",
        "method": "digital",
        "pages": 0,
        "success": False,
        "error": None,
    }

    try:
        digital_text, page_count = _extract_digital(file_path)
        result["pages"] = page_count

        # If digital extraction got meaningful text (>50 chars per page on avg)
        if digital_text and len(digital_text.strip()) > page_count * 50:
            result["text"] = digital_text.strip()
            result["method"] = "digital"
            result["success"] = True
            logger.info(f"[PDF] Digital extraction: {len(digital_text)} chars, {page_count} pages")
            return result

        
        logger.info("[PDF] Digital text too short, trying OCR...")
        ocr_text, ocr_pages = _extract_ocr(file_path)

        if ocr_text:
            # Combine whatever digital text exists with OCR
            combined = (digital_text + "\n" + ocr_text).strip()
            result["text"]    = combined
            result["method"]  = "ocr" if not digital_text.strip() else "mixed"
            result["success"] = True
            logger.info(f"[PDF] OCR extraction: {len(ocr_text)} chars")
        elif digital_text:
            # OCR failed but we have some digital text — use it
            result["text"]    = digital_text.strip()
            result["method"]  = "digital"
            result["success"] = True
        else:
            result["error"]   = "Could not extract text. PDF may be image-only and Tesseract is not installed."

    except Exception as e:
        logger.error(f"[PDF] Extraction error: {e}")
        result["error"] = str(e)

    return result


def _extract_digital(file_path: str):

    text_parts = []
    page_count = 0


    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        page_count = len(reader.pages)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        return "\n".join(text_parts), page_count
    except ImportError:
        pass

    
    try:
        import PyPDF2
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            page_count = len(reader.pages)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts), page_count
    except Exception as e:
        logger.warning(f"[PDF] PyPDF2 failed: {e}")
        return "", 0


def _extract_ocr(file_path: str):
    """Convert PDF pages to images and run Tesseract OCR."""
    try:
        
        import pkgutil
        if not hasattr(pkgutil, 'find_loader'):
            import importlib.util
            pkgutil.find_loader = lambda name: importlib.util.find_spec(name)

        import pytesseract
        from pdf2image import convert_from_path
        from PIL import Image

        images = convert_from_path(file_path, dpi=150)
        text_parts = []

        for i, img in enumerate(images):
            try:
                text = pytesseract.image_to_string(img, lang="hin+eng")
            except Exception:
                text = pytesseract.image_to_string(img, lang="eng")
            if text.strip():
                text_parts.append(text.strip())

        return "\n".join(text_parts), len(images)

    except ImportError as e:
        logger.warning("[PDF] OCR not available: %s", e)
        return "", 0
    except Exception as e:
        logger.warning("[PDF] OCR failed: %s", e)
        return "", 0


def clean_text(text: str, max_chars: int = 12000) -> str:

    import re
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = text.strip()
    
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[content truncated]"
    return text
