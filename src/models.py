"""Pydantic models for structured data throughout the pipeline."""
from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class BoundingBox(BaseModel):
    field: str
    page: int
    x1: float
    y1: float
    x2: float
    y2: float


class ExtractedField(BaseModel):
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: Optional[BoundingBox] = None


class PageData(BaseModel):
    page_num: int
    text: str
    fields: Dict[str, ExtractedField]
    bounding_boxes: List[BoundingBox] = []


class DocumentExtraction(BaseModel):
    doc_type: Literal["sale_deed", "patta", "ec", "building_plan", "other", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    pages: List[PageData]
    raw_text: str = ""


class NormalizedDocument(BaseModel):
    doc_type: str
    survey_number: Optional[str] = None
    extent: Optional[str] = None
    extent_normalized_sqft: Optional[float] = None
    owner_name: Optional[str] = None
    grantor: Optional[str] = None
    grantee: Optional[str] = None
    execution_date: Optional[str] = None  # ISO 8601
    registration_date: Optional[str] = None  # ISO 8601
    sro_name: Optional[str] = None
    doc_number: Optional[str] = None
    village: Optional[str] = None
    taluk: Optional[str] = None
    district: Optional[str] = None
    jurisdiction: Optional[str] = None  # CMDA / DTCP / Panchayat
    parent_deed_details: Optional[str] = None
    parent_deed_doc_number: Optional[str] = None
    parent_deed_year: Optional[str] = None
    parent_deed_sro: Optional[str] = None
    pseudonyms: Dict[str, str] = {}  # real_name -> PERSON_A
    consistency_flags: List[str] = []


class PortalCheckResult(BaseModel):
    qr_check_status: Literal["MATCH", "MISMATCH", "NO_QR_FOUND", "QR_UNREADABLE", "NOT_CHECKED"]
    signature_status: Literal["VALID", "INVALID", "NOT_SIGNED", "ERROR", "NOT_CHECKED"]
    portal_search_status: Literal["MATCH", "MISMATCH", "NOT_FOUND", "CAPTCHA_FAILED", "DOWN", "ALL_TIERS_FAILED", "NOT_CHECKED"]
    overall_portal_status: Literal["VERIFIED", "PARTIAL", "UNABLE_TO_VERIFY", "ALL_TIERS_FAILED"]
    portal_details: Dict[str, Any] = {}
    downloaded_files: Dict[str, str] = {}
    errors: List[str] = []



class MissingDocument(BaseModel):
    name: str
    reason: str
    required: bool = True


class GuardFlag(BaseModel):
    type: str
    severity: Literal["FAIL", "WARNING", "INFO"]
    details: str
    field: Optional[str] = None


class GuardResult(BaseModel):
    verdict: Literal["PASS", "WARNING", "FAIL", "INCOMPLETE"]
    flags: List[GuardFlag]
    can_final_verdict: bool = False


class Scores(BaseModel):
    risk_score: int = Field(ge=0, le=100)
    confidence_score: int = Field(ge=0, le=100)
    risk_level: Literal["Low", "Medium", "High", "Unknown"]


class ProcessingMetrics(BaseModel):
    total_time_seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    estimated_cost_inr: float = 0.0


class FinalReport(BaseModel):
    verdict: Literal["PASS", "WARNING", "FAIL", "INCOMPLETE"]
    confidence: int
    risk: Literal["Low", "Medium", "High", "Unknown"]
    issues: List[str]
    problematic_areas: List[str]
    portal_check: PortalCheckResult
    final_verdict_status: str
    missing_documents: List[MissingDocument]
    evidence_references: List[Dict[str, Any]]
    next_actions: List[str]
    disclaimer: str = "PRELIMINARY SCREENING — NOT A SUBSTITUTE FOR A LAWYER'S TITLE SEARCH."
    human_review_required: bool = False
    metrics: Optional[ProcessingMetrics] = None