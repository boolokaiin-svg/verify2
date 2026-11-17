"""Parallel Bilingual OCR, extraction, and classification using Google Gemini 3.1 Flash-Lite via OpenRouter."""
import json
import base64
import io
import re
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from openai import OpenAI

from src.config import CONFIG
from src.models import DocumentExtraction, PageData, ExtractedField, BoundingBox


EXTRACTION_PROMPT = """You are an expert bilingual Tamil Nadu land document OCR and extraction engine.
You are fluent in both Tamil (தமிழ்) and English legal terminology.

Analyze the provided document image(s) and extract ALL text and structured data accurately.
Tamil Nadu land documents typically contain mixed Tamil and English, official government seals, stamps, registration tables, and handwritten notations.

BILINGUAL REVENUE & LEGAL VOCABULARY GUIDE:
- Sale Deed / Title Deed: கிரய பத்திரம் / விற்பனை ஆவணம் / தான செட்டில்மெண்ட் பத்திரம்
- Patta / Chitta: பட்டா / சிட்டா / பட்டா மாறுதல் உத்தரவு
- Encumbrance Certificate (EC): வில்லங்கச் சான்றிதழ்
- Survey Number / Sub-division: சர்வே எண் / புல எண் / உட்பிரிவு எண் (e.g. 131/4, 45/2B, 929/1, 929/2)
- Extent / Area: விஸ்தீர்ணம் / பரப்பளவு (Acres / Cents / Ground / Sq.Ft / சதுர அடி)
- Purchaser / Buyer / Grantee: கிரயதாரர் / வாங்குபவர் / சொத்து வாங்குபவர்
- Vendor / Seller / Grantor: விற்பனையாளர் / கிரய விற்பனையாளர் / சொத்து கொடுப்பவர்
- Current Owner: நில உடமையாளர் / பட்டாதாரர் பெயர்
- Registration Date / Execution Date: பதிவு நாள் / எழுதிக் கொடுத்த நாள்
- Sub-Registrar Office: சார் பதிவாளர் அலுவலகம் (SRO)
- Document Registration Number: ஆவண எண் / பதிவு எண் (e.g., 14899/2025)
- Village / Taluk / District: கிராமம் / வட்டம் / மாவட்டம்
- Recitals / Prior Parent Document: மூலப்பத்திரம் / முந்தைய ஆவணம் / சொத்து வந்த வழி விவரம் (e.g. "Doc No 9929/2006 at Kundrathur SRO")

TASKS:
1. Classify document type strictly into one of: "sale_deed", "patta", "ec", "building_plan", "other".
2. Extract critical fields with confidence scores (0.0 to 1.0):
   - survey_number (normalized English format e.g. "929/1, 929/2")
   - extent (with unit e.g. "2512 sq.ft" or "5 cents")
   - owner_name (English transliteration/name)
   - grantor (seller name)
   - grantee (buyer name)
   - execution_date (YYYY-MM-DD or DD-MM-YYYY format)
   - registration_date (YYYY-MM-DD or DD-MM-YYYY format)
   - sro_name (Sub-Registrar Office e.g. "Kundrathur")
   - doc_number (e.g. "14899/2025")
   - village
   - district
   - parent_deed_doc_number (Doc number of previous deed cited in recitals/சொத்து வந்த வழி விவரம்)
   - parent_deed_year (Year of previous deed e.g. "2006")
   - parent_deed_sro (SRO of previous deed)
3. For each field, provide approximate bounding box coordinates (x1, y1, x2, y2) if identifiable.
4. Provide full extracted text for each page (preserving both Tamil and English).

OUTPUT STRICT JSON FORMAT:
{
  "doc_type": "sale_deed",
  "confidence": 0.95,
  "pages": [
    {
      "page_num": 1,
      "text": "full extracted page text in Tamil/English...",
      "fields": {
        "survey_number": {"value": "929/1, 929/2", "confidence": 0.98, "bounding_box": {"page": 1, "x1": 100, "y1": 200, "x2": 250, "y2": 230}},
        "extent": {"value": "2512 sq.ft", "confidence": 0.95},
        "owner_name": {"value": "M. Manikandan", "confidence": 0.96},
        "grantor": {"value": "J.D. John", "confidence": 0.95},
        "grantee": {"value": "M. Manikandan", "confidence": 0.97},
        "execution_date": {"value": "13-08-2025", "confidence": 0.98},
        "registration_date": {"value": "13-08-2025", "confidence": 0.99},
        "sro_name": {"value": "Kundrathur", "confidence": 0.95},
        "doc_number": {"value": "14899/2025", "confidence": 0.98},
        "village": {"value": "Kundrathur", "confidence": 0.95},
        "district": {"value": "Kanchipuram", "confidence": 0.95},
        "parent_deed_doc_number": {"value": "9929/2006", "confidence": 0.90},
        "parent_deed_year": {"value": "2006", "confidence": 0.90},
        "parent_deed_sro": {"value": "Kundrathur", "confidence": 0.90}
      },
      "bounding_boxes": []
    }
  ]
}

RULES:
- If a field is not present or cannot be found, set value to "" and confidence to 0.0.
- For Tamil names and locations, provide clear English transliterations in the field value.
- Never invent document numbers or survey numbers. Extract strictly what appears in the document.
- Return ONLY the JSON object.
"""


