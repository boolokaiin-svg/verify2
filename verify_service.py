"""Clean integration service for external backends (FastAPI, Flask, Django, etc.).

Usage from your backend:
    from verify_service import verify_property_document

    result = verify_property_document("path/to/sale_deed.pdf")
    # Or passing raw bytes:
    # result = verify_property_document(file_bytes, filename="deed.pdf")

    print(result["verdict"])           # e.g. "PASS", "WARNING", "FAIL"
    print(result["report"])            # Full legal report string
    print(result["downloaded_files"])  # e.g. {"ec": "output/ec_14899_2025.pdf"}
    print(result["metrics"])           # Execution time, tokens, cost
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Union, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = str(Path(__file__).parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)

from src.main import PropertyVerificationAgent

# Singleton instance for high efficiency across backend calls
_agent_instance = None

def get_agent() -> PropertyVerificationAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = PropertyVerificationAgent()
    return _agent_instance

def verify_property_document(
    document: Union[str, bytes],
    filename: str = None,
    manual_ec: Union[str, bytes] = None,
    manual_patta: Union[str, bytes] = None
) -> Dict[str, Any]:
    """
    Main backend entry point.

    Args:
        document: File path (str) OR raw file bytes of the Sale Deed (PDF/JPG/PNG).
        filename: Optional filename (required if document is bytes).
        manual_ec: Optional path or bytes of Encumbrance Certificate (bypasses portal download).
        manual_patta: Optional path or bytes of Patta (bypasses portal download).

    Returns:
        dict: {
            "success": bool,
            "verdict": str,             # "PASS", "WARNING", "FAIL", "NEEDS_MANUAL_UPLOAD", "ERROR"
            "report": str,              # Full formatted legal report
            "downloaded_files": dict,   # e.g. {"ec": "output/ec_14899_2025.pdf"}
            "error": str (if any)
        }
    """
    # 1. Resolve document bytes and filename
    if isinstance(document, str):
        if not os.path.exists(document):
            return {"success": False, "verdict": "ERROR", "error": f"File not found: {document}", "report": "", "downloaded_files": {}}
        filename = filename or os.path.basename(document)
        with open(document, "rb") as f:
            file_bytes = f.read()
    elif isinstance(document, bytes):
        file_bytes = document
        filename = filename or "uploaded_document.pdf"
    else:
        return {"success": False, "verdict": "ERROR", "error": "Invalid document input type", "report": "", "downloaded_files": {}}

    # 2. Resolve optional manual documents
    ec_bytes = None
    if manual_ec:
        if isinstance(manual_ec, str) and os.path.exists(manual_ec):
            with open(manual_ec, "rb") as f:
                ec_bytes = f.read()
        elif isinstance(manual_ec, bytes):
            ec_bytes = manual_ec

    patta_bytes = None
    if manual_patta:
        if isinstance(manual_patta, str) and os.path.exists(manual_patta):
            with open(manual_patta, "rb") as f:
                patta_bytes = f.read()
        elif isinstance(manual_patta, bytes):
            patta_bytes = manual_patta

    # 3. Execute Verification Engine
    agent = get_agent()
    agent.last_report = None
    try:
        report_text, downloaded_files = agent.process(
            file_bytes=file_bytes,
            filename=filename,
            manual_ec_bytes=ec_bytes,
            manual_patta_bytes=patta_bytes
        )

        # Extract verdict, confidence, and risk metadata
        verdict = "UNKNOWN"
        confidence = "100%"
        risk = "Low"
        for line in report_text.split("\n"):
            line_s = line.strip()
            if line_s.startswith("VERDICT:"):
                verdict = line_s.replace("VERDICT:", "").strip()
            elif line_s.startswith("CONFIDENCE:"):
                confidence = line_s.replace("CONFIDENCE:", "").strip()
            elif line_s.startswith("RISK:"):
                risk = line_s.replace("RISK:", "").strip()

        return {
            "success": verdict not in ("ERROR", "UNKNOWN"),
            "data": agent.last_report or {},
            "verdict": verdict,
            "confidence": confidence,
            "risk": risk,
            "report": report_text,
            "downloaded_files": downloaded_files
        }
    except Exception as e:
        return {
            "success": False,
            "verdict": "ERROR",
            "error": str(e),
            "report": f"Processing error: {str(e)}",
            "downloaded_files": {}
        }

if __name__ == "__main__":
    import sys
    default_test = "Kundrathur Murugn Nagar Plot No-77, 78 Manikannan (1).pdf" if os.path.exists("Kundrathur Murugn Nagar Plot No-77, 78 Manikannan (1).pdf") else "test_doc.pdf"
    test_file = sys.argv[1] if len(sys.argv) > 1 else default_test
    print(f"Testing verify_service on: {test_file}\n" + "=" * 60)
    res = verify_property_document(test_file)
    print("\n" + "=" * 60)
    print("VERIFICATION RESULT:")
    print("=" * 60)
    print("Success:", res["success"])
    print("Verdict:", res["verdict"])
    print("Downloaded files:", res["downloaded_files"])
    print("\n" + "=" * 60)
    print("FULL REPORT:")
    print("=" * 60)
    print(res["report"])

