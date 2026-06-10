
"""flask backend file """

import os
import uuid
import logging
import time
from collections import defaultdict
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

from config import (
    UPLOAD_FOLDER, ALLOWED_EXTENSIONS, SECRET_KEY,
    MAX_PDF_SIZE_MB, MAX_TEXT_CHARS, RATE_LIMIT_PER_HOUR,
    DEFAULT_QUESTION_COUNT, MAX_QUESTION_COUNT, MIN_QUESTION_COUNT,
    SUPPORTED_LANGUAGES,
)
from pdf_extractor import extract_text_from_pdf, clean_text
from question_generator import generate_mock_test


app = Flask(__name__)
app.secret_key = SECRET_KEY


CORS(app, origins=[
    "https://360result.com",
    "https://www.360result.com",
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:5000",
])

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


_rate_store: dict[str, list] = defaultdict(list)

def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    window = 3600  
  
    _rate_store[ip] = [t for t in _rate_store[ip] if now - t < window]
    if len(_rate_store[ip]) >= RATE_LIMIT_PER_HOUR:
        return True
    _rate_store[ip].append(now)
    return False


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_clie() -> str:
    
    return (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.remote_addr
        or "unknown"
    )



@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "360result Mock Test API"})


@app.route("/generate", methods=["POST"])
def generate():
    """
    Main endpoint: Upload PDF → Get MCQ questions.

    Form fields:
        file        (required) PDF file
        language    (optional) hindi | english | hinglish  (default: english)
        count       (optional) 5–50                        (default: 20)
    """
    ip = _get_client_ip()


    if _is_rate_limited(ip):
        return jsonify({
            "success": False,
            "error": "Too many requests. Please wait an hour before trying again.",
        }), 429


    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected."}), 400

    if not _allowed_file(file.filename):
        return jsonify({"success": False, "error": "Only PDF files are accepted."}), 400


    file.seek(0, 2)  # seek to end
    size_bytes = file.tell()
    file.seek(0)
    if size_bytes > MAX_PDF_SIZE_MB * 1024 * 1024:
        return jsonify({
            "success": False,
            "error": f"PDF too large. Maximum allowed size is {MAX_PDF_SIZE_MB} MB.",
        }), 400


    language = request.form.get("language", "english").lower().strip()
    if language not in SUPPORTED_LANGUAGES:
        language = "english"

    try:
        count = int(request.form.get("count", DEFAULT_QUESTION_COUNT))
        count = max(MIN_QUESTION_COUNT, min(MAX_QUESTION_COUNT, count))
    except (ValueError, TypeError):
        count = DEFAULT_QUESTION_COUNT


    unique_name = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    file_path   = os.path.join(UPLOAD_FOLDER, unique_name)
    try:
        file.save(file_path)

     
        extraction = extract_text_from_pdf(file_path)

        if not extraction["success"]:
            return jsonify({
                "success": False,
                "error": extraction["error"] or "Failed to read PDF.",
            }), 422

        raw_text   = extraction["text"]
        clean      = clean_text(raw_text, max_chars=MAX_TEXT_CHARS)
        method     = extraction["method"]
        pages      = extraction["pages"]

        logger.info(f"[Generate] IP={ip} lang={language} count={count} pages={pages} method={method}")

   
        result = generate_mock_test(clean, language=language, count=count)

        if result["success"]:
            result["pdf_pages"]  = pages
            result["pdf_method"] = method  # digital | ocr | mixed
            return jsonify(result), 200
        else:
            return jsonify(result), 422

    finally:

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass


@app.errorhandler(413)
def too_large(e):
    return jsonify({"success": False, "error": "File too large."}), 413


@app.errorhandler(500)
def server_error(e):
    logger.error(f"500 error: {e}")
    return jsonify({"success": False, "error": "Internal server error."}), 500


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    logger.info(f"[360result] Mock Test API starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
