"""Risk and confidence scoring — kept strictly separate."""
from src.models import GuardResult, PortalCheckResult, Scores
from src.config import CONFIG


class ScoringEngine:
    """Computes two independent scores: Risk and Confidence."""
    
    def compute(self, guard: GuardResult, portal: PortalCheckResult, 
                is_incomplete: bool, ocr_low_confidence_count: int) -> Scores:
        """
        Risk: based on hard verdicts (higher = more dangerous).
        Confidence: based on evidence quality (higher = more certain).
        """
        risk = self._compute_risk(guard, portal)
        confidence = self._compute_confidence(guard, portal, is_incomplete, ocr_low_confidence_count)
        
        risk_level = self._risk_level(risk)
        
        return Scores(risk_score=risk, confidence_score=confidence, risk_level=risk_level)
    
    def _compute_risk(self, guard: GuardResult, portal: PortalCheckResult) -> int:
        score = 0
        
        for flag in guard.flags:
            if flag.type in ["OWNER_OR_SURVEY_MISMATCH", "UNREGISTERED_DOCUMENT"]:
                score += CONFIG.RISK_OWNER_MISMATCH
            elif flag.type == "INVALID_SIGNATURE":
                score += CONFIG.RISK_SIGNATURE_INVALID
            elif flag.type == "MISSING_CRITICAL_DOC":
                score += CONFIG.RISK_MISSING_DOC
            elif flag.type == "DOWNLOADED_PATTA_MISMATCH":
                score += 20
            elif flag.type == "DOWNLOADED_EC_MISMATCH":
                score += 20
        
        # Additional risk from portal status
        if portal.portal_search_status == "MISMATCH":
            score += 20
        if portal.qr_check_status == "MISMATCH":
            score += 20
        if portal.overall_portal_status == "ALL_TIERS_FAILED":
            score += 25
        
        return min(score, 100)
    
    def _compute_confidence(self, guard: GuardResult, portal: PortalCheckResult,
                           is_incomplete: bool, ocr_low_count: int) -> int:
        score = 100
        
        # OCR quality penalty
        if ocr_low_count > 0:
            score -= CONFIG.CONFIDENCE_LOW_OCR_PENALTY
        
        # Portal verification penalty
        if portal.overall_portal_status in ["UNABLE_TO_VERIFY", "ALL_TIERS_FAILED"]:
            score -= CONFIG.CONFIDENCE_PORTAL_FAIL_PENALTY
        elif portal.overall_portal_status == "PARTIAL":
            score -= 10
        
        # Completeness penalty
        if is_incomplete:
            score -= CONFIG.CONFIDENCE_INCOMPLETE_PENALTY
        
        # CAPTCHA failure penalty
        if portal.portal_search_status == "CAPTCHA_FAILED":
            score -= CONFIG.CONFIDENCE_CAPTCHA_FAIL_PENALTY
        
        # If incomplete, cap confidence
        if is_incomplete:
            score = min(score, 40)
        
        return max(score, 0)
    
    def _risk_level(self, risk: int) -> str:
        if risk >= 60:
            return "High"
        elif risk >= 30:
            return "Medium"
        else:
            return "Low"