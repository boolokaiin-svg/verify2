# Tamil Nadu Property Verification Agent (Backend REST API)

Autonomous AI & Government Portal Verification Engine for Tamil Nadu Land Documents (Sale Deeds, Settlement Deeds, Gift Deeds, and Patta).

---

## 🚀 Quick Start for Frontend & Integration Teams

### 1. Requirements
* Python 3.10+ (Recommended: Python 3.11)
* Active Internet connection (for TNREGINET citizen portal & OpenRouter AI)

### 2. Setup
```bash
# 1. Install dependencies (pure HTTP, zero Chromium - takes < 30 seconds)
pip install -r requirements.txt

# 2. Configure environment
# Copy the template to .env (if not already present):
cp .env.example .env
```

Ensure your `.env` has:
```env
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
TNREGINET_USERNAME=your_tnreginet_citizen_username
TNREGINET_PASSWORD=your_tnreginet_citizen_password
PORTAL_MODE=http
OCR_MAX_WORKERS=2
```

### 3. Launch Backend Server
```bash
python app.py
```
* Server starts on: **`http://localhost:8000`**
* API documentation: **`http://localhost:8000/docs`**
* Service metadata: **`http://localhost:8000/`**
* Readiness: **`http://localhost:8000/health`** or **`/api/internal/readiness`**
* This service has no application frontend. Your backend should send multipart uploads to `POST /api/verify` with the required `file` field.

---

## 📡 REST API Reference

The frontend team can consume these endpoints:

### 1. `POST /api/verify`
Upload a property document (PDF or image) to trigger autonomous bilingual OCR, TNREGINET login, captcha solving, EC download, and cross-verification.

* **URL**: `/api/verify`
* **Method**: `POST`
* **Content-Type**: `multipart/form-data`
* **Form Fields**:
  * `file`: *(File, Required)* The primary Sale Deed or Title Document (PDF, JPG, PNG).
  * `manual_ec`: *(File, Optional)* Pre-existing Encumbrance Certificate PDF (skips automated portal retrieval if provided).
  * `manual_patta`: *(File, Optional)* Pre-existing Patta/Chitta PDF.

#### Example Response (`200 OK`):
```json
{
  "success": true,
  "verdict": "WARNING",
  "confidence": "100%",
  "risk": "Low",
  "downloaded_files": {
    "ec": "output/ec_14899_2025.pdf"
  },
  "report": "======================================================================\nVERDICT: WARNING\nCONFIDENCE: 100%\nRISK: Low\nISSUES FOUND IN THIS DOCUMENT:\n  • The document contains inconsistent survey numbers across different pages.\n...\n======================================================================"
}
```

* Possible `verdict` values:
  * `"PASS"`: Clean title, all portal checks match, no discrepancies.
  * `"WARNING"`: Minor issues detected (e.g. sub-division survey numbers, missing Patta mutation) but no legal blockers.
  * `"FAIL"`: Critical mismatch (e.g. fraudulent registration, encumbrance lien found, owner name mismatch).

---

### 2. `POST /api/verify-sample`
Runs the complete autonomous verification on the included sample deed (`Kundrathur Murugn Nagar Plot No-77, 78 Manikannan (1).pdf`) without uploading a file.

* **URL**: `/api/verify-sample`
* **Method**: `POST`
* **Content-Type**: `application/json`
* **Response**: Same format as `/api/verify`.

---

### 3. `GET /api/download/{filename}`
Retrieves and downloads the official Encumbrance Certificate (EC) PDF retrieved from the TNREGINET portal.

* **URL**: `/api/download/{filename}`
* **Method**: `GET`
* **Example**: `http://localhost:8000/api/download/ec_14899_2025.pdf`
* **Response**: Binary PDF file (`application/pdf`).

---

## 🐍 Python Programmatic Usage (Direct Integration)

If calling directly from another Python backend:

```python
from verify_service import verify_property_document

# Verify from file path
result = verify_property_document("path/to/sale_deed.pdf")

# Or verify from raw in-memory bytes
result = verify_property_document(
    document=file_bytes,
    filename="deed.pdf",
    manual_ec=optional_ec_bytes
)

print("Verdict:", result["verdict"])
print("Confidence:", result["confidence"])
print("Risk:", result["risk"])
print("Downloaded EC path:", result["downloaded_files"].get("ec"))
print(result["report"])
```

---

## 📁 Clean Project Structure

```text
property_verification_agent/
├── app.py                     # FastAPI backend REST API server
├── verify_service.py          # Clean high-level Python integration entry point
├── requirements.txt           # Minimal, lightweight dependencies (pure HTTP, no Chromium)
├── render.yaml                # 1-Click Render deployment configuration (512MB RAM optimized)
├── .env.example               # Sanitized environment variable template
├── .gitignore                 # Excludes .env, build files, caches, and outputs
├── Kundrathur Murugn Nagar... # Reference sample deed fixture (Doc 14899/2025 Kundrathur)
├── output/                    # Folder where retrieved official EC PDFs are saved
│   ├── .gitkeep
│   └── ec_14899_2025.pdf      # Sample verified official Encumbrance Certificate
└── src/                       # Modular verification engine
    ├── main.py                # PropertyVerificationAgent pipeline orchestrator
    ├── config.py              # Dynamic configuration & API client management
    ├── models.py              # Pydantic data schemas
    ├── intake.py              # File validation, MIME checks & PyMuPDF page rendering
    ├── ocr_extractor.py       # Parallel Gemini 3.1 Flash-Lite bilingual OCR
    ├── normalizer.py          # Field normalization & Tamil/English standardization
    ├── portal_verifier.py     # Zero-browser direct citizen HTTP session & captcha solver
    ├── completeness_engine.py # Completeness validation & document rules
    ├── deterministic_guard.py # Strict cross-verification between deed & portal EC
    ├── scoring.py             # Risk and confidence calculation engine
    └── report_generator.py    # Final legal report generation & token cost calculation
```

---

## ☁️ Cloud Deployment (Render 512MB Free / Starter Tier)

This engine is engineered specifically for low-memory cloud hosts (under **180MB peak RAM**):
* **Zero Chromium / Zero Playwright**: Replaced with direct Python HTTP sessions (`requests.Session` + `cryptography` AES-128-CBC encryption).
* **Memory Management**: Uses PyMuPDF streaming page cache shrinking (`TOOLS.store_shrink`) and garbage collection to ensure memory never spikes.
* **Render Configuration**:
  * **Runtime**: Python 3.11
  * **Build Command**: `pip install -r requirements.txt`
  * **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
  * **Environment Variables**:
    * `PORTAL_MODE=http`
    * `OCR_MAX_WORKERS=2`
    * `OPENROUTER_API_KEY=...`
    * `TNREGINET_USERNAME=...`
    * `TNREGINET_PASSWORD=...`
