# Builds Chain 1 (classify + extract IDs) and Chain 2 (recommend action) as LangChain Runnables.
from __future__ import annotations

import logging
from langchain_core.language_models import BaseLanguageModel
from langchain_core.runnables import Runnable, RunnableLambda

from app.llm.models import ClassificationResult, ActionResult
from app.llm.parser import ClassificationOutputParser, ActionOutputParser
from app.llm.prompts import chain_1_prompt, chain_2_prompt

logger = logging.getLogger(__name__)


def build_chain_1(llm: BaseLanguageModel) -> Runnable:
    """Build Chain 1 — classifies the email and extracts style IDs.

    The inner function is intentionally named _run_chain_1 (not the generic
    _run) so that stack traces clearly identify which chain raised an error.
    """

    def _run_chain_1(inputs: dict) -> ClassificationResult:
        email_text = " ".join([
            inputs.get("subject", ""),
            inputs.get("body", ""),
            inputs.get("thread_context", ""),
        ])

        logger.debug("Chain 1 | invoking LLM | subject=%r", inputs.get("subject", ""))
        messages = chain_1_prompt.format_messages(**inputs)
        response = llm.invoke(messages)

        raw_text: str = response.content if hasattr(response, "content") else str(response)
        logger.debug("Chain 1 | raw LLM response: %s", raw_text)

        result = ClassificationOutputParser(email_text=email_text).parse(raw_text)
        logger.info(
            "Chain 1 | category=%s | ids=%s | confidence=%.2f",
            result.category,
            result.extracted_ids,
            result.confidence,
        )
        return result

    return RunnableLambda(_run_chain_1)


def build_chain_2(llm: BaseLanguageModel) -> Runnable:
    """Build Chain 2 — takes Chain 1's result and recommends what action to take.

    The inner function is intentionally named _run_chain_2 (not the generic
    _run) so that stack traces clearly identify which chain raised an error.
    """

    def _run_chain_2(classification: ClassificationResult) -> ActionResult:
        logger.debug("Chain 2 | invoking LLM | category=%s", classification.category)
        messages = chain_2_prompt.format_messages(
            classification_json=classification.model_dump_json(indent=2)
        )
        response = llm.invoke(messages)

        raw_text: str = response.content if hasattr(response, "content") else str(response)
        logger.debug("Chain 2 | raw LLM response: %s", raw_text)

        result = ActionOutputParser().parse(raw_text)
        logger.info(
            "Chain 2 | action=%s | priority=%s",
            result.recommended_action,
            result.priority,
        )
        return result

    return RunnableLambda(_run_chain_2)
