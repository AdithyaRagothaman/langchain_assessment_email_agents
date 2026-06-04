# Connects Chain 1 and Chain 2 into a single pipeline and wraps errors cleanly.
from __future__ import annotations

from langchain_groq import ChatGroq

from app.config import settings
from app.llm.chains import build_chain_1, build_chain_2
from app.llm.models import EmailInput, PipelineResult


class EmailPipelineError(Exception):
    """Raised when either chain fails during processing."""


class EmailPipeline:
    """Wires Chain 1 and Chain 2 together into a single callable pipeline."""

    def __init__(self) -> None:
        llm = ChatGroq(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            api_key=settings.groq_api_key or None,  # type: ignore[arg-type]
        )
        self._chain_1 = build_chain_1(llm)
        self._chain_2 = build_chain_2(llm)

    def run(self, subject: str, body: str, thread_context: str = "") -> PipelineResult:
        """Run an email through both chains and return the combined result."""
        email_input = EmailInput(subject=subject, body=body, thread_context=thread_context)

        try:
            classification = self._chain_1.invoke(email_input.model_dump())
        except Exception as exc:
            raise EmailPipelineError(f"Chain 1 (classification) failed: {exc}") from exc

        try:
            action = self._chain_2.invoke(classification)
        except Exception as exc:
            raise EmailPipelineError(f"Chain 2 (action recommendation) failed: {exc}") from exc

        return PipelineResult(classification=classification, action=action)
