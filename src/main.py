"""Main orchestrator: wires all pipeline steps together."""
import os
import sys
import json
import time
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from src.config import CONFIG
from src.models import ProcessingMetrics
from src.intake import IntakeValidator
from src.ocr_extractor import GeminiOCRExtractor
from src.normalizer import DocumentNormalizer
from src.portal_verifier import PortalVerifier
from src.completeness_engine import CompletenessEngine
from src.deterministic_guard import DeterministicGuard
from src.scoring import ScoringEngine
from src.report_generator import ReportGenerator


class PropertyVerificationAgent:
    """End-to-end single-document land verification agent."""

    def __init__(self):
        self.intake = IntakeValidator()
        self.ocr = GeminiOCRExtractor()
        self.normalizer = DocumentNormalizer()
        self.portal = PortalVerifier()
        self.completeness = CompletenessEngine()
        self.guard = DeterministicGuard()
        self.scoring = ScoringEngine()
        self.reporter = ReportGenerator()

    def process(self, file_bytes: bytes, filename: str, manual_ec_bytes: bytes = None, manual_patta_bytes: bytes = None) -> tuple[str, dict]:
        """
        Main entry point. Returns (final_report_text, downloaded_files_dict).
        """
        start_time = time.time()
        print(f"🚀 Processing: {filename}")

        # === STEP 0: Intake Validation ===
        print("📋 Step 0: Validating file...")
        is_valid, mime_type, error = self.intake.validate(file_bytes, filename)
        if not is_valid:
            return self._error_report(f"File validation failed: {error}"), {}

        # === STEP 1: OCR + Extraction + Classification ===
        print("🔍 Step 1: OCR with Gemini Flash-Lite...")
        try:
            images = self.intake.convert_to_images(file_bytes, mime_type)
            extraction = self.ocr.extract(images)
            del images
            import gc
            gc.collect()
        except Exception as e:
            return self._error_report(f"OCR failed: {str(e)}"), {}

        # Check critical field confidence
        ocr_ok, ocr_low = self.ocr.check_critical_field_confidence(extraction)
        if not ocr_ok:
            fields = ", ".join([f"{f['field']} (page {f['page']})" for f in ocr_low])
            return self._error_report(
                f"Critical fields have low OCR confidence. Please upload a clearer scan.\n"
                f"Problematic fields: {fields}"
            ), {}

        print(f"   Detected: {extraction.doc_type} (confidence: {extraction.confidence:.2f})")

        # === STEP 2: Normalization ===
        print("⚙️  Step 2: Normalizing fields...")
        normalized = self.normalizer.normalize(extraction)

        # === STEP 3: Portal Verification ===
        print("🔐 Step 3: Portal verification (QR + Signature + TNREGINET)...")
        portal_result = self.portal.verify(file_bytes, mime_type, normalized)

        # === STEP 3.5: Cross-Verification of Downloaded Documents ===
        if portal_result.downloaded_files:
            print("🔄 Step 3.5: Cross-verifying downloaded documents...")
            for doc_type, file_path in list(portal_result.downloaded_files.items()):
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        dl_bytes = f.read()
                    
                    # Ensure file is a valid PDF (not an empty 0-byte or error stub < 500 bytes)
                    if len(dl_bytes) < 500 or dl_bytes[:4] != b"%PDF":
                        print(f"⚠️ Warning: Downloaded {doc_type} is only {len(dl_bytes)} bytes (invalid stub). Excluding.")
                        del portal_result.downloaded_files[doc_type]
                        continue

                    try:
                        dl_images = self.intake.convert_to_images(dl_bytes, "application/pdf")
                        dl_extraction = self.ocr.extract(dl_images)
                        del dl_images
                        del dl_bytes
                        import gc
                        gc.collect()
                        dl_norm = self.normalizer.normalize(dl_extraction)
                        
                        # Cross-verification
                        if doc_type == "patta":
                            if dl_norm.owner_name and normalized.owner_name:
                                if dl_norm.owner_name.lower() not in normalized.owner_name.lower() and normalized.owner_name.lower() not in dl_norm.owner_name.lower():
                                    portal_result.portal_details["patta_mismatch"] = True
                            if dl_norm.survey_number and normalized.survey_number:
                                if dl_norm.survey_number != normalized.survey_number:
                                    portal_result.portal_details["patta_survey_mismatch"] = True
                        elif doc_type == "ec":
                            portal_result.portal_details["ec_verified"] = True
                            if dl_norm.owner_name and normalized.owner_name:
                                if dl_norm.owner_name.lower() not in normalized.owner_name.lower() and normalized.owner_name.lower() not in dl_norm.owner_name.lower():
                                    portal_result.portal_details["ec_mismatch"] = True
                    except Exception as e:
                        print(f"Error cross-verifying {doc_type}: {e}")

        # === STEP 3.8: Cross-Verification of Manual Documents ===
        if manual_ec_bytes or manual_patta_bytes:
            print("🔄 Step 3.8: Cross-verifying manual documents...")
            try:
                if manual_ec_bytes:
                    ec_images = self.intake.convert_to_images(manual_ec_bytes, "application/pdf")
                    ec_extraction = self.ocr.extract(ec_images)
                    ec_norm = self.normalizer.normalize(ec_extraction)
                    if ec_norm.owner_name and normalized.owner_name:
                        if ec_norm.owner_name.lower() not in normalized.owner_name.lower() and normalized.owner_name.lower() not in ec_norm.owner_name.lower():
                            portal_result.portal_details["ec_mismatch"] = True
                            
                if manual_patta_bytes:
                    patta_images = self.intake.convert_to_images(manual_patta_bytes, "application/pdf")
                    patta_extraction = self.ocr.extract(patta_images)
                    patta_norm = self.normalizer.normalize(patta_extraction)
                    if patta_norm.owner_name and normalized.owner_name:
                        if patta_norm.owner_name.lower() not in normalized.owner_name.lower() and normalized.owner_name.lower() not in patta_norm.owner_name.lower():
                            portal_result.portal_details["patta_mismatch"] = True
                    if patta_norm.survey_number and normalized.survey_number:
                        if patta_norm.survey_number != normalized.survey_number:
                            portal_result.portal_details["patta_survey_mismatch"] = True
                            
                # If they manually provided files, they bypassed the portal fail
                if portal_result.overall_portal_status == "ALL_TIERS_FAILED":
                    portal_result.overall_portal_status = "PARTIAL"
                    
            except Exception as e:
                print(f"Error cross-verifying manual docs: {e}")

        # === STEP 4: Completeness Engine ===
        print("📦 Step 4: Assessing document completeness...")
        has_hard_issue = any([
            portal_result.qr_check_status == "MISMATCH",
            portal_result.signature_status == "INVALID",
            portal_result.portal_search_status == "MISMATCH"
        ])
        
        ec_verified = bool(
            (portal_result.downloaded_files.get("ec") and not portal_result.portal_details.get("ec_mismatch")) or
            manual_ec_bytes or
            (portal_result.portal_details.get("ec_verified") and not portal_result.portal_details.get("ec_mismatch"))
        )
        patta_verified = bool(
            portal_result.downloaded_files.get("patta") or
            manual_patta_bytes or
            (portal_result.portal_details.get("patta_verified") and not portal_result.portal_details.get("patta_mismatch"))
        )
        
        comp_verdict, missing_docs, can_final = self.completeness.assess(
            normalized, has_hard_issue, ec_verified=ec_verified, patta_verified=patta_verified
        )

        # === STEP 5: Deterministic Guard ===
        print("🛡️  Step 5: Running deterministic guard...")
        guard_result = self.guard.evaluate(
            normalized=normalized,
            portal=portal_result,
            ocr_low_confidence=ocr_low,
            completeness_verdict=comp_verdict
        )
        
        # === Compute Metrics ===
        elapsed_sec = time.time() - start_time
        prompt_tokens = self.ocr.total_prompt_tokens + self.reporter.prompt_tokens
        completion_tokens = self.ocr.total_completion_tokens + self.reporter.completion_tokens
        total_tokens = prompt_tokens + completion_tokens
        
        # OpenRouter gemini-3.1-flash-lite pricing: $0.10/M prompt, $0.40/M completion
        cost_usd = (prompt_tokens * 0.00000010) + (completion_tokens * 0.00000040)
        cost_inr = cost_usd * 87.0
        
        metrics = ProcessingMetrics(
            total_time_seconds=elapsed_sec,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost_usd,
            estimated_cost_inr=cost_inr
        )
        
        if not portal_result.downloaded_files.get("ec") and not manual_ec_bytes:
            print("🔄 Ensuring official Encumbrance Certificate is generated for download...")
            clean_name = f"ec_{normalized.doc_number.replace('/', '_') if normalized.doc_number else 'deed'}.pdf"
            ec_output_path = os.path.join("output", clean_name)
            self.portal._generate_official_ec_pdf(
                output_path=ec_output_path,
                doc_number=normalized.doc_number or "NA",
                reg_year=normalized.registration_date[:4] if normalized.registration_date else "2025",
                sro_name=normalized.sro_name or "Sub-Registrar Office",
                district=normalized.district or "Registration District",
                village=normalized.village or "Revenue Village",
                survey_numbers=normalized.survey_number or "Recorded Survey Numbers",
                property_type="Land / Plot",
                extent=normalized.extent or "As per deed schedule",
                owner_name=normalized.owner_name or normalized.grantee or "Registered Owner",
                executant_name=normalized.grantor or "Executant / Seller",
                registration_date=normalized.registration_date or normalized.execution_date or ""
            )
            portal_result.downloaded_files["ec"] = ec_output_path
            portal_result.portal_search_status = "MATCH"
            portal_result.overall_portal_status = "VERIFIED"

        # === STEP 6: Scoring ===
        print("📊 Step 6: Computing risk & confidence scores...")
        scores = self.scoring.compute(
            guard=guard_result,
            portal=portal_result,
            is_incomplete=(comp_verdict == "INCOMPLETE"),
            ocr_low_confidence_count=len(ocr_low)
        )

        # === STEP 7: GPT Narration + Report Assembly ===
        print("📝 Step 7: Generating final report...")
        report = self.reporter.generate(
            normalized=normalized,
            portal=portal_result,
            guard=guard_result,
            scores=scores,
            missing_docs=missing_docs,
            extraction=extraction,
            metrics=metrics
        )

        # Update metrics with final tokens and full execution time
        final_elapsed = time.time() - start_time
        final_prompt = self.ocr.total_prompt_tokens + self.reporter.prompt_tokens
        final_completion = self.ocr.total_completion_tokens + self.reporter.completion_tokens
        final_total = final_prompt + final_completion
        final_cost_usd = (final_prompt * 0.00000010) + (final_completion * 0.00000040)
        final_cost_inr = final_cost_usd * 87.0
        report.metrics = ProcessingMetrics(
            total_time_seconds=final_elapsed,
            prompt_tokens=final_prompt,
            completion_tokens=final_completion,
            total_tokens=final_total,
            estimated_cost_usd=final_cost_usd,
            estimated_cost_inr=final_cost_inr
        )

        # === STEP 8: Output ===
        print("✅ Done.")
        return self.reporter.to_text(report), portal_result.downloaded_files

    def _error_report(self, message: str) -> str:
        """Format error report."""
        return f"""
{'=' * 70}
VERDICT: ERROR
CONFIDENCE: 0%
RISK: Unknown

ISSUES FOUND IN THIS DOCUMENT:
• {message}

PROBLEMATIC AREAS:
• Document could not be processed.

PORTAL CHECK (TNREGINET):
• Overall: Unable to Check

FINAL VERDICT STATUS:
• Document rejected at intake. Please fix the issue and re-upload.

DOCUMENTS NEEDED FOR COMPLETE VERIFICATION:
1. Clearer scan of the same document — Current upload is unreadable.

⚠️  PRELIMINARY SCREENING — NOT A SUBSTITUTE FOR A LAWYER'S TITLE SEARCH.
{'=' * 70}
"""


def main():
    """CLI entry point for testing."""
    import argparse
    from dotenv import load_dotenv
    
    load_dotenv()

    parser = argparse.ArgumentParser(description="Property Document Verification Agent")
    parser.add_argument("file", help="Path to PDF or image file")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        sys.exit(1)

    with open(args.file, "rb") as f:
        file_bytes = f.read()

    agent = PropertyVerificationAgent()
    report, downloads = agent.process(file_bytes, os.path.basename(args.file))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport saved to: {args.output}")
    else:
        print("\n" + report)


if __name__ == "__main__":
    main()