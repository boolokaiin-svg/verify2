"""
Property Verification Agent - Backend API (FastAPI)
Run locally:
    python app.py
Or on Render:
    uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
PROJECT_ROOT = str(Path(__file__).parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from verify_service import verify_property_document

app = FastAPI(title="Tamil Nadu Property Verification Agent", version="2.0")

# Ensure output directory exists
os.makedirs(os.path.join(PROJECT_ROOT, "output"), exist_ok=True)

@app.get("/")
async def index():
    """Identify the backend service and its integration endpoints."""
    return {
        "service": "property-verification-agent",
        "status": "ok",
        "verify_endpoint": "/api/verify",
        "docs": "/docs",
    }


@app.get("/health")
@app.get("/api/internal/readiness")
async def readiness():
    """Process readiness; external AI and portal services are not probed."""
    return {"status": "ok"}


@app.post("/api/verify")
async def verify_uploaded_document(
    file: UploadFile = File(...),
    manual_ec: Optional[UploadFile] = File(None),
    manual_patta: Optional[UploadFile] = File(None)
):
    """API endpoint to verify uploaded deed bytes."""
    try:
        file_bytes = await file.read()
        ec_bytes = await manual_ec.read() if manual_ec else None
        patta_bytes = await manual_patta.read() if manual_patta else None

        result = verify_property_document(
            document=file_bytes,
            filename=file.filename,
            manual_ec=ec_bytes,
            manual_patta=patta_bytes
        )
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/verify-sample")
async def verify_sample_deed():
    """One-click API endpoint to verify the included Kundrathur deed."""
    sample_filename = "Kundrathur Murugn Nagar Plot No-77, 78 Manikannan (1).pdf"
    sample_path = os.path.join(PROJECT_ROOT, sample_filename)

    if not os.path.exists(sample_path):
        raise HTTPException(status_code=404, detail="Sample deed file not found in repository.")

    try:
        with open(sample_path, "rb") as f:
            file_bytes = f.read()

        result = verify_property_document(
            document=file_bytes,
            filename=sample_filename
        )
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """Serves downloaded official EC PDFs from output folder."""
    clean_filename = os.path.basename(filename)
    file_path = os.path.join(PROJECT_ROOT, "output", clean_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested file not found in output folder.")

    return FileResponse(file_path, media_type="application/pdf", filename=clean_filename)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