class GeminiOCRExtractor:
    """Gemini 3.1 Flash-Lite based document extractor via OpenRouter with Parallel Processing."""

    def __init__(self):
        cfg = CONFIG.AI_CLIENT_CONFIG
        if cfg.get("base_url"):
            self.client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], max_retries=1)
        else:
            self.client = OpenAI(api_key=cfg["api_key"], max_retries=1)
            
        self.model_name = CONFIG.OCR_MODEL
        self.batch_size = 4
        
        # Token metrics
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    def _resize_image(self, image_bytes: bytes, max_size: int = 1400) -> str:
        """Resize image to fit token limits while preserving high readability for OCR (memory-efficient JPEG)."""
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        del img
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def _process_single_batch(self, batch_info: Tuple[int, List[bytes]]) -> Dict[str, Any]:
        """Process a single batch of page images with OpenRouter."""
        start_idx, batch = batch_info
        batch_num = (start_idx // self.batch_size) + 1
        
        content_parts: List[Dict[str, Any]] = [
            {"type": "text", "text": EXTRACTION_PROMPT}
        ]
        
        for img_bytes in batch:
            b64_img = self._resize_image(img_bytes)
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64_img}"
                }
            })
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": content_parts}
                ],
                temperature=0.0,
                max_tokens=8192
            )
            
            # Extract token usage
            usage = getattr(response, "usage", None)
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            
            raw_text = response.choices[0].message.content or ""
            clean_json = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.MULTILINE)
            clean_json = re.sub(r"\s*```$", "", clean_json.strip(), flags=re.MULTILINE).strip()
            
            parsed = json.loads(clean_json)
            
            return {
                "batch_num": batch_num,
                "start_idx": start_idx,
                "parsed": parsed,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens
            }
        except Exception as e:
            err_msg = str(e)
            is_auth_error = "401" in err_msg or "User not found" in err_msg or "unauthorized" in err_msg.lower()
            if is_auth_error:
                print(f"[AUTH ERROR] Batch {batch_num}: API key rejected (401 - User not found).")
            else:
                print(f"Parallel OCR Batch {batch_num} Error: {e}")
            fallback_pages = []
            for idx in range(len(batch)):
                fallback_pages.append({
                    "page_num": start_idx + idx + 1,
                    "text": "",
                    "fields": {},
                    "bounding_boxes": [],
                    "error": str(e)
                })
            return {
                "batch_num": batch_num,
                "start_idx": start_idx,
                "parsed": {"pages": fallback_pages, "doc_type": "unknown", "confidence": 0.0},
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "auth_error": is_auth_error
            }

    def extract(self, page_images: List[bytes]) -> DocumentExtraction:
        """
        Extract structured data from document page images in PARALLEL.
        Dispatches batches to multiple threads for up to 4x faster execution.
        """
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        
        batches = [
            (i, page_images[i:i + self.batch_size]) 
            for i in range(0, len(page_images), self.batch_size)
        ]
        
        # Execute all batches in parallel
        results = []
        max_workers = min(len(batches), getattr(CONFIG, 'OCR_MAX_WORKERS', 2)) or 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_batch = {executor.submit(self._process_single_batch, b): b[0] for b in batches}
            for future in as_completed(future_to_batch):
                results.append(future.result())
        
        # Check if all batches failed with auth_error
        if results and all(r.get("auth_error") for r in results):
            raise RuntimeError(
                "AI Service Authentication Failed (401: User not found).\n"
                "The OPENROUTER_API_KEY in your .env was rejected by OpenRouter.\n"
                "Please generate a fresh key at https://openrouter.ai/keys and paste it into .env,\n"
                "or set GEMINI_API_KEY in .env (get a free key at https://aistudio.google.com/apikey)."
            )

        # Sort results strictly in order of page index
        results.sort(key=lambda r: r["start_idx"])
        
        all_pages = []
        doc_type = "unknown"
        overall_confidence = 0.0
        
        for res in results:
            self.total_prompt_tokens += res.get("prompt_tokens", 0)
            self.total_completion_tokens += res.get("completion_tokens", 0)
            
            parsed = res.get("parsed", {})
            start_idx = res.get("start_idx", 0)
            
            # Primary document classification from batch 1
            if start_idx == 0:
                doc_type = parsed.get("doc_type", "unknown")
                overall_confidence = parsed.get("confidence", 0.0)
            
            for page in parsed.get("pages", []):
                # Ensure 1-indexed overall page numbering
                page["page_num"] = page.get("page_num", 0) + start_idx
                all_pages.append(page)

        # Assemble structured PageData objects
        pages_data = []
        for p in all_pages:
            fields = {}
            for key, val in p.get("fields", {}).items():
                if isinstance(val, dict):
                    bb = val.get("bounding_box")
                    bbox = None
                    if bb:
                        bbox = BoundingBox(
                            field=key,
                            page=bb.get("page", p.get("page_num", 1)),
                            x1=bb.get("x1", 0), y1=bb.get("y1", 0),
                            x2=bb.get("x2", 0), y2=bb.get("y2", 0)
                        )
                    fields[key] = ExtractedField(
                        value=str(val.get("value", "")),
                        confidence=float(val.get("confidence", 0.0)),
                        bounding_box=bbox
                    )
            
            bboxes = []
            for bb in p.get("bounding_boxes", []):
                bboxes.append(BoundingBox(
                    field=bb.get("field", ""),
                    page=bb.get("page", p.get("page_num", 1)),
                    x1=bb.get("x1", 0), y1=bb.get("y1", 0),
                    x2=bb.get("x2", 0), y2=bb.get("y2", 0)
                ))
            
            pages_data.append(PageData(
                page_num=p.get("page_num", 0),
                text=p.get("text", ""),
                fields=fields,
                bounding_boxes=bboxes
            ))
        
        raw_text_combined = "\n".join([p.text for p in pages_data])
        
        return DocumentExtraction(
            doc_type=doc_type if doc_type in ["sale_deed", "patta", "ec", "building_plan", "other"] else "other",
            confidence=overall_confidence,
            pages=pages_data,
            raw_text=raw_text_combined
        )

    def check_critical_field_confidence(self, extraction: DocumentExtraction) -> Tuple[bool, list]:
        """Check if critical fields meet minimum confidence threshold."""
        critical_fields = ["survey_number", "extent", "owner_name", "execution_date"]
        low_confidence = []
        
        for page in extraction.pages:
            for field_name in critical_fields:
                if field_name in page.fields:
                    field = page.fields[field_name]
                    if 0 < field.confidence < CONFIG.MIN_OCR_CONFIDENCE:
                        low_confidence.append({
                            "field": field_name,
                            "value": field.value,
                            "confidence": field.confidence,
                            "page": page.page_num
                        })
        
        is_acceptable = len(low_confidence) == 0
        return is_acceptable, low_confidence