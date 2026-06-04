# Solution — LangChain Email Classification Chains

---

## Quick Start

```bash
# 1. Clone and enter the project
cd langchain_assessment_email_agents

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and set your GROQ_API_KEY

# 5. Run the test suite (no API key required — all LLM calls are mocked)
pytest tests/ -v

# 6. Start the FastAPI server
uvicorn app.main:app --reload --port 8000
# Swagger UI → http://localhost:8000/docs
```

---

## Architecture

### Data Flow

```
POST /api/v1/classify
  { subject, body, thread_context }
        │
        ▼
[EmailInput — Pydantic validation]
        │
        ▼
┌─────────────────────────────────────────────┐
│  Chain 1 — Classify + Extract               │
│                                             │
│  ChatPromptTemplate                         │
│    → llm.invoke()  (Groq LLaMA 3.3 70B)    │
│    → ClassificationOutputParser             │
│        ├─ _extract_json()                   │
│        ├─ validate_style_ids() [regex]      │
│        └─ ClassificationResult (Pydantic)   │
└─────────────────────────────────────────────┘
        │
        ▼  ClassificationResult
           { category, extracted_ids, confidence }
        │
        ▼
┌─────────────────────────────────────────────┐
│  Chain 2 — Recommend Action                 │
│                                             │
│  ChatPromptTemplate                         │
│    → llm.invoke()  (same Groq instance)     │
│    → ActionOutputParser                     │
│        ├─ _extract_json()                   │
│        └─ ActionResult (Pydantic)           │
└─────────────────────────────────────────────┘
        │
        ▼  PipelineResult
           { classification, action }
        │
        ▼
HTTP 200 JSON Response
```

### Folder Structure

```
app/
├── llm/
│   ├── models.py        ← All Pydantic input/output models and enums
│   ├── prompts.py       ← ChatPromptTemplate definitions for Chain 1 & 2
│   ├── chains.py        ← Chain 1 & Chain 2 factory functions (RunnableLambda)
│   └── parser.py        ← Custom output parsers + regex hallucination validator
├── services/
│   └── email_pipeline.py  ← Orchestrates Chain 1 → Chain 2, error handling
├── api/
│   └── routes.py        ← FastAPI router: POST /classify, GET /health
├── config.py            ← Pydantic BaseSettings (reads .env)
└── main.py              ← FastAPI application entry point

tests/
└── test_chains.py       ← 10 pytest test cases, all LLM calls mocked

fixtures/
└── sample_emails.json   ← 10 real-inspired sample emails across all categories

docs/
└── INPUT_FORMAT.md      ← Production email → chain input field mapping
```

---

## Why Two Chains Instead of One

| Concern | One Chain | Two Chains (this solution) |
|---|---|---|
| **Testability** | Must test classification + action together | Chain 1 and Chain 2 tested independently |
| **Reusability** | Monolithic — cannot reuse classification alone | Chain 1 can be used in any context |
| **Replaceability** | Changing action logic risks breaking classification | Swap Chain 2 without touching Chain 1 |
| **Debuggability** | Hard to trace which step produced bad output | Clear intermediate `ClassificationResult` to inspect |
| **Extension** | Requires rewriting the whole chain | Add a new category by editing enums + prompt only |

The intermediate `ClassificationResult` object is also a first-class audit artifact — useful for logging, monitoring, and future routing decisions.

---

## LangChain Structure & Composition

Both chains are built using `RunnableLambda`, which wraps a standard Python function into a LangChain-compatible `Runnable`.

**Why `RunnableLambda` over the standard `prompt | llm | parser` pipe?**

Chain 1's parser requires the **original email text** to run the hallucination check. In a standard LCEL pipe, threading this extra variable requires `RunnablePassthrough` and `RunnableParallel`, adding complexity. With `RunnableLambda`, the variable is available naturally as a Python closure:

```python
def build_chain_1(llm: BaseLanguageModel) -> Runnable:

    def _run_chain_1(inputs: dict) -> ClassificationResult:
        email_text = " ".join([inputs["subject"], inputs["body"], inputs["thread_context"]])

        messages = chain_1_prompt.format_messages(**inputs)
        response = llm.invoke(messages)
        raw_text = response.content

        # email_text passed sideways into the parser for regex cross-check
        return ClassificationOutputParser(email_text=email_text).parse(raw_text)

    return RunnableLambda(_run_chain_1)
```

**Chain composition in `EmailPipeline.run()`:**

```python
classification = self._chain_1.invoke(email_input.model_dump())
action         = self._chain_2.invoke(classification)
return PipelineResult(classification=classification, action=action)
```

