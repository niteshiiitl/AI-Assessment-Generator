AI Assessment Generator

A production-ready NLP pipeline that dynamically generates multi-lingual mock tests from complex PDF study materials.

📌 Overview
The AI Assessment Generator is a robust Flask-based REST API designed to automate the creation of multiple-choice questions (MCQs) for competitive exams (IBPS, SSC, UPSC, .. Etc). By leveraging the Groq LLM and a multi-tiered document parsing strategy, the system intelligently extracts context from user-uploaded PDFs and generates highly accurate, structured question sets in English, Hindi, and Hinglish.

Designed with production constraints in mind, this service includes automated OCR fallbacks for scanned documents, custom JSON-recovery algorithms for non-deterministic LLM outputs, and robust rate-limiting for safe public deployment.

✨ Core Features
Intelligent Document Parsing: Implements a dual-layer extraction pipeline using pypdf for digital text, with an automated fallback to pytesseract OCR for image-heavy or scanned PDFs.

Multi-Lingual Generation: Prompt-engineered to generate highly context-aware questions and explanations in English, Hindi, and Hinglish.

Contextual Reasoning: Specifically designed to handle grouped reasoning questions (e.g., seating arrangements, data tables) by aggressively preserving shared directions across linked MCQs.

LLM Output Salvaging: Features custom regex and truncation-recovery algorithms to gracefully handle and repair malformed JSON responses from the LLM, ensuring high API reliability.

Production Safeguards: Includes IP-based rate limiting, dynamic payload constraints, file-size bounding, and strict CORS configuration.

🛠️ Tech Stack
Backend Framework: Python, Flask, Gunicorn

AI & LLM: Groq API (Llama 3 / Mixtral models), Advanced Prompt Engineering

Document Processing: PyPDF2, pypdf, pdf2image, Tesseract OCR, Pillow

Infrastructure: AWS (EC2), Nginx

⚙️ Technical Architecture
Ingestion: User uploads a PDF via the /generate endpoint. The system verifies file integrity, size limits, and rate limits.

Extraction: The pdf_extractor evaluates the document's digital text density. If sufficient, it processes the text layer. If sparse (indicating a scanned document), it seamlessly routes the file through a high-DPI image conversion and Tesseract OCR pipeline.

Prompt Construction: The extracted text is cleaned, normalized, and bound to localized system prompts containing strict JSON-schema instructions and pedagogical rules.

Generation & Recovery: The payload is sent to the Groq API. The response undergoes rigorous JSON validation. If the LLM hallucinates markdown or breaks the schema, a multi-step recovery function rebuilds the payload into valid JSON.

Delivery: The validated questions, along with metadata (topic, difficulty mix, extraction method), are returned to the client application.

Note: This repository contains the backend API service. The frontend integration is currently live and actively serving users in a production environment.
