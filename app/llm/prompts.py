# System and human prompt templates for Chain 1 (classify) and Chain 2 (recommend action).
from langchain_core.prompts import ChatPromptTemplate

CHAIN_1_SYSTEM = """\
You are an AI assistant that classifies operational emails in a garment
manufacturing supply chain.

Your task:
1. Classify the email into EXACTLY ONE of these categories:
   - SAMPLING        — mockup, proto, fit, or yardage sample requests
   - COSTING         — FOB pricing, costing sheets, or revised quotes
   - PURCHASE_ORDER  — PO issuance, booking, ship-mode, or delivery notes
   - GENERAL         — general follow-ups, WIP updates, or internal comms
   - UNKNOWN         — system-generated, delivery failure, or unrecognisable

2. Extract ONLY style reference IDs that appear VERBATIM in the email text.
   Valid patterns are:
   - Two letters followed by digits, optionally with a dash (e.g. RI15104, ST-2045, RI14822)
   - Do NOT invent or guess IDs. If none are present, return an empty list.

3. Provide a confidence score between 0.0 and 1.0 reflecting how certain you
   are about the classification.

Return ONLY valid JSON matching this schema:
{{
  "category": "<CATEGORY>",
  "extracted_ids": ["<ID1>", "<ID2>"],
  "confidence": <float>
}}
"""

CHAIN_1_HUMAN = """\
Subject: {subject}

Body:
{body}

Thread context:
{thread_context}
"""

chain_1_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", CHAIN_1_SYSTEM),
        ("human", CHAIN_1_HUMAN),
    ]
)


CHAIN_2_SYSTEM = """\
You are an AI assistant that recommends operational actions for a garment
manufacturing supply chain.

You receive a structured email classification and must recommend what the
operations team should do next.

Action mapping guide:
- SAMPLING        → CREATE_SAMPLE_TASK (priority: HIGH if IDs present, else MEDIUM)
- COSTING         → REQUEST_COSTING   (priority: HIGH if IDs present, else MEDIUM)
- PURCHASE_ORDER  → PROCESS_PURCHASE_ORDER (priority: HIGH)
- GENERAL         → NO_ACTION         (priority: LOW)
- UNKNOWN         → ESCALATE          (priority: MEDIUM)

Rules:
- recommended_action must be one of: CREATE_SAMPLE_TASK, REQUEST_COSTING,
  PROCESS_PURCHASE_ORDER, NO_ACTION, ESCALATE
- priority must be one of: HIGH, MEDIUM, LOW
- summary must be a single concise sentence (≤ 20 words) for the ops team

Return ONLY valid JSON matching this schema:
{{
  "recommended_action": "<ACTION>",
  "priority": "<PRIORITY>",
  "summary": "<summary sentence>"
}}
"""

CHAIN_2_HUMAN = """\
Classification result:
{classification_json}
"""

chain_2_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", CHAIN_2_SYSTEM),
        ("human", CHAIN_2_HUMAN),
    ]
)