Chain 1 output (`ClassificationResult`) is passed directly as input to Chain 2. The chains are independently buildable and testable, but compose cleanly in the pipeline.

---

## Structured Output Validation — Pydantic Strategy

Every input and output in the system is a Pydantic v2 model:

| Model | Layer | Purpose |
|---|---|---|
| `EmailInput` | Entry | Validates `subject`, `body`, `thread_context` before touching LLM |
| `ClassificationResult` | Chain 1 output | `EmailCategory` enum, `extracted_ids` list, `confidence` in [0.0, 1.0] |
| `ActionResult` | Chain 2 output | `RecommendedAction` enum, `ActionPriority` enum, `summary` string |
| `PipelineResult` | API layer | Bundles both chain results for the HTTP response |

**Enforcement example — confidence range:**
```python
confidence: Annotated[float, Field(ge=0.0, le=1.0)]
```
If the LLM returns `1.5`, Pydantic raises `ValidationError` before it ever reaches any business logic.

**Enum enforcement:**
```python
class EmailCategory(str, Enum):
    SAMPLING = "SAMPLING"
    COSTING  = "COSTING"
    ...
```
If the LLM invents a category like `"FABRIC_REQUEST"`, Pydantic rejects it immediately.

---

## Hallucination Prevention — Two-Layer Defence

LLMs can fabricate Style IDs that never appeared in the email. Two layers prevent this:

**Layer 1 — Prompt instruction:**
> *"Extract ONLY style reference IDs that appear VERBATIM in the email text. Do NOT invent or guess IDs."*

**Layer 2 — Regex cross-check in `parser.py`:**

```python
_STYLE_ID_PATTERN = re.compile(r"\b[A-Z]{2}-?\d{4,}\b")

def validate_style_ids(raw_ids: list[str], email_text: str) -> list[str]:
    email_text_upper = email_text.upper()
    validated = []
    for raw_id in raw_ids:
        normalised = raw_id.strip().upper()
        if not _STYLE_ID_PATTERN.fullmatch(normalised):   # format check
            continue
        if normalised not in email_text_upper:             # existence check
            continue
        validated.append(raw_id.strip())
    return validated
```

Every ID the LLM returns is:
1. Checked against the regex pattern (`[A-Z]{2}-?\d{4,}`)
2. Verified to exist **verbatim** in `subject + body + thread_context`

A hallucinated `"RI99999"` in an email that never mentions it is always silently dropped.

---

## Test Coverage & Correctness

All 10 test cases run without any API key — LLM calls are replaced by `MagicMock`.

```bash
pytest tests/ -v
```

| # | Test | What it verifies |
|---|---|---|
| 1 | `test_validate_style_ids_passes_valid_ids` | Valid IDs present in email text are kept |
| 2 | `test_validate_style_ids_strips_hallucinated_ids` | IDs absent from email text are dropped |
| 3 | `test_validate_style_ids_mixed` | Valid and hallucinated IDs handled in one call |
| 4 | `test_chain_1_sampling_classification` | Chain 1 correctly produces a `SAMPLING` result |
| 5 | `test_chain_1_general_no_ids` | Chain 1 returns `GENERAL` with empty `extracted_ids` |
| 6 | `test_chain_1_purchase_order` | Chain 1 correctly produces `PURCHASE_ORDER` |
| 7 | `test_chain_1_costing_ids_from_context` | IDs in `thread_context` are extracted correctly |
| 8 | `test_chain_2_sampling_recommends_create_sample_task` | Chain 2 maps `SAMPLING` → `CREATE_SAMPLE_TASK` at `HIGH` |
| 9 | `test_chain_2_unknown_recommends_escalate` | Chain 2 maps `UNKNOWN` → `ESCALATE` at `MEDIUM` |
| 10 | `test_classification_parser_raises_on_invalid_json` | Parser raises `OutputParserException` on plain-text LLM output |

---

## API Reference (Bonus)

### `POST /api/v1/classify`

**Request:**
```json
{
  "subject": "Need mockup sample for RI15104",
  "body": "Please arrange mockup sample for RI15104 with trims.",
  "thread_context": "First order from this buyer."
}
```

**Response `200 OK`:**
```json
{
  "classification": {
    "category": "SAMPLING",
    "extracted_ids": ["RI15104"],
    "confidence": 0.95
  },
  "action": {
    "recommended_action": "CREATE_SAMPLE_TASK",
    "priority": "HIGH",
    "summary": "Buyer requested mockup sample for style RI15104."
  }
}
```

**Error responses:**
- `422` — LLM returned bad output (caught `EmailPipelineError`)
- `500` — Unexpected server error

### `GET /api/v1/health`

