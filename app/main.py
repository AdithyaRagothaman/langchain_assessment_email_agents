"""
FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload --port 8000

Then open:
    http://localhost:8000/docs  (Swagger UI)
    http://localhost:8000/redoc (ReDoc UI)
"""

from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(
    title="Email Classification API",
    description=(
        "LangChain-powered email classification and action recommendation "
        "for garment manufacturing supply-chain operations."
    ),
    version="1.0.0",
)

app.include_router(router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """Redirect hint for the root path."""
    return {"message": "Visit /docs for the API documentation."}
