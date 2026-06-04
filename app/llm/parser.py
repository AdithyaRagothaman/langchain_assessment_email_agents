# Parses LLM JSON output for both chains and validates style IDs against the original email text.
from __future__ import annotations

import re
import json
from typing import Any

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import BaseOutputParser

from app.llm.models import ClassificationResult, ActionResult

_STYLE_ID_PATTERN = re.compile(r"\b[A-Z]{2}-?\d{4,}\b")


def validate_style_ids(raw_ids: list[str], email_text: str) -> list[str]:
    """
    Keep only IDs that match the style ID pattern AND appear verbatim in the email.
    This is the second line of defence against hallucinated style IDs.
    """
    email_text_upper = email_text.upper()
    validated: list[str] = []
    seen: set[str] = set()

    for raw_id in raw_ids:
        normalised = raw_id.strip().upper()
        if not _STYLE_ID_PATTERN.fullmatch(normalised):
            continue
        if normalised not in email_text_upper:
            continue
        if normalised not in seen:
            seen.add(normalised)
            validated.append(raw_id.strip())

    return validated


def extract_style_ids_from_text(email_text: str) -> list[str]:
    """Scan raw text and return all style IDs found — useful as a standalone utility."""
    return _STYLE_ID_PATTERN.findall(email_text.upper())


class ClassificationOutputParser(BaseOutputParser[ClassificationResult]):
    """Parses the LLM's JSON response for Chain 1 and validates it with Pydantic."""

    email_text: str = ""

    @property
    def _type(self) -> str:
        return "classification_output_parser"

    def parse(self, text: str) -> ClassificationResult:
        raw = self._extract_json(text)
        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OutputParserException(
                f"Chain 1 returned invalid JSON: {exc}\nRaw output:\n{text}"
            ) from exc

        data["extracted_ids"] = validate_style_ids(
            data.get("extracted_ids", []), self.email_text
        )

        try:
            return ClassificationResult(**data)
        except Exception as exc:
            raise OutputParserException(
                f"Chain 1 output failed Pydantic validation: {exc}\nData: {data}"
            ) from exc

    @staticmethod
    def _extract_json(text: str) -> str:
        """Pull out the first JSON object from the LLM's response text."""
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise OutputParserException(f"No JSON object found in Chain 1 output:\n{text}")
        return text[start:end]

    def get_format_instructions(self) -> str:
        return "Return only a JSON object with keys: category, extracted_ids, confidence."


class ActionOutputParser(BaseOutputParser[ActionResult]):
    """Parses the LLM's JSON response for Chain 2 and validates it with Pydantic."""

    @property
    def _type(self) -> str:
        return "action_output_parser"

    def parse(self, text: str) -> ActionResult:
        raw = self._extract_json(text)
        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OutputParserException(
                f"Chain 2 returned invalid JSON: {exc}\nRaw output:\n{text}"
            ) from exc

        try:
            return ActionResult(**data)
        except Exception as exc:
            raise OutputParserException(
                f"Chain 2 output failed Pydantic validation: {exc}\nData: {data}"
            ) from exc

    @staticmethod
    def _extract_json(text: str) -> str:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise OutputParserException(f"No JSON object found in Chain 2 output:\n{text}")
        return text[start:end]

    def get_format_instructions(self) -> str:
        return "Return only a JSON object with keys: recommended_action, priority, summary."
