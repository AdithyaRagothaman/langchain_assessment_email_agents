# FastAPI routes — /classify runs the email through the pipeline, /health checks the service is up.
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.llm.models import PipelineResult
from app.services.email_pipeline import EmailPipeline, EmailPipelineError

router = APIRouter(prefix="/api/v1", tags=["email-classification"])

_pipeline = EmailPipeline()


class ClassifyRequest(BaseModel):
    subject: str
    body: str
    thread_context: str = ""


class ClassifyResponse(BaseModel):
    classification: dict
    action: dict


@router.post("/classify", response_model=ClassifyResponse, status_code=status.HTTP_200_OK)
def classify_email(request: ClassifyRequest) -> ClassifyResponse:
    """Run an email through Chain 1 → Chain 2 and return the result."""
    try:
        result: PipelineResult = _pipeline.run(
            subject=request.subject,
            body=request.body,
            thread_context=request.thread_context,
        )
    except EmailPipelineError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {exc}") from exc

    return ClassifyResponse(
        classification=result.classification.model_dump(),
        action=result.action.model_dump(),
    )


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}