Returns `{"status": "ok"}` — used by Docker health checks and load balancers.

---

## Docker (Bonus)

```bash
# Build
docker build -t email-classifier .

# Run (pass API key as env var)
docker run -p 8000:8000 -e GROQ_API_KEY=your_key_here email-classifier

# Or pass via .env file
docker run -p 8000:8000 --env-file .env email-classifier
```

The Dockerfile uses a **multi-stage build**:
- Stage 1 (builder): installs all packages including build tools
- Stage 2 (runtime): copies only the installed packages and `app/` source — no test files, no dev scripts, no build tools

The container runs as a non-root user and includes a health check on `/api/v1/health`.

---

## Integration into a Larger Pipeline

```python
from app.services.email_pipeline import EmailPipeline
from app.llm.models import RecommendedAction

pipeline = EmailPipeline()

result = pipeline.run(
    subject=email.subject,
    body=email.body,
    thread_context=email.thread_context,
)

match result.action.recommended_action:
    case RecommendedAction.CREATE_SAMPLE_TASK:
        task_service.create_sample_task(result)
    case RecommendedAction.REQUEST_COSTING:
        costing_service.open_request(result)
    case RecommendedAction.PROCESS_PURCHASE_ORDER:
        po_service.process(result)
    case RecommendedAction.ESCALATE:
        slack_service.alert_ops_team(result)
    case _:
        audit_log.record(result)
```

---

## Adding a New Category (e.g. `INSPECTION_REQUEST`)

1. Add to `EmailCategory` enum in `models.py`:
   ```python
   INSPECTION_REQUEST = "INSPECTION_REQUEST"
   ```
2. Add to `RecommendedAction` enum in `models.py`:
   ```python
   SCHEDULE_INSPECTION = "SCHEDULE_INSPECTION"
   ```
3. Add one line to `CHAIN_2_SYSTEM` in `prompts.py`:
   ```
   - INSPECTION_REQUEST → SCHEDULE_INSPECTION (priority: HIGH)
   ```
4. Add test cases to `tests/test_chains.py`.

**No chain wiring changes required.** This is the SOLID Open/Closed Principle — open for extension, closed for modification.

---

## Proposed Shared Order-State Model (Design Notes)

> No code required. This section proposes how order state should be persisted when multiple agents interact with the same order over time.

### The Problem

Multiple agents (email classifier, sampling agent, costing agent, PO agent) all interact with the same order at different points in time. Each agent must be able to:
- Read the current order state without blocking other agents.
- Update only the fields it is responsible for.
- Never overwrite updates made by a concurrent agent.

### Proposed Schema

```json
{
  "order_id": "ORD-2026-001",
  "style_refs": ["RI15104"],
  "buyer": "Garan",
  "vendor": "BestCorp",
  "status": "SAMPLING",
  "checkpoints": {
    "classification_done": true,
    "sample_task_created": true,
    "costing_submitted": false,
    "po_issued": false,
    "shipped": false
  },
  "ownership": {
    "classification": "email_classifier_agent",
    "sampling": "sampling_agent",
    "costing": null,
    "po": null
  },
  "history": [
    {
      "agent": "email_classifier_agent",
      "action": "CLASSIFIED",
      "timestamp": "2026-06-02T10:00:00Z",
      "payload": { "category": "SAMPLING", "confidence": 0.95 }
    }
  ],
  "version": 3,
  "updated_at": "2026-06-02T10:05:00Z"
}
```

### Update Rules

1. **Optimistic locking via `version`** — Each agent reads the current `version`, makes its changes, and writes back only if `version` has not changed. If it has, the agent re-reads and retries.

2. **Field ownership** — Each agent writes only to its designated `ownership` slot. No agent can modify another agent's fields.

3. **Append-only `history`** — All updates are appended, never deleted. This gives a complete audit trail across all agents.

4. **Atomic writes** — Use a database transaction or compare-and-swap (CAS) to guarantee read-modify-write is atomic.

5. **Future fields from techpack/client docs:**
   - `crd` — Critical Request Date
   - `target_fob` — target FOB price from buyer
   - `fabric_status` — bulk fabric booking state
   - `inspection_date` — scheduled QC inspection
   - `tech_pack_url` — link to buyer's tech pack PDF

### Recommended Storage

| Use case | Technology |
|---|---|
| Production (ACID guarantees) | PostgreSQL with row-level locking |
| High-throughput / low-latency | Redis with `WATCH/MULTI/EXEC` (CAS) |
| Simple prototyping | SQLite with SQLAlchemy |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Groq API key |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Model name |
| `LLM_TEMPERATURE` | `0.0` | Sampling temperature (0 = deterministic) |
