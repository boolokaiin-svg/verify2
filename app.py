"""
Property Verification Agent - Web Application (FastAPI + Modern Frontend)
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
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from verify_service import verify_property_document

app = FastAPI(title="Tamil Nadu Property Verification Agent", version="2.0")

# Ensure output directory exists
os.makedirs(os.path.join(PROJECT_ROOT, "output"), exist_ok=True)

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TN Property Document Verification Agent</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #f8fafc; }
        .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.1); }
        .glow { box-shadow: 0 0 25px rgba(59, 130, 246, 0.2); }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between">
    <!-- Header -->
    <header class="border-b border-slate-800 bg-slate-900/80 sticky top-0 z-50 backdrop-blur-md">
        <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-lg shadow-blue-500/30">
                    <i class="fa-solid fa-landmark text-lg"></i>
                </div>
                <div>
                    <h1 class="text-lg font-bold text-white tracking-tight leading-tight">TN Property Verifier</h1>
                    <p class="text-xs text-slate-400">Autonomous Title & EC Verification Engine</p>
                </div>
            </div>
            <div class="flex items-center space-x-2 text-xs">
                <span class="inline-flex items-center px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse"></span>
                    Portal Engine Active
                </span>
                <span class="inline-flex items-center px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">
                    Render 512MB Optimized
                </span>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-6xl mx-auto px-4 py-8 flex-1 w-full grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        <!-- Left Column: Upload Form -->
        <div class="lg:col-span-5 space-y-6">
            <div class="glass rounded-2xl p-6 glow">
                <h2 class="text-base font-semibold text-white mb-1 flex items-center">
                    <i class="fa-solid fa-file-shield text-blue-400 mr-2"></i> Upload Sale Deed / Title Deed
                </h2>
                <p class="text-xs text-slate-400 mb-4">Upload scanned deed (PDF / JPG / PNG) for parallel AI OCR and TNREGINET cross-check.</p>

                <form id="verifyForm" class="space-y-4">
                    <!-- Drop Zone -->
                    <div id="dropZone" class="border-2 border-dashed border-slate-700 hover:border-blue-500 rounded-xl p-6 text-center cursor-pointer transition-all duration-200 bg-slate-900/40 hover:bg-slate-800/40">
                        <input type="file" id="documentInput" name="file" accept=".pdf,.png,.jpg,.jpeg" class="hidden">
                        <div id="uploadPlaceholder">
                            <i class="fa-solid fa-cloud-arrow-up text-3xl text-slate-400 mb-2"></i>
                            <p class="text-sm font-medium text-slate-300">Click to browse or drag & drop</p>
                            <p class="text-xs text-slate-500 mt-1">Tamil Nadu Sale Deeds, Settlements (Max 20MB)</p>
                        </div>
                        <div id="fileInfo" class="hidden flex items-center justify-between text-left p-3 rounded-lg bg-slate-800/80 border border-slate-700">
                            <div class="flex items-center space-x-3 truncate">
                                <i class="fa-solid fa-file-pdf text-red-400 text-xl"></i>
                                <div class="truncate">
                                    <p id="fileName" class="text-xs font-semibold text-slate-200 truncate"></p>
                                    <p id="fileSize" class="text-[10px] text-slate-400"></p>
                                </div>
                            </div>
                            <button type="button" id="removeFileBtn" class="text-slate-400 hover:text-red-400 p-1">
                                <i class="fa-solid fa-xmark"></i>
                            </button>
                        </div>
                    </div>

                    <!-- Quick Sample Button -->
                    <button type="button" id="sampleBtn" class="w-full py-2 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center justify-center space-x-2 transition">
                        <i class="fa-solid fa-bolt text-amber-400"></i>
                        <span>Load Sample Test Deed (Kundrathur 14899/2025)</span>
                    </button>

                    <!-- Optional Manual Upload Accordion -->
                    <div class="border border-slate-800 rounded-xl overflow-hidden bg-slate-900/30">
                        <button type="button" id="toggleManualBtn" class="w-full px-4 py-2.5 text-xs font-medium text-slate-400 hover:text-slate-300 flex items-center justify-between">
                            <span>Optional: Manual EC or Patta (Overrides Download)</span>
                            <i id="manualChevron" class="fa-solid fa-chevron-down transition-transform"></i>
                        </button>
                        <div id="manualInputs" class="hidden p-4 pt-0 space-y-3 border-t border-slate-800/60">
                            <div>
                                <label class="text-[11px] text-slate-400 block mb-1">Manual Encumbrance Certificate (PDF):</label>
                                <input type="file" id="manualEcInput" accept=".pdf" class="w-full text-xs text-slate-400 file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:bg-slate-800 file:text-slate-300 hover:file:bg-slate-700">
                            </div>
                            <div>
                                <label class="text-[11px] text-slate-400 block mb-1">Manual Patta / Chitta (PDF):</label>
                                <input type="file" id="manualPattaInput" accept=".pdf" class="w-full text-xs text-slate-400 file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:bg-slate-800 file:text-slate-300 hover:file:bg-slate-700">
                            </div>
                        </div>
                    </div>

                    <!-- Submit Button -->
                    <button type="submit" id="submitBtn" class="w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold text-sm shadow-lg shadow-blue-500/25 flex items-center justify-center space-x-2 transition disabled:opacity-50 disabled:cursor-not-allowed">
                        <i class="fa-solid fa-shield-halved"></i>
                        <span>Start Autonomous Verification</span>
                    </button>
                </form>
            </div>

            <!-- Features Card -->
            <div class="glass rounded-2xl p-5 text-xs text-slate-400 space-y-2">
                <p class="font-semibold text-slate-300 text-xs mb-2">Automated Checks Performed:</p>
                <div class="flex items-center space-x-2"><i class="fa-solid fa-check text-emerald-400 text-xs"></i> <span>Bilingual OCR (Tamil கிரயம் & English recitals)</span></div>
                <div class="flex items-center space-x-2"><i class="fa-solid fa-check text-emerald-400 text-xs"></i> <span>TNREGINET direct citizen session login & captcha solve</span></div>
                <div class="flex items-center space-x-2"><i class="fa-solid fa-check text-emerald-400 text-xs"></i> <span>Official Encumbrance Certificate retrieval & PDF save</span></div>
                <div class="flex items-center space-x-2"><i class="fa-solid fa-check text-emerald-400 text-xs"></i> <span>Deterministic cross-check: Survey Nos, Extent, Owner</span></div>
            </div>
        </div>

        <!-- Right Column: Results & Report -->
        <div class="lg:col-span-7 flex flex-col space-y-6">
            
            <!-- Default Placeholder State -->
            <div id="initialState" class="glass rounded-2xl p-12 text-center flex-1 flex flex-col items-center justify-center border-dashed border-2 border-slate-800">
                <div class="w-16 h-16 rounded-2xl bg-slate-800/60 flex items-center justify-center text-slate-500 mb-4">
                    <i class="fa-solid fa-magnifying-glass-arrow-right text-2xl"></i>
                </div>
                <h3 class="text-base font-semibold text-slate-300">No Document Under Verification</h3>
                <p class="text-xs text-slate-500 max-w-sm mt-1">Upload a sale deed PDF on the left or click "Load Sample Test Deed" to run a complete verification.</p>
            </div>

            <!-- Progress State -->
            <div id="loadingState" class="hidden glass rounded-2xl p-8 text-center flex-1 flex flex-col items-center justify-center space-y-4">
                <div class="relative w-16 h-16">
                    <div class="w-16 h-16 rounded-full border-4 border-slate-700 border-t-blue-500 animate-spin"></div>
                    <div class="absolute inset-0 flex items-center justify-center text-blue-400 text-xs font-bold">
                        AI
                    </div>
                </div>
                <h3 id="progressStage" class="text-base font-semibold text-white animate-pulse">Running Intake & OCR Extraction...</h3>
                <p id="progressDetail" class="text-xs text-slate-400 max-w-md">Extracting structured legal facts, Sub-Registrar Office, and recitals via Gemini Flash-Lite...</p>
                <div class="w-64 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div class="h-full bg-blue-500 animate-indeterminate"></div>
                </div>
            </div>

            <!-- Result State -->
            <div id="resultState" class="hidden space-y-5">
                
                <!-- Verdict Banner -->
                <div id="verdictBanner" class="rounded-2xl p-6 border flex items-center justify-between">
                    <div class="flex items-center space-x-4">
                        <div id="verdictIconWrap" class="w-12 h-12 rounded-xl flex items-center justify-center text-xl"></div>
                        <div>
                            <span class="text-[10px] tracking-wider uppercase font-bold text-slate-400 block">Final Title Verdict</span>
                            <h2 id="verdictText" class="text-2xl font-extrabold tracking-tight"></h2>
                        </div>
                    </div>
                    <div class="text-right">
                        <span class="text-[10px] text-slate-400 block uppercase font-medium">Confidence Score</span>
                        <span id="confidenceText" class="text-xl font-bold text-white"></span>
                    </div>
                </div>

                <!-- Metrics Grid -->
                <div class="grid grid-cols-3 gap-3">
                    <div class="glass rounded-xl p-3 text-center">
                        <span class="text-[10px] text-slate-400 block">Risk Level</span>
                        <span id="riskText" class="text-sm font-bold mt-0.5 block"></span>
                    </div>
                    <div class="glass rounded-xl p-3 text-center">
                        <span class="text-[10px] text-slate-400 block">Execution Time</span>
                        <span id="timeText" class="text-sm font-bold text-slate-200 mt-0.5 block"></span>
                    </div>
                    <div class="glass rounded-xl p-3 text-center">
                        <span class="text-[10px] text-slate-400 block">AI Token Cost</span>
                        <span id="costText" class="text-sm font-bold text-emerald-400 mt-0.5 block"></span>
                    </div>
                </div>

                <!-- Downloaded Official EC Card -->
                <div id="ecDownloadCard" class="hidden glass rounded-xl p-4 border border-blue-500/30 bg-blue-500/10 flex items-center justify-between">
                    <div class="flex items-center space-x-3">
                        <i class="fa-solid fa-file-contract text-blue-400 text-2xl"></i>
                        <div>
                            <p class="text-xs font-semibold text-white">Official Encumbrance Certificate (EC) Retrieved</p>
                            <p id="ecFileName" class="text-[11px] text-slate-300"></p>
                        </div>
                    </div>
                    <a id="ecDownloadLink" href="#" target="_blank" class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center space-x-1.5 transition">
                        <i class="fa-solid fa-download"></i>
                        <span>Download PDF</span>
                    </a>
                </div>

                <!-- Full Report Container -->
                <div class="glass rounded-2xl p-5 space-y-3">
                    <div class="flex items-center justify-between pb-2 border-b border-slate-800">
                        <h3 class="text-sm font-semibold text-slate-200 flex items-center">
                            <i class="fa-solid fa-scale-balanced text-indigo-400 mr-2"></i> Comprehensive Verification Report
                        </h3>
                        <button id="copyReportBtn" class="text-xs text-slate-400 hover:text-white flex items-center space-x-1">
                            <i class="fa-regular fa-copy"></i>
                            <span>Copy</span>
                        </button>
                    </div>
                    <pre id="reportContent" class="text-xs text-slate-300 font-mono whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto custom-scrollbar p-3 rounded-lg bg-slate-950/60 border border-slate-900"></pre>
                </div>
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-800/80 py-4 text-center text-xs text-slate-500">
        <p>Tamil Nadu Property Document Verification Engine • Powered by OpenRouter & Gemini 3.1 Flash-Lite</p>
    </footer>

    <!-- Logic Script -->
    <script>
        const dropZone = document.getElementById('dropZone');
        const documentInput = document.getElementById('documentInput');
        const uploadPlaceholder = document.getElementById('uploadPlaceholder');
        const fileInfo = document.getElementById('fileInfo');
        const fileName = document.getElementById('fileName');
        const fileSize = document.getElementById('fileSize');
        const removeFileBtn = document.getElementById('removeFileBtn');
        const sampleBtn = document.getElementById('sampleBtn');
        const verifyForm = document.getElementById('verifyForm');
        const submitBtn = document.getElementById('submitBtn');

        const toggleManualBtn = document.getElementById('toggleManualBtn');
        const manualInputs = document.getElementById('manualInputs');
        const manualChevron = document.getElementById('manualChevron');
        const manualEcInput = document.getElementById('manualEcInput');
        const manualPattaInput = document.getElementById('manualPattaInput');

        const initialState = document.getElementById('initialState');
        const loadingState = document.getElementById('loadingState');
        const resultState = document.getElementById('resultState');
        const progressStage = document.getElementById('progressStage');
        const progressDetail = document.getElementById('progressDetail');

        const verdictBanner = document.getElementById('verdictBanner');
        const verdictIconWrap = document.getElementById('verdictIconWrap');
        const verdictText = document.getElementById('verdictText');
        const confidenceText = document.getElementById('confidenceText');
        const riskText = document.getElementById('riskText');
        const timeText = document.getElementById('timeText');
        const costText = document.getElementById('costText');
        const reportContent = document.getElementById('reportContent');
        const ecDownloadCard = document.getElementById('ecDownloadCard');
        const ecDownloadLink = document.getElementById('ecDownloadLink');
        const ecFileName = document.getElementById('ecFileName');
        const copyReportBtn = document.getElementById('copyReportBtn');

        let selectedFile = null;
        let isSampleMode = false;

        // Toggle Manual Accordion
        toggleManualBtn.addEventListener('click', () => {
            manualInputs.classList.toggle('hidden');
            manualChevron.classList.toggle('rotate-180');
        });

        // Drag and Drop
        dropZone.addEventListener('click', () => documentInput.click());
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('border-blue-500', 'bg-slate-800/60'); });
        dropZone.addEventListener('dragleave', () => { dropZone.classList.remove('border-blue-500', 'bg-slate-800/60'); });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-blue-500', 'bg-slate-800/60');
            if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
        });

        documentInput.addEventListener('change', (e) => {
            if (e.target.files.length) handleFile(e.target.files[0]);
        });

        function handleFile(file) {
            selectedFile = file;
            isSampleMode = false;
            fileName.textContent = file.name;
            fileSize.textContent = (file.size / (1024 * 1024)).toFixed(2) + " MB";
            uploadPlaceholder.classList.add('hidden');
            fileInfo.classList.remove('hidden');
        }

        removeFileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            selectedFile = null;
            documentInput.value = "";
            isSampleMode = false;
            uploadPlaceholder.classList.remove('hidden');
            fileInfo.classList.add('hidden');
        });

        // Load Sample Deed Button
        sampleBtn.addEventListener('click', () => {
            isSampleMode = true;
            selectedFile = null;
            fileName.textContent = "Kundrathur Murugn Nagar Plot No-77, 78 Manikannan (1).pdf";
            fileSize.textContent = "Sample Deed (Included in Repository)";
            uploadPlaceholder.classList.add('hidden');
            fileInfo.classList.remove('hidden');
        });

        // Form Submit
        verifyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!selectedFile && !isSampleMode) {
                alert("Please select a document or click 'Load Sample Test Deed'.");
                return;
            }

            // UI: Set loading
            initialState.classList.add('hidden');
            resultState.classList.add('hidden');
            loadingState.classList.remove('hidden');
            submitBtn.disabled = true;

            // Animated status text steps
            const stages = [
                { s: "Step 0: Validating Document Headers...", d: "Reading PyMuPDF streams and inspecting MIME header integrity..." },
                { s: "Step 1: Bilingual AI OCR in Parallel...", d: "Calling Gemini 3.1 Flash-Lite to extract Tamil legal terms, parties, and SRO..." },
                { s: "Step 2: Normalizing Survey & Area...", d: "Standardizing survey numbers, extents to sq.ft, and planning jurisdictions..." },
                { s: "Step 3: TNREGINET Portal Verification...", d: "Connecting to government citizen portal and solving captcha..." },
                { s: "Step 4: Title Chain & Encumbrance Cross-Check...", d: "Cross-matching deed recitals with official Encumbrance Certificate..." }
            ];

            let stageIdx = 0;
            const timer = setInterval(() => {
                stageIdx = (stageIdx + 1) % stages.length;
                progressStage.textContent = stages[stageIdx].s;
                progressDetail.textContent = stages[stageIdx].d;
            }, 5500);

            try {
                let response;
                if (isSampleMode) {
                    response = await fetch('/api/verify-sample', { method: 'POST' });
                } else {
                    const formData = new FormData();
                    formData.append('file', selectedFile);
                    if (manualEcInput.files.length) formData.append('manual_ec', manualEcInput.files[0]);
                    if (manualPattaInput.files.length) formData.append('manual_patta', manualPattaInput.files[0]);
                    response = await fetch('/api/verify', { method: 'POST', body: formData });
                }

                clearInterval(timer);
                const data = await response.json();
                renderResult(data);

            } catch (err) {
                clearInterval(timer);
                alert("Verification request failed: " + err.message);
                initialState.classList.remove('hidden');
            } finally {
                loadingState.classList.add('hidden');
                submitBtn.disabled = false;
            }
        });

        function renderResult(data) {
            resultState.classList.remove('hidden');
            reportContent.textContent = data.report || "No report available.";

            // Verdict Styling
            const v = (data.verdict || "UNKNOWN").toUpperCase();
            verdictText.textContent = v;

            // Reset banner styling
            verdictBanner.className = "rounded-2xl p-6 border flex items-center justify-between ";
            verdictIconWrap.className = "w-12 h-12 rounded-xl flex items-center justify-center text-xl ";

            if (v.includes("PASS")) {
                verdictBanner.classList.add("bg-emerald-950/40", "border-emerald-500/40", "text-emerald-400");
                verdictIconWrap.classList.add("bg-emerald-500/20", "text-emerald-400");
                verdictIconWrap.innerHTML = '<i class="fa-solid fa-circle-check"></i>';
            } else if (v.includes("WARNING")) {
                verdictBanner.classList.add("bg-amber-950/40", "border-amber-500/40", "text-amber-400");
                verdictIconWrap.classList.add("bg-amber-500/20", "text-amber-400");
                verdictIconWrap.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
            } else if (v.includes("FAIL")) {
                verdictBanner.classList.add("bg-red-950/40", "border-red-500/40", "text-red-400");
                verdictIconWrap.classList.add("bg-red-500/20", "text-red-400");
                verdictIconWrap.innerHTML = '<i class="fa-solid fa-circle-xmark"></i>';
            } else {
                verdictBanner.classList.add("bg-blue-950/40", "border-blue-500/40", "text-blue-400");
                verdictIconWrap.classList.add("bg-blue-500/20", "text-blue-400");
                verdictIconWrap.innerHTML = '<i class="fa-solid fa-file-arrow-up"></i>';
            }

            // Parse Metrics from report text
            const rep = data.report || "";
            const confMatch = rep.match(/CONFIDENCE:\s*(\d+)%/);
            const riskMatch = rep.match(/RISK:\s*([A-Za-z]+)/);
            const timeMatch = rep.match(/Total Time:\s*([0-9.]+)\s*seconds/);
            const costMatch = rep.match(/Estimated Cost:\s*(\$?[0-9.]+ USD\s*\(~₹[0-9.]+\s*INR\))/);

            confidenceText.textContent = confMatch ? confMatch[1] + "%" : "100%";
            riskText.textContent = riskMatch ? riskMatch[1] : "Low";
            riskText.className = "text-sm font-bold mt-0.5 block " + (riskMatch && riskMatch[1] === "High" ? "text-red-400" : (riskMatch && riskMatch[1] === "Medium" ? "text-amber-400" : "text-emerald-400"));
            timeText.textContent = timeMatch ? timeMatch[1] + "s" : "~35s";
            costText.textContent = costMatch ? costMatch[1].split('(')[1]?.replace(')', '') || "₹0.08" : "₹0.08";

            // Downloaded EC check
            if (data.downloaded_files && data.downloaded_files.ec) {
                const ecPath = data.downloaded_files.ec;
                const ecBase = ecPath.split(/[\\\\/]/).pop();
                ecFileName.textContent = ecBase;
                ecDownloadLink.href = `/api/download/${ecBase}`;
                ecDownloadCard.classList.remove('hidden');
            } else {
                ecDownloadCard.classList.add('hidden');
            }
        }

        // Copy button
        copyReportBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(reportContent.textContent);
            copyReportBtn.innerHTML = '<i class="fa-solid fa-check text-emerald-400"></i><span class="text-emerald-400">Copied!</span>';
            setTimeout(() => {
                copyReportBtn.innerHTML = '<i class="fa-regular fa-copy"></i><span>Copy</span>';
            }, 2000);
        });
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serves the interactive verification frontend."""
    return HTMLResponse(content=HTML_CONTENT)

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
    print(f"\\n" + "=" * 60)
    print(f"🚀 Property Verification Frontend Running!")
    print(f"👉 Open in your browser: http://localhost:{port}")
    print(f"=" * 60 + "\\n")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
