"""Normalize extracted fields: dates, numbers, names, PII pseudonyms."""
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from src.models import DocumentExtraction, NormalizedDocument, ExtractedField
from src.config import CONFIG


class DocumentNormalizer:
    """Normalizes and validates extracted document fields."""
    
    # Tamil-English name normalization mappings
    TRANSLIT_VARIANTS = {
        "th": "t", "dh": "d", "sh": "s", "zh": "z",
        "aa": "a", "ee": "e", "oo": "o", "uu": "u",
        "k.": "k", "r.": "r", "s.": "s", "m.": "m"
    }
    
    def __init__(self):
        self.pseudonym_counter = 0
        self.pseudonym_map: Dict[str, str] = {}
    
    def normalize(self, extraction: DocumentExtraction) -> NormalizedDocument:
        """Convert extraction to normalized, canonical form."""
        # Aggregate fields across pages (take highest confidence value)
        aggregated = self._aggregate_fields(extraction)
        
        # Extract key values
        survey = self._canonicalize_survey(aggregated.get("survey_number", ""))
        extent = aggregated.get("extent", "")
        extent_sqft = self._normalize_extent(extent)
        
        owner = aggregated.get("owner_name", "")
        grantor = aggregated.get("grantor", "")
        grantee = aggregated.get("grantee", "")
        
        exec_date = self._normalize_date(aggregated.get("execution_date", ""))
        reg_date = self._normalize_date(aggregated.get("registration_date", ""))
        
        sro = aggregated.get("sro_name", "")
        doc_num = aggregated.get("doc_number", "")
        village = aggregated.get("village", "")
        district = aggregated.get("district", "")
        
        parent_doc = aggregated.get("parent_deed_doc_number", "")
        parent_year = aggregated.get("parent_deed_year", "")
        parent_sro = aggregated.get("parent_deed_sro", "")
        parent_details = f"Doc No: {parent_doc}, Year: {parent_year}, SRO: {parent_sro}" if (parent_doc or parent_year) else None
        
        # Derive jurisdiction
        jurisdiction = self._derive_jurisdiction(district, village, sro)
        
        # Create pseudonyms for PII
        all_names = [n for n in [owner, grantor, grantee] if n]
        pseudonyms = self._create_pseudonyms(all_names)
        
        # Run consistency checks
        consistency_flags = self._check_consistency(
            extraction, exec_date, reg_date, extent, extent_sqft
        )
        
        return NormalizedDocument(
            doc_type=extraction.doc_type,
            survey_number=survey,
            extent=extent,
            extent_normalized_sqft=extent_sqft,
            owner_name=owner,
            grantor=grantor,
            grantee=grantee,
            execution_date=exec_date,
            registration_date=reg_date,
            sro_name=sro,
            doc_number=doc_num,
            village=village,
            district=district,
            jurisdiction=jurisdiction,
            parent_deed_details=parent_details,
            parent_deed_doc_number=parent_doc if parent_doc else None,
            parent_deed_year=parent_year if parent_year else None,
            parent_deed_sro=parent_sro if parent_sro else None,
            pseudonyms=pseudonyms,
            consistency_flags=consistency_flags
        )
    
    def _aggregate_fields(self, extraction: DocumentExtraction) -> Dict[str, str]:
        """Take the highest-confidence value for each field across pages."""
        best: Dict[str, Tuple[str, float]] = {}
        for page in extraction.pages:
            for field_name, field in page.fields.items():
                if field_name not in best or field.confidence > best[field_name][1]:
                    best[field_name] = (field.value, field.confidence)
        return {k: v[0] for k, v in best.items()}
    
    def _canonicalize_survey(self, raw: str) -> Optional[str]:
        """Normalize survey number format."""
        if not raw:
            return None
        # Remove extra spaces, standardize slash
        cleaned = raw.strip().upper()
        cleaned = re.sub(r"\s+", "", cleaned)
        cleaned = re.sub(r"[\\\/]", "/", cleaned)
        # Pattern: number/number or number/numberletter
        match = re.match(r"^(\d+)/(\d+)([A-Z]?)$", cleaned)
        if match:
            return f"{match.group(1)}/{match.group(2)}{match.group(3)}"
        return cleaned if cleaned else None
    
    def _normalize_extent(self, raw: str) -> Optional[float]:
        """Convert extent to square feet."""
        if not raw:
            return None
        
        # Extract number and unit
        match = re.search(r"(\d+\.?\d*)\s*(acres?|grounds?|sq\.?ft|square\s*feet|hectares?|cents?)", raw.lower())
        if not match:
            return None
        
        value = float(match.group(1))
        unit = match.group(2)
        
        conversions = {
            "acre": 43560, "acres": 43560,
            "ground": 2400, "grounds": 2400,
            "sqft": 1, "sq.ft": 1, "square feet": 1,
            "hectare": 107639, "hectares": 107639,
            "cent": 435.6, "cents": 435.6
        }
        
        for key, factor in conversions.items():
            if key in unit:
                return round(value * factor, 2)
        
        return value
    
    def _normalize_date(self, raw: str) -> Optional[str]:
        """Convert various date formats to ISO 8601."""
        if not raw:
            return None
        
        formats = [
            "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
            "%d-%m-%y", "%d/%m/%y",
            "%Y-%m-%d", "%Y/%m/%d",
            "%d %B %Y", "%d %b %Y",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(raw.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        return None
    
    def _derive_jurisdiction(self, district: str, village: str, sro: str) -> str:
        """Derive planning jurisdiction from location."""
        district_lower = (district or "").lower()
        sro_lower = (sro or "").lower()
        
        # Chennai Metropolitan Area
        chennai_keywords = ["chennai", "ambattur", "avadi", "tambaram", "pallavaram", "alandur"]
        if any(k in district_lower or k in sro_lower for k in chennai_keywords):
            return "CMDA"
        
        # DTCP areas (major towns)
        dtcp_towns = ["coimbatore", "madurai", "trichy", "salem", "tirunelveli", 
                      "erode", "tiruppur", "vellore", "thanjavur"]
        if any(k in district_lower for k in dtcp_towns):
            return "DTCP"
        
        # Default to local panchayat
        return "LOCAL_PANCHAYAT"
    
    def _create_pseudonyms(self, names: List[str]) -> Dict[str, str]:
        """Replace real names with stable pseudonyms."""
        for name in names:
            normalized = self._normalize_name(name)
            if normalized not in self.pseudonym_map and normalized:
                self.pseudonym_counter += 1
                self.pseudonym_map[normalized] = f"{CONFIG.PSEUDONYM_PREFIX}{chr(64 + self.pseudonym_counter)}"
        return self.pseudonym_map
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for matching."""
        cleaned = name.lower().strip()
        cleaned = re.sub(r"[^a-z\s]", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        for old, new in self.TRANSLIT_VARIANTS.items():
            cleaned = cleaned.replace(old, new)
        return cleaned.strip()
    
    def _check_consistency(self, extraction: DocumentExtraction, 
                           exec_date: Optional[str], reg_date: Optional[str],
                           extent: str, extent_sqft: Optional[float]) -> List[str]:
        """Run internal consistency checks."""
        flags = []
        
        # Date logic
        if exec_date and reg_date:
            if exec_date > reg_date:
                flags.append("EXECUTION_DATE_AFTER_REGISTRATION")
        
        # Duplicate survey numbers across pages
        surveys = []
        for page in extraction.pages:
            if "survey_number" in page.fields and page.fields["survey_number"].value:
                surveys.append(page.fields["survey_number"].value)
        if len(set(surveys)) > 1:
            flags.append("MULTIPLE_SURVEY_NUMBERS_ACROSS_PAGES")
        
        return flags