"""Authenticated Boolok adapter. Run one worker: legacy engine uses relative paths."""
import os
import re
import secrets
import shutil
import threading
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
STORAGE = Path(os.getenv('VERIFICATION_STORAGE_DIR', str(ROOT / 'storage'))).resolve()
STORAGE.mkdir(parents=True, exist_ok=True)
LOCK = threading.Lock()
app = FastAPI(title='Boolok Property Verification', docs_url=None, redoc_url=None)


def authorize(authorization: str = Header(default='')):
    token = os.getenv('VERIFICATION_SERVICE_TOKEN', '').strip()
    if not token:
        raise HTTPException(503, 'Verification service token is not configured')
    if not secrets.compare_digest(authorization, f'Bearer {token}'):
        raise HTTPException(401, 'Invalid service credential')


def account(x_boolok_user_id: str = Header(default='')):
    if not re.fullmatch(r'[a-fA-F0-9]{24}', x_boolok_user_id):
        raise HTTPException(400, 'Valid Boolok user ID required')
    return x_boolok_user_id.lower()


def configured():
    return any(os.getenv(key, '').strip() for key in ('OPENROUTER_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY', 'OPENAI_API_KEY'))


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/api/internal/readiness', dependencies=[Depends(authorize)])
def readiness():
    if not configured():
        raise HTTPException(503, 'AI provider is not configured')
    from verify_service import PropertyVerificationAgent
    return {'ready': True}


async def read_upload(upload):
    if upload is None:
        return None
    data = await upload.read(20 * 1024 * 1024 + 1)
    if not data or len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, 'Each document must contain data and be at most 20 MB')
    if Path(upload.filename or '').suffix.lower() not in ('.pdf', '.png', '.jpg', '.jpeg'):
        raise HTTPException(400, 'Only PDF, JPG and PNG files are supported')
    return data


def process_document(user, payload, filename, ec, patta):
    from verify_service import verify_property_document
    work = STORAGE / user / uuid.uuid4().hex
    work.mkdir(parents=True)
    (work / 'output').mkdir()
    previous = Path.cwd()
    try:
        os.chdir(work)
        result = verify_property_document(payload, filename=Path(filename).name, manual_ec=ec, manual_patta=patta)
        files = {}
        for key, value in result.get('downloaded_files', {}).items():
            path = Path(value).resolve()
            if path.is_relative_to(work) and path.is_file() and path.suffix.lower() == '.pdf':
                name = f'{uuid.uuid4().hex}.pdf'
                shutil.move(str(path), str(STORAGE / user / name))
                files[key] = name
        result['downloaded_files'] = files
        return result
    finally:
        os.chdir(previous)
        shutil.rmtree(work)


@app.post('/api/verify', dependencies=[Depends(authorize)])
async def verify(document: UploadFile = File(default=None), file: UploadFile = File(default=None),
                 manual_ec: UploadFile = File(default=None), manual_patta: UploadFile = File(default=None),
                 user: str = Depends(account)):
    upload = document or file
    if upload is None:
        raise HTTPException(422, 'A document is required')
    if not configured():
        raise HTTPException(503, 'AI provider is not configured')
    if not LOCK.acquire(blocking=False):
        raise HTTPException(429, 'Verification is already running', headers={'Retry-After': '30'})
    try:
        payload = await read_upload(upload)
        ec = await read_upload(manual_ec)
        patta = await read_upload(manual_patta)
        return await run_in_threadpool(process_document, user, payload, upload.filename, ec, patta)
    finally:
        LOCK.release()


@app.get('/api/download-ec/{filename}', dependencies=[Depends(authorize)])
@app.get('/api/download/{filename}', dependencies=[Depends(authorize)])
def download(filename: str, user: str = Depends(account)):
    if not re.fullmatch(r'[a-f0-9]{32}\.pdf', filename):
        raise HTTPException(404, 'Certificate not found')
    path = STORAGE / user / filename
    if not path.is_file():
        raise HTTPException(404, 'Certificate not found')
    return FileResponse(path, filename=filename, media_type='application/pdf')


@app.post('/api/internal/delete-account/{user_id}', dependencies=[Depends(authorize)])
def delete_account(user_id: str):
    if not re.fullmatch(r'[a-fA-F0-9]{24}', user_id):
        raise HTTPException(400, 'Invalid user ID')
    if not LOCK.acquire(blocking=False):
        raise HTTPException(429, 'Verification is already running')
    try:
        folder = STORAGE / user_id.lower()
        if folder.exists():
            shutil.rmtree(folder)
        return {'success': True}
    finally:
        LOCK.release()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '8000')))
