"""Deterministic guard: code-based verdict, no LLM involvement."""
from typing import List, Optional
from src.models import NormalizedDocument, PortalCheckResult, GuardResult, GuardFlag
from src.config import CONFIG


class DeterministicGuard:
    """Hard checks. 100% reproducible. No probabilistic decisions."""
    
    def evaluate(self, normalized: NormalizedDocument, 
                 portal: PortalCheckResult,
                 ocr_low_confidence: List[dict],
                 completeness_verdict: str) -> GuardResult:
        """
        Run all hard checks and emit verdict.
        """
        flags: List[GuardFlag] = []
        
        # Check 1: Portal owner name mismatch
        if portal.qr_check_status == "MISMATCH" or portal.portal_search_status == "MISMATCH":
            flags.append(GuardFlag(
                type="OWNER_OR_SURVEY_MISMATCH",
                severity="FAIL",
                details="Document fields do not match TNREGINET portal records.",
                field="owner_name/survey_number"
            ))
        
        # Check 2: Unregistered / Not found
        if portal.portal_search_status == "NOT_FOUND" and portal.qr_check_status == "NO_QR_FOUND":
            flags.append(GuardFlag(
                type="UNREGISTERED_DOCUMENT",
                severity="FAIL",
                details="Document not found in TNREGINET portal. May be unregistered or forged.",
                field="doc_number"
            ))
        
        # Check 3: Invalid digital signature
        if portal.signature_status == "INVALID":
            flags.append(GuardFlag(
                type="INVALID_SIGNATURE",
                severity="FAIL",
                details="Digital signature validation failed. Document may have been tampered with.",
                field="digital_signature"
            ))
        
        # Check 4: Date logic
        if normalized.execution_date and normalized.registration_date:
            if normalized.execution_date > normalized.registration_date:
                flags.append(GuardFlag(
                    type="DATE_LOGIC_ERROR",
                    severity="FAIL",
                    details=f"Execution date ({normalized.execution_date}) is after registration date ({normalized.registration_date}).",
                    field="execution_date/registration_date"
                ))
        

        # Check 6: OCR low confidence on critical fields
        if ocr_low_confidence:
            fields = ", ".join([f"{f['field']} (page {f['page']})" for f in ocr_low_confidence[:3]])
            flags.append(GuardFlag(
                type="OCR_LOW_CONFIDENCE",
                severity="WARNING",
                details=f"Low OCR confidence on: {fields}",
                field="multiple"
            ))
            
        # Check 7: Downloaded Documents Cross-Verification
        if portal.portal_details.get("patta_mismatch"):
            flags.append(GuardFlag(
                type="DOWNLOADED_PATTA_MISMATCH",
                severity="WARNING",
                details="Auto-downloaded Patta shows a different owner. Pending transfer or mutation issue.",
                field="owner_name"
            ))
        if portal.portal_details.get("patta_survey_mismatch"):
            flags.append(GuardFlag(
                type="DOWNLOADED_PATTA_MISMATCH",
                severity="FAIL",
                details="Auto-downloaded Patta shows a different survey number.",
                field="survey_number"
            ))
        if portal.portal_details.get("ec_mismatch"):
            flags.append(GuardFlag(
                type="DOWNLOADED_EC_MISMATCH",
                severity="FAIL",
                details="Auto-downloaded EC shows conflicting ownership details.",
                field="owner_name"
            ))
            

        for consistency in normalized.consistency_flags:
            if consistency == "EXECUTION_DATE_AFTER_REGISTRATION":
                flags.append(GuardFlag(
                    type="CONSISTENCY_ERROR",
                    severity="FAIL",
                    details="Execution date is after registration date.",
                    field="dates"
                ))
            elif consistency == "MULTIPLE_SURVEY_NUMBERS_ACROSS_PAGES":
                flags.append(GuardFlag(
                    type="CONSISTENCY_ERROR",
                    severity="WARNING",
                    details="Different survey numbers found across pages of the same document.",
                    field="survey_number"
                ))
        
        # Determine verdict
        has_fail = any(f.severity == "FAIL" for f in flags)
        has_warning = any(f.severity == "WARNING" for f in flags)
        
        if has_fail:
            verdict = "FAIL"
        elif has_warning:
            verdict = "WARNING"
        elif completeness_verdict == "PASS":
            verdict = "PASS"
        else:
            verdict = completeness_verdict  # Usually INCOMPLETE
        
        can_final = (verdict == "PASS")
        
        return GuardResult(verdict=verdict, flags=flags, can_final_verdict=can_final)