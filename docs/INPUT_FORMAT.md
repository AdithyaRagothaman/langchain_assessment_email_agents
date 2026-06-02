# Input Format — Mapping Production Emails to Chain Input

The chains accept a flat JSON object with three string
fields. This is what interns should model as their `EmailInput` Pydantic schema.

```json
{
  "subject": "string",
  "body": "string",
  "thread_context": "string"
}
```

In the production Email Agent pipeline, these fields are derived from cleaned
email JSON and thread artifacts **after** IMAP fetch, MIME parse, and body
cleaning.

---

## Field mapping

| Chain input       | Production source |
|-------------------|-------------------|
| `subject`         | Cleaned email `subject` (plain string) |
| `body`            | Cleaned email `body.sections` joined with newlines. Omit signatures and image placeholders unless they carry meaning. |
| `thread_context`  | Prior messages in the thread, summarized or concatenated. Built from thread JSON (`primary_email` + `emails[]`) or inline `thread[]` on the cleaned email. Empty string when the email is the first message. |

---

## Cleaned email shape (simplified)

Production cleaned emails look like this:

```json
{
  "thread_ref_id": "th_20260508_132317_efc0f12692",
  "email_ref_id": "em_20260513_040036_8bb64e60b9",
  "subject": "RE: PO# 234917(3033031) - Not Reflected into GTN Portal",
  "from": { "name": "Inul Islam", "email": "Inul.Islam@deltagalilbd.com" },
  "body": {
    "sections": [
      "Hi Ravi,",
      "Pls allow me to share updated PO with updating ship mode.",
      "Pls confirm your receiving & confirm the booking ASAP."
    ],
    "signature": ["Thanks.", "Md. Inul Islam Chowdhury", "..."],
    "images": []
  }
}
```

**→ Chain input**

```json
{
  "subject": "RE: PO# 234917(3033031) - Not Reflected into GTN Portal",
  "body": "Hi Ravi,\nPls allow me to share updated PO with updating ship mode.\nPls confirm your receiving & confirm the booking ASAP.",
  "thread_context": "Earlier thread: buyer reported PO 234917 not visible on GTN portal; logistics team was looped in."
}
```

---

## Thread artifact shape (simplified)

Thread files provide prior-message context:

```json
{
  "thread_ref_id": "th_20260415_061908_c2c38e535e",
  "thread_subject": "wn fabric development - spring 27- testing",
  "primary_email": {
    "subject": "RE: WN Fabric Development - Spring 27- Testing",
    "body": ["Dear Jennifier,", "We require fabric wash test report...", "..."]
  },
  "emails": []
}
```

Use `thread_subject` and truncated prior `body` lines to build `thread_context`.
Keep it short (a few sentences) — the LLM does not need the full thread history.

---

## Style reference IDs

The assignment expects extraction of **style reference IDs** matching:

| Pattern     | Example  |
|-------------|----------|
| `RI` + digits | `RI15104` |
| `ST-` + digits | `ST-2045` |

Production emails also contain PO numbers, fabric codes, and buyer style numbers
that are **not** style refs for this assignment. Your validator should only
accept IDs matching the patterns above **and** present in the source text.

---

## Test fixtures

See `fixtures/sample_emails.json` for 10 ready-to-use inputs covering all
assignment categories. Each entry includes an `id` and `source_inspiration`
field for traceability — **do not pass those fields to the chains**; only
`subject`, `body`, and `thread_context` are chain input.
