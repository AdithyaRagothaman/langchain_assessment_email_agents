from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.llm.models import (
    ActionPriority,
    ClassificationResult,
    EmailCategory,
    RecommendedAction,
)
from app.llm.parser import (
    ActionOutputParser,
    ClassificationOutputParser,
    validate_style_ids,
)
from app.llm.chains import build_chain_1, build_chain_2


# --- Helpers ---

def make_mock_llm(response_content: str) -> MagicMock:
    """Return a mock LLM that replies with the given JSON string."""
    msg = MagicMock()
    msg.content = response_content
    llm = MagicMock()
    llm.invoke.return_value = msg
    return llm


# --- Tests ---

def test_validate_style_ids_passes_valid_ids():
    """IDs present in the email text should pass through."""
    result = validate_style_ids(["RI15104"], "Please arrange mockup sample for RI15104.")
    assert result == ["RI15104"]


def test_validate_style_ids_strips_hallucinated_ids():
    """IDs not found in the email text should be dropped."""
    result = validate_style_ids(["RI99999", "ST-1234"], "Any update on the previous discussion?")
    assert result == []


def test_validate_style_ids_mixed():
    """Only ST-2045 is in the text — the other two should be stripped."""
    result = validate_style_ids(
        ["ST-2045", "RI99999", "FP-0001"],
        "RE: S27 FM Sample Yardage Request - ST-2045",
    )
    assert "ST-2045" in result
    assert "RI99999" not in result
    assert "FP-0001" not in result


def test_chain_1_sampling_classification():
    """Chain 1 should classify a mockup request as SAMPLING and extract RI15104."""
    llm = make_mock_llm(json.dumps({"category": "SAMPLING", "extracted_ids": ["RI15104"], "confidence": 0.95}))
    result: ClassificationResult = build_chain_1(llm).invoke({
        "subject": "Need mockup sample for RI15104",
        "body": "Please arrange mockup sample for RI15104 with trims.",
        "thread_context": "First order from this buyer.",
    })
    assert result.category == EmailCategory.SAMPLING
    assert "RI15104" in result.extracted_ids
    assert result.confidence == pytest.approx(0.95)


def test_chain_1_general_no_ids():
    """A vague follow-up email should come back as GENERAL with no extracted IDs."""
    llm = make_mock_llm(json.dumps({"category": "GENERAL", "extracted_ids": [], "confidence": 0.88}))
    result: ClassificationResult = build_chain_1(llm).invoke({
        "subject": "Following up",
        "body": "Any update on the previous discussion?",
        "thread_context": "Previous context about a costing discussion.",
    })
    assert result.category == EmailCategory.GENERAL
    assert result.extracted_ids == []


def test_chain_1_purchase_order():
    """A PO booking email should be classified as PURCHASE_ORDER."""
    llm = make_mock_llm(json.dumps({"category": "PURCHASE_ORDER", "extracted_ids": [], "confidence": 0.92}))
    result: ClassificationResult = build_chain_1(llm).invoke({
        "subject": "RE: PO# 234917 - Not Reflected into GTN Portal",
        "body": "Pls allow me to share updated PO with updating ship mode.",
        "thread_context": "Buyer reported PO not reflected on GTN portal.",
    })
    assert result.category == EmailCategory.PURCHASE_ORDER


def test_chain_1_costing_ids_from_context():
    """Chain 1 should extract IDs that appear in thread_context, not just the body."""
    llm = make_mock_llm(json.dumps({"category": "COSTING", "extracted_ids": ["ST-2045", "RI15201"], "confidence": 0.90}))
    result: ClassificationResult = build_chain_1(llm).invoke({
        "subject": "RE: Revised costing submission",
        "body": "Any update on the revised costing we discussed last week?",
        "thread_context": "Thread about ST-2045 and RI15201 costing for Fall 26 program.",
    })
    assert result.category == EmailCategory.COSTING
    assert "ST-2045" in result.extracted_ids
    assert "RI15201" in result.extracted_ids


def test_chain_2_sampling_recommends_create_sample_task():
    """SAMPLING with IDs should map to CREATE_SAMPLE_TASK at HIGH priority."""
    llm = make_mock_llm(json.dumps({
        "recommended_action": "CREATE_SAMPLE_TASK",
        "priority": "HIGH",
        "summary": "Buyer requested mockup sample for style RI15104.",
    }))
    result = build_chain_2(llm).invoke(
        ClassificationResult(category=EmailCategory.SAMPLING, extracted_ids=["RI15104"], confidence=0.95)
    )
    assert result.recommended_action == RecommendedAction.CREATE_SAMPLE_TASK
    assert result.priority == ActionPriority.HIGH


def test_chain_2_unknown_recommends_escalate():
    """UNKNOWN emails (e.g. mail delivery failures) should always escalate."""
    llm = make_mock_llm(json.dumps({
        "recommended_action": "ESCALATE",
        "priority": "MEDIUM",
        "summary": "Unrecognised system email; manual review required.",
    }))
    result = build_chain_2(llm).invoke(
        ClassificationResult(category=EmailCategory.UNKNOWN, extracted_ids=[], confidence=0.40)
    )
    assert result.recommended_action == RecommendedAction.ESCALATE
    assert result.priority == ActionPriority.MEDIUM


def test_classification_parser_raises_on_invalid_json():
    """Parser should raise OutputParserException when the LLM returns plain text instead of JSON."""
    from langchain_core.exceptions import OutputParserException
    parser = ClassificationOutputParser(email_text="some email text")
    with pytest.raises(OutputParserException):
        parser.parse("Sorry, I cannot classify this email.")
