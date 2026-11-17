"""Determines if the document set is sufficient and what is missing."""
from typing import List
from src.models import NormalizedDocument, MissingDocument


class CompletenessEngine:
    """
    Tiered title assessment engine.
    - Sale Deed + Clean EC = PASS (Clear Title verified, Patta advised as administrative mutation).
    - Parent Deed is verified through Sale Deed recitals without forcing user upload.
    - Missing documents are categorized into required vs advisory.
    """
    
    def assess(self, normalized: NormalizedDocument, has_hard_issue: bool, 
               ec_verified: bool = False, patta_verified: bool = False) -> tuple[str, List[MissingDocument], bool]:
        """
        Returns: (verdict_base, missing_documents, can_final_verdict)
        """
        # If any hard fraud or mismatch was found, immediate FAIL
        if has_hard_issue:
            missing = [
                MissingDocument(name="Certified Copy / Rectification", reason="Hard discrepancy found with official government records.", required=True)
            ]
            return "FAIL", missing, False

        doc_type = normalized.doc_type or "other"
        missing: List[MissingDocument] = []

        if doc_type == "sale_deed":
            # 1. EC Check
            if not ec_verified:
                missing.append(MissingDocument(
                    name="Latest Encumbrance Certificate (EC)",
                    reason="Required to confirm property is free from mortgages, court attachments, or double sales.",
                    required=True
                ))
            
            # 2. Parent Deed Check (Satisfied if cited in recitals)
            has_recital_parent = bool(normalized.parent_deed_doc_number or normalized.parent_deed_details)
            if not has_recital_parent:
                missing.append(MissingDocument(
                    name="Prior Parent Deed (மூலப்பத்திரம்)",
                    reason="Prior deed reference was not clearly stated in recitals. Needed to establish 13-30 year unbroken title chain.",
                    required=False
                ))
            
            # 3. Patta Check (Advisory for mutation)
            if not patta_verified:
                missing.append(MissingDocument(
                    name="Current Patta / Chitta (பட்டா)",
                    reason="Recommended administrative step to ensure name mutation is updated in Tamil Nadu Nilam revenue records.",
                    required=False
                ))

            # Tiered Decision:
            # If EC is verified (either auto-downloaded or provided), we have complete title & encumbrance clearance!
            if ec_verified:
                return "PASS", missing, True
            else:
                return "INCOMPLETE", missing, False

        elif doc_type == "patta":
            missing.append(MissingDocument(
                name="Registered Sale Deed",
                reason="Patta proves revenue possession; registered Sale Deed is required to prove legal ownership.",
                required=True
            ))
            if not ec_verified:
                missing.append(MissingDocument(
                    name="Latest EC",
                    reason="To verify no bank liens or mortgages exist on the land.",
                    required=True
                ))
            return "INCOMPLETE", missing, False

        elif doc_type == "ec":
            missing.append(MissingDocument(
                name="Primary Sale Deed",
                reason="EC shows transaction history; the primary registered title deed is required to confirm rights.",
                required=True
            ))
            return "INCOMPLETE", missing, False

        elif doc_type == "building_plan":
            if not patta_verified:
                missing.append(MissingDocument(name="Patta", reason="To verify land ownership before construction approval", required=True))
            if not ec_verified:
                missing.append(MissingDocument(name="Latest EC", reason="To confirm land is free of lien", required=True))
            return "INCOMPLETE", missing, False

        else:
            missing.extend([
                MissingDocument(name="Sale Deed", reason="Primary ownership title document", required=True),
                MissingDocument(name="Latest EC", reason="Encumbrance check", required=True),
                MissingDocument(name="Patta", reason="Government revenue ownership record", required=False),
            ])
            return "INCOMPLETE", missing, False