"""Report generation: GPT-5.6 narrates findings; code assembles final output."""
import json
from typing import List, Dict, Any
from openai import OpenAI

from src.config import CONFIG
from src.models import (
    NormalizedDocument, PortalCheckResult, GuardResult, Scores,
    MissingDocument, FinalReport
)


class ReportGenerator:
    """Narrates findings into clean actionable English. Code enforces final verdict and rules."""

    def __init__(self):
        cfg = CONFIG.AI_CLIENT_CONFIG
        if cfg.get("base_url"):
            self.client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], max_retries=1)
        else:
            self.client = OpenAI(api_key=cfg["api_key"], max_retries=1)
            
        self.model = CONFIG.REPORT_MODEL or CONFIG.GPT_MODEL
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def generate(self, normalized: NormalizedDocument,
                 portal: PortalCheckResult,
                 guard: GuardResult,
                 scores: Scores,
                 missing_docs: List[MissingDocument],
                 extraction: Any,
                 metrics: Any = None) -> FinalReport:
        """Generate final concise report."""

        # Build structured context for GPT
        context = self._build_context(normalized, portal, guard, scores, missing_docs)

        # GPT narrates issues, problematic areas, next actions
        narrative = self._call_gpt(context)

        # Assemble final report in strict format
        report = self._assemble_report(
            normalized, portal, guard, scores, missing_docs,
            narrative, extraction, metrics=metrics
        )

        return report

    def _build_context(self, normalized: NormalizedDocument,
                       portal: PortalCheckResult,
                       guard: GuardResult,
                       scores: Scores,
                       missing_docs: List[MissingDocument]) -> str:
        """Build structured context string for GPT prompt."""

        flags_text = "\n".join([
            f"- [{f.severity}] {f.type}: {f.details}"
            for f in guard.flags
        ]) or "- None"

        missing_text = "\n".join([
            f"{i+1}. {m.name} — {m.reason}"
            for i, m in enumerate(missing_docs)
        ]) or "- None"

        portal_text = (
            f"QR: {portal.qr_check_status}\n"
            f"Signature: {portal.signature_status}\n"
            f"Portal Search: {portal.portal_search_status}\n"
            f"Overall: {portal.overall_portal_status}"
        )

        return f"""
DOCUMENT TYPE: {normalized.doc_type}
SURVEY NUMBER: {normalized.survey_number or 'Not found'}
EXTENT: {normalized.extent or 'Not found'}
OWNER: {normalized.owner_name or 'Not found'}
GRANTOR: {normalized.grantor or 'Not found'}
GRANTEE: {normalized.grantee or 'Not found'}
EXECUTION DATE: {normalized.execution_date or 'Not found'}
REGISTRATION DATE: {normalized.registration_date or 'Not found'}
JURISDICTION: {normalized.jurisdiction or 'Unknown'}

PORTAL CHECK:
{portal_text}

GUARD FLAGS:
{flags_text}

RISK SCORE: {scores.risk_score}/100
CONFIDENCE SCORE: {scores.confidence_score}/100

MISSING DOCUMENTS FOR COMPLETE VERIFICATION:
{missing_text}
"""

    def _call_gpt(self, context: str) -> Dict[str, Any]:
        """Call GPT-5.6 to narrate findings. Strict constraints applied."""

        system_prompt = """You are a legal document assistant for Tamil Nadu property verification.
You ONLY narrate findings. You NEVER decide legal validity. You NEVER say "probably safe" or "likely fine".

RULES:
1. Explain each issue in exactly 1 concise line.
2. Explain each problematic area in exactly 1 concise line.
3. List next actions as bullet points.
4. If INCOMPLETE, explicitly state: "This document alone is NOT sufficient to confirm the land is issue-free."
5. If FAIL, explicitly state: "Hard issue found."
6. NEVER contradict the provided verdict.
7. Use plain language. No legal jargon unless necessary.
8. Output STRICT JSON:
{
  "issues": ["string", ...],
  "problematic_areas": ["string", ...],
  "next_actions": ["string", ...],
  "narrative_summary": "string"
}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze these findings and return JSON:\n\n{context}"}
                ],
                temperature=0.2,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            usage = getattr(response, "usage", None)
            if usage:
                self.prompt_tokens += getattr(usage, "prompt_tokens", 0)
                self.completion_tokens += getattr(usage, "completion_tokens", 0)

            content = response.choices[0].message.content or "{}"
            import re
            clean_json = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.MULTILINE)
            clean_json = re.sub(r"\s*```$", "", clean_json.strip(), flags=re.MULTILINE).strip()
            return json.loads(clean_json)

        except Exception as e:
            # Fallback if GPT fails
            return {
                "issues": ["GPT narration failed. Using structured data only."],
                "problematic_areas": [],
                "next_actions": ["Retry report generation or proceed with raw findings."],
                "narrative_summary": "Report generation encountered an error."
            }

    def _assemble_report(self, normalized: NormalizedDocument,
                         portal: PortalCheckResult,
                         guard: GuardResult,
                         scores: Scores,
                         missing_docs: List[MissingDocument],
                         narrative: Dict[str, Any],
                         extraction: Any,
                         metrics: Any = None) -> FinalReport:
        """Assemble final report with strict sections."""

        # Evidence references from bounding boxes
        evidence = []
        for page in extraction.pages:
            for field_name, field in page.fields.items():
                if field_name in ["survey_number", "owner_name", "grantor", "grantee", "extent"]:
                    if field.bounding_box:
                        evidence.append({
                            "field": field_name,
                            "value": field.value,
                            "page": page.page_num,
                            "bounding_box": {
                                "x1": field.bounding_box.x1,
                                "y1": field.bounding_box.y1,
                                "x2": field.bounding_box.x2,
                                "y2": field.bounding_box.y2
                            }
                        })

        # Final verdict status text
        verdict_status_map = {
            "INCOMPLETE": "This document alone is NOT sufficient to confirm the land is issue-free. Provide the documents below for final result.",
            "FAIL": "Hard issue found. This document has problems even before full verification.",
            "WARNING": "Minor issues found. Full verification still requires additional documents.",
            "PASS": "Title and Encumbrance verified. No adverse transactions or legal issues found."
        }

        final_status = verdict_status_map.get(guard.verdict, verdict_status_map["INCOMPLETE"])

        # Human review trigger
        human_review = guard.verdict in ["FAIL", "WARNING", "INCOMPLETE"] or scores.confidence_score < 50

        return FinalReport(
            verdict=guard.verdict,
            confidence=scores.confidence_score,
            risk=scores.risk_level,
            issues=narrative.get("issues", []),
            problematic_areas=narrative.get("problematic_areas", []),
            portal_check=portal,
            final_verdict_status=final_status,
            missing_documents=missing_docs,
            evidence_references=evidence,
            next_actions=narrative.get("next_actions", []),
            human_review_required=human_review,
            metrics=metrics
        )

    def to_text(self, report: FinalReport) -> str:
        """Convert report to strict text format for user display."""

        lines = [
            "=" * 70,
            f"VERDICT: {report.verdict}",
            f"CONFIDENCE: {report.confidence}%",
            f"RISK: {report.risk}",
            "",
            "ISSUES FOUND IN THIS DOCUMENT:",
        ]

        if report.issues:
            for issue in report.issues:
                lines.append(f"• {issue}")
        else:
            lines.append("• None")

        lines.extend([
            "",
            "PROBLEMATIC AREAS:",
        ])

        if report.problematic_areas:
            for area in report.problematic_areas:
                lines.append(f"• {area}")
        else:
            lines.append("• None")

        lines.extend([
            "",
            "PORTAL CHECK (TNREGINET):",
            f"• QR Verification: {report.portal_check.qr_check_status}",
            f"• Digital Signature: {report.portal_check.signature_status}",
            f"• Document Search: {report.portal_check.portal_search_status}",
            f"• Overall: {report.portal_check.overall_portal_status}",
            "",
            "FINAL VERDICT STATUS:",
            f"• {report.final_verdict_status}",
            "",
            "DOCUMENTS NEEDED FOR COMPLETE VERIFICATION:",
        ])

        for i, doc in enumerate(report.missing_documents, 1):
            lines.append(f"{i}. {doc.name} — {doc.reason}")

        lines.extend([
            "",
            "EVIDENCE REFERENCES:",
        ])

        for ev in report.evidence_references[:5]:  # Top 5
            lines.append(
                f"• \"{ev['value']}\" — Page {ev['page']}, "
                f"Box ({ev['bounding_box']['x1']:.0f}, {ev['bounding_box']['y1']:.0f}, "
                f"{ev['bounding_box']['x2']:.0f}, {ev['bounding_box']['y2']:.0f})"
            )

        lines.extend([
            "",
            "NEXT ACTIONS:",
        ])

        for action in report.next_actions:
            lines.append(f"• {action}")

        if report.metrics:
            lines.extend([
                "",
                "RESOURCE & EXECUTION METRICS:",
                f"• Total Time: {report.metrics.total_time_seconds:.2f} seconds",
                f"• AI Token Usage: {report.metrics.total_tokens:,} tokens ({report.metrics.prompt_tokens:,} prompt, {report.metrics.completion_tokens:,} completion)",
                f"• Estimated Cost: ${report.metrics.estimated_cost_usd:.4f} USD (~₹{report.metrics.estimated_cost_inr:.2f} INR)",
            ])

        lines.extend([
            "",
            f"⚠️  {report.disclaimer}",
            "=" * 70,
        ])

        return "\n".join(lines)