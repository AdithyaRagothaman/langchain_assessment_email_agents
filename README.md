# Take-Home Assignment: LangChain Email Classification Chains

| | |
| --- | --- |
| **Duration** | 48 hours |
| **Goal** | Build composable LangChain chains to classify operational emails and extract structured metadata. |

---

## The Problem

We receive emails from buyers and vendors in a manufacturing supply chain. Each email requires:

1. **Classification** — what type of operational request is this?
2. **Extraction** — what key identifiers are mentioned?
3. **Action recommendation** — what should happen next?

Currently, these are done as manual LLM calls. Your task is to build **reusable LangChain chains** that can be composed together and tested independently.

---

## What You're Building

**Two connected LangChain chains:**

```
Raw Email → [Chain 1: Classify + Extract] → Intermediate Result
                                                      ↓
                                      [Chain 2: Recommend Action]
                                                     ↓
                                               Final Result
```

---

## Examples

### Example 1: Sampling Request

**Input**

```json
{
  "subject": "Need mockup sample for RI15104",
  "body": "Hi, please arrange mockup sample for RI15104 with trims. Thanks.",
  "thread_context": "First order from this buyer."
}
```

**Expected Chain 1 output**

```json
{
  "category": "SAMPLING",
  "extracted_ids": ["RI15104"],
  "confidence": 0.95
}
```

**Expected Chain 2 output**

```json
{
  "recommended_action": "CREATE_SAMPLE_TASK",
  "priority": "HIGH",
  "summary": "Buyer requested mockup sample for style RI15104."
}
```

---

### Example 2: General Follow-up

**Input**

```json
{
  "subject": "Following up",
  "body": "Any update on the previous discussion?",
  "thread_context": "Previous context about a costing discussion."
}
```

**Expected Chain 1 output**

```json
{
  "category": "GENERAL",
  "extracted_ids": [],
  "confidence": 0.88
}
```

**Expected Chain 2 output**

```json
{
  "recommended_action": "NO_ACTION",
  "priority": "LOW",
  "summary": "General follow-up, no immediate action needed."
}
```

---

## Requirements

### Chain 1: Classification + Extraction

- Classify email into: `SAMPLING`, `COSTING`, `PURCHASE_ORDER`, `GENERAL`, `UNKNOWN`
- Extract **style reference IDs** (patterns like `RI15104`, `ST-2045`)
- Return confidence score (0.0–1.0)
- Use **Pydantic** for output validation
- Prevent hallucinated extractions (validate patterns)

### Chain 2: Action Recommendation

- Takes Chain 1 output as input (demonstrates composition)
- Map classification + extracted IDs to recommended actions
- Provide priority and summary for ops teams
- Also use **Pydantic** for structured output

### General Constraints

- Use **LangChain** (not raw API calls)
- Write **at least 4 test cases** covering different scenarios
- Include a **README** explaining your approach
- Show how this integrates into an existing email pipeline

---

## Deliverables

- [ ] LangChain chain implementation
- [ ] Pydantic models for all inputs/outputs
- [ ] Test cases (4+, with sample emails)
- [ ] README with:
  - How to run the chains
  - Why you structured them this way (chain composition, reusability)
  - How to integrate into a larger pipeline
- [ ] Bonus: FastAPI endpoint or database persistence

---

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Create your project structure (suggested starting point)
mkdir -p app/llm
touch app/llm/chains.py
touch app/llm/models.py
mkdir tests
touch tests/test_chains.py
```

You choose the rest of the layout. Build everything from scratch.

---

## Test Inputs

Ten sample emails are provided in `fixtures/sample_emails.json`. Each entry
has the three fields your chains should accept:

- `subject`
- `body`
- `thread_context`

These are adapted from real production cleaned emails and thread artifacts.
See `docs/INPUT_FORMAT.md` for how production JSON maps to this shape.

The `id` and `source_inspiration` fields are for your reference only — do
**not** pass them into the chains.

Use at least 4 of these in your test suite; you may add your own cases too.

---

## Questions to Think About

1. Why build two separate chains instead of one?
2. How do you prevent the LLM from hallucinating style reference IDs?
3. How would you add a new email type (e.g., `INSPECTION_REQUEST`) without rewriting the chains?
4. How do you test these chains without calling the LLM API every time?

---

## Evaluation

We'll assess:

- LangChain structure & composition
- Structured output validation
- Test coverage & correctness
- Code clarity & integration feasibility
