"""Personalized document checklist and application guidance service.

This service generates:
1. Personalized document checklists based on scheme requirements
2. Step-by-step application guides with official links
3. Source-linked explanations for each requirement

The service uses existing scheme payload data (documents, application_steps)
and applies personalization based on profile answers where applicable.

No persistent storage of documents or guides.
"""

from __future__ import annotations

from typing import Any

from claim_whats_yours.domain.fields import load_registry


class DocumentService:
    """Generates personalized document checklists and application guides."""

    def __init__(self) -> None:
        self._registry = load_registry()

    def get_document_checklist(
        self,
        scheme_payload: dict[str, Any],
        profile_answers: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a personalized document checklist for a scheme.

        Args:
            scheme_payload: The scheme's payload dict containing documents.
            profile_answers: The citizen's profile answers.

        Returns:
            A structured checklist with:
                - required: list of mandatory documents
                - conditional: list of documents that may be needed
                - excluded: list of documents not needed based on profile
                - explanation: why each document is required
        """
        documents = self._extract_documents(scheme_payload)

        required: list[dict[str, Any]] = []
        conditional: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []

        for doc in documents:
            # Check if document has conditional logic
            condition = doc.get("condition")
            if condition and isinstance(condition, dict):
                # Evaluate condition against profile answers
                is_required = self._evaluate_condition(condition, profile_answers)
                if is_required:
                    required.append(self._format_document(doc, "required"))
                else:
                    excluded.append(self._format_document(doc, "excluded"))
            else:
                # Default: if mandatory flag, require; otherwise conditional
                if doc.get("mandatory", True):
                    required.append(self._format_document(doc, "required"))
                else:
                    conditional.append(self._format_document(doc, "conditional"))

        return {
            "required": required,
            "conditional": conditional,
            "excluded": excluded,
            "total_required": len(required),
            "total_conditional": len(conditional),
            "disclaimer": self._build_disclaimer(required, conditional),
        }

    def get_application_guide(
        self,
        scheme_payload: dict[str, Any],
        profile_answers: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a step-by-step application guide.

        Args:
            scheme_payload: The scheme's payload dict.
            profile_answers: The citizen's profile answers.

        Returns:
            A structured guide with:
                - steps: list of application steps
                - department: recommended department/office
                - official_url: application portal URL
                - documents_needed: summary of required docs
        """
        steps = self._extract_application_steps(scheme_payload)
        department = self._extract_department(scheme_payload)

        return {
            "steps": steps,
            "department": department,
            "official_url": self._extract_application_url(scheme_payload),
            "documents_needed": self._build_documents_summary(scheme_payload),
            "sources": self._extract_sources(scheme_payload),
        }

    def _extract_documents(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract documents from scheme payload."""
        documents = []

        # Try multiple possible locations for documents
        doc_list = (
            payload.get("documents")
            or payload.get("required_documents")
            or payload.get("documents_required")
            or []
        )

        if isinstance(doc_list, list):
            for doc in doc_list:
                if isinstance(doc, dict):
                    documents.append(doc)
                elif isinstance(doc, str):
                    documents.append({"name": doc, "mandatory": True})

        return documents

    def _extract_application_steps(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract application steps from scheme payload."""
        steps = []

        step_list = (
            payload.get("application_steps")
            or payload.get("steps")
            or payload.get("application_process")
            or []
        )

        if isinstance(step_list, list):
            for i, step in enumerate(step_list, 1):
                if isinstance(step, dict):
                    steps.append(
                        {
                            "step": i,
                            "instruction": step.get("instruction", step.get("text", "")),
                            "department": step.get("department"),
                            "office": step.get("office"),
                        }
                    )
                elif isinstance(step, str):
                    steps.append(
                        {
                            "step": i,
                            "instruction": step,
                            "department": None,
                            "office": None,
                        }
                    )

        return steps

    def _extract_department(self, payload: dict[str, Any]) -> str | None:
        """Extract department/office from scheme payload."""
        return (
            payload.get("department")
            or payload.get("department_name")
            or payload.get("implementing_department")
            or None
        )

    def _extract_application_url(self, payload: dict[str, Any]) -> str | None:
        """Extract application URL from scheme payload."""
        return (
            payload.get("application_url")
            or payload.get("apply_url")
            or payload.get("portal_url")
            or None
        )

    def _extract_sources(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract source references from scheme payload."""
        sources = []

        source_list = payload.get("sources") or payload.get("evidence") or []

        if isinstance(source_list, list):
            for src in source_list:
                if isinstance(src, dict):
                    sources.append(
                        {
                            "title": src.get("title"),
                            "url": src.get("url"),
                            "type": src.get("source_type"),
                        }
                    )
                elif isinstance(src, str):
                    sources.append({"title": src, "url": None, "type": None})

        return sources

    def _evaluate_condition(
        self,
        condition: dict[str, Any],
        profile_answers: dict[str, Any],
    ) -> bool:
        """Evaluate a document condition against profile answers.

        Supports simple conditions like:
        - {"field": "is_farmer", "equals": true}
        - {"field": "occupation", "in": ["farmer", "daily_wage"]}
        - {"field": "landholding_acres", "lte": 2}
        """
        field = condition.get("field")
        if not field:
            return True

        value = profile_answers.get(field)
        if value is None or value == "prefer_not_to_say":
            # Missing data → assume not required to be safe
            return False

        equals = condition.get("equals")
        if equals is not None:
            return value == equals

        in_values = condition.get("in")
        if in_values is not None:
            return value in in_values

        lte = condition.get("lte")
        if lte is not None and isinstance(value, (int, float)):
            return value <= lte

        gte = condition.get("gte")
        if gte is not None and isinstance(value, (int, float)):
            return value >= gte

        # Default: if condition is defined but unparseable, include
        return True

    def _format_document(self, doc: dict[str, Any], status: str) -> dict[str, Any]:
        """Format a document entry for the checklist."""
        return {
            "name": doc.get("name", doc.get("title", "Unknown document")),
            "description": doc.get("description", doc.get("notes", "")),
            "mandatory": doc.get("mandatory", True),
            "conditional": doc.get("conditional", False),
            "source": doc.get("source", None),
            "status": status,
            "explanation": self._build_document_explanation(doc, status),
        }

    def _build_document_explanation(
        self,
        doc: dict[str, Any],
        status: str,
    ) -> str:
        """Build an explanation for why a document is required."""
        if status == "excluded":
            return "This document is not required based on your profile."

        name = doc.get("name", doc.get("title", "document"))
        purpose = doc.get("purpose", doc.get("description", ""))

        if purpose:
            return f"Required to verify: {purpose}"
        return f"Official proof of {name.lower()}"

    def _build_disclaimer(
        self,
        required: list[dict[str, Any]],
        conditional: list[dict[str, Any]],
    ) -> str:
        """Build a standard disclaimer for the checklist."""
        count = len(required)
        if count == 0:
            return "No documents are required for this scheme."
        if count == 1:
            return (
                "You must provide the document listed above. "
                "Additional documents may be requested by the department."
            )
        return (
            f"You must provide these {count} documents. "
            "Additional documents may be requested by the department based on your application."
        )

    def _build_documents_summary(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Build a summary of documents needed for the application."""
        documents = self._extract_documents(payload)
        summary = []

        for doc in documents:
            name = doc.get("name", doc.get("title", "Unknown document"))
            mandatory = doc.get("mandatory", True)

            if mandatory:
                summary.append(
                    {
                        "name": name,
                        "type": "mandatory",
                        "note": doc.get("description", ""),
                    }
                )
            else:
                summary.append(
                    {
                        "name": name,
                        "type": "optional",
                        "note": doc.get("description", ""),
                    }
                )

        return summary
