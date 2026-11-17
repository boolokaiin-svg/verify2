"""Central configuration for Property Verification Agent."""
import os
import tempfile
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Production configuration with dynamic environment variable resolution."""
    
    # File intake limits
    MAX_FILE_SIZE_MB: int = 20
    ALLOWED_MIME_TYPES: List[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png"
    ]
    MAX_PDF_PAGES: int = 50
    MIN_IMAGE_DIMENSION: int = 500
    
    # Dynamic API Keys
    @property
    def OPENROUTER_API_KEY(self) -> str:
        return os.getenv("OPENROUTER_API_KEY", "")

    @property
    def OPENROUTER_BASE_URL(self) -> str:
        return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    @property
    def GEMINI_API_KEY(self) -> str:
        return os.getenv("GEMINI_API_KEY", "")

    @property
    def OPENAI_API_KEY(self) -> str:
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def CAPSOLVER_API_KEY(self) -> str:
        return os.getenv("CAPSOLVER_API_KEY", "")

    @property
    def AI_CLIENT_CONFIG(self) -> dict:
        """Dynamically resolves API key and base_url for OpenRouter, Google Gemini direct, or OpenAI."""
        if self.OPENROUTER_API_KEY:
            return {
                "api_key": self.OPENROUTER_API_KEY,
                "base_url": self.OPENROUTER_BASE_URL or "https://openrouter.ai/api/v1"
            }
        gemini_key = self.GEMINI_API_KEY or os.getenv("GOOGLE_API_KEY", "")
        if gemini_key:
            return {
                "api_key": gemini_key,
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"
            }
        if self.OPENAI_API_KEY:
            return {
                "api_key": self.OPENAI_API_KEY,
                "base_url": None
            }
        return {"api_key": "not-set", "base_url": None}

    @property
    def TAVILY_API_KEY(self) -> str:
        return os.getenv("TAVILY_API_KEY", "")

    # Dynamic Model settings
    @property
    def OCR_MODEL(self) -> str:
        return os.getenv("OCR_MODEL", "google/gemini-3.1-flash-lite")

    @property
    def CAPTCHA_MODEL(self) -> str:
        return os.getenv("CAPTCHA_MODEL", "google/gemini-3.1-flash-lite")

    @property
    def REPORT_MODEL(self) -> str:
        return os.getenv("REPORT_MODEL", "google/gemini-3.1-flash-lite")

    @property
    def GEMINI_MODEL(self) -> str:
        return os.getenv("GEMINI_MODEL", "google/gemini-3.1-flash-lite")

    @property
    def GPT_MODEL(self) -> str:
        return os.getenv("GPT_MODEL", "google/gemini-3.1-flash-lite")

    # OCR confidence threshold
    MIN_OCR_CONFIDENCE: float = 0.75

    # Portal verification
    @property
    def TNREGINET_BASE_URL(self) -> str:
        return os.getenv("TNREGINET_BASE_URL", "https://tnreginet.gov.in/portal")

    @property
    def TNREGINET_USERNAME(self) -> str:
        return os.getenv("TNREGINET_USERNAME", "")

    @property
    def TNREGINET_PASSWORD(self) -> str:
        return os.getenv("TNREGINET_PASSWORD", "")

    CAPSOLVER_TIMEOUT_SECONDS: int = 120

    @property
    def PORTAL_MODE(self) -> str:
        """
        Portal verification mode:
        - 'http': Ultra-lightweight zero-browser HTTP client (~25MB RAM, 0MB disk). Recommended for Render 512MB RAM.
        - 'remote_browser': Remote Playwright CDP (e.g. Browserless.io) via BROWSER_WS_ENDPOINT (0MB local Chromium).
        - 'local_browser': Local Playwright Chromium (only for machines with >= 2GB RAM).
        - 'auto': Use http if BROWSER_WS_ENDPOINT is empty; otherwise remote_browser.
        """
        return os.getenv("PORTAL_MODE", "http").lower()

    @property
    def BROWSER_WS_ENDPOINT(self) -> str:
        """Remote Chrome DevTools WebSocket URL (e.g. wss://chrome.browserless.io?token=YOUR_TOKEN)"""
        return os.getenv("BROWSER_WS_ENDPOINT", "")

    @property
    def OCR_MAX_WORKERS(self) -> int:
        """Maximum concurrent worker threads for OCR processing (default 2 to prevent OOM on 512MB RAM)."""
        return int(os.getenv("OCR_MAX_WORKERS", "2"))

    # Scoring
    RISK_OWNER_MISMATCH: int = 40
    RISK_SIGNATURE_INVALID: int = 20
    RISK_MISSING_DOC: int = 10

    CONFIDENCE_LOW_OCR_PENALTY: int = 30
    CONFIDENCE_PORTAL_FAIL_PENALTY: int = 20
    CONFIDENCE_INCOMPLETE_PENALTY: int = 15
    CONFIDENCE_CAPTCHA_FAIL_PENALTY: int = 10

    # Paths
    @property
    def TEMP_DIR(self) -> str:
        return os.getenv("TEMP_DIR", os.path.join(tempfile.gettempdir(), "property_agent"))

    CLAMAV_SOCKET: str = "/var/run/clamav/clamd.ctl"

    # PII pseudonyms
    PSEUDONYM_PREFIX: str = "PERSON_"


# Singleton instance
CONFIG = Config()