"""File intake validation — no external virus API, header-based checks only."""
import io
import os
try:
    import magic
except Exception:
    magic = None
import filetype
from PIL import Image
from pathlib import Path
from typing import Tuple, Optional, List
import pikepdf

from src.config import CONFIG


class IntakeValidator:
    """Validates uploaded files before processing."""
    
    def __init__(self):
        self.max_size = CONFIG.MAX_FILE_SIZE_MB * 1024 * 1024
        self.allowed_mimes = CONFIG.ALLOWED_MIME_TYPES
        self.max_pages = CONFIG.MAX_PDF_PAGES
        self.min_dim = CONFIG.MIN_IMAGE_DIMENSION
    
    def validate(self, file_bytes: bytes, filename: str) -> Tuple[bool, str, Optional[str]]:
        """
        Returns: (is_valid, mime_type, error_message)
        """
        # 1. Size check
        if len(file_bytes) > self.max_size:
            return False, "", f"File too large: {len(file_bytes)/(1024*1024):.1f}MB > {CONFIG.MAX_FILE_SIZE_MB}MB limit"
        
        # 2. MIME type via python-magic (reads file header, not extension)
        try:
            detected_mime = magic.from_buffer(file_bytes, mime=True) if magic else (filetype.guess(file_bytes).mime if filetype.guess(file_bytes) else ("application/pdf" if file_bytes[:4] == b"%PDF" else ""))
        except Exception as e:
            return False, "", f"Cannot detect file type: {str(e)}"
        
        if detected_mime not in self.allowed_mimes:
            return False, detected_mime, f"Unsupported file type: {detected_mime}. Only PDF, JPG, PNG allowed."
        
        # 3. File header integrity via filetype
        kind = filetype.guess(file_bytes)
        if kind is None:
            return False, detected_mime, "Cannot determine file format from header bytes."
        
        # 4. Format-specific validation
        if detected_mime == "application/pdf":
            return self._validate_pdf(file_bytes)
        elif detected_mime in ("image/jpeg", "image/png"):
            return self._validate_image(file_bytes)
        
        return False, detected_mime, "Unknown validation path."
    
    def _validate_pdf(self, file_bytes: bytes) -> Tuple[bool, str, Optional[str]]:
        """Validate PDF structure and page count."""
        try:
            pdf = pikepdf.open(io.BytesIO(file_bytes))
            page_count = len(pdf.pages)
            pdf.close()
            
            if page_count > self.max_pages:
                return False, "application/pdf", f"PDF has {page_count} pages (max {self.max_pages})."
            
            if page_count < 1:
                return False, "application/pdf", "PDF has no pages."
            
            return True, "application/pdf", None
        except pikepdf.PdfError as e:
            return False, "application/pdf", f"Invalid PDF structure: {str(e)}"
        except Exception as e:
            return False, "application/pdf", f"PDF validation error: {str(e)}"
    
    def _validate_image(self, file_bytes: bytes) -> Tuple[bool, str, Optional[str]]:
        """Validate image dimensions and corruption."""
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.verify()  # Check for corruption
            
            # Re-open after verify (verify closes file)
            img = Image.open(io.BytesIO(file_bytes))
            width, height = img.size
            
            if width < self.min_dim or height < self.min_dim:
                return False, f"image/{img.format.lower()}", f"Image too small: {width}x{height} (min {self.min_dim}x{self.min_dim})."
            
            return True, f"image/{img.format.lower()}", None
        except Exception as e:
            return False, "image/unknown", f"Invalid image: {str(e)}"
    
    def convert_to_images(self, file_bytes: bytes, mime_type: str) -> List[bytes]:
        """Convert upload to list of page images for Gemini OCR (memory-optimized for Render 512MB)."""
        images = []
        
        if mime_type == "application/pdf":
            try:
                try:
                    import pymupdf as fitz
                except ImportError:
                    import fitz
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                for page in doc:
                    # 130 DPI JPEG quality 85 provides crisp text for OCR while using 85% less RAM than 200 DPI PNG
                    pix = page.get_pixmap(dpi=130)
                    images.append(pix.tobytes("jpeg", jpg_quality=85))
                    del pix
                    if hasattr(fitz, "TOOLS") and hasattr(fitz.TOOLS, "store_shrink"):
                        fitz.TOOLS.store_shrink(100)
                doc.close()
                del doc
                import gc
                gc.collect()
            except Exception as e:
                from pdf2image import convert_from_bytes
                pil_images = convert_from_bytes(file_bytes, dpi=130)
                for pil_img in pil_images:
                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=85)
                    images.append(buf.getvalue())
        else:
            images.append(file_bytes)
        
        return images