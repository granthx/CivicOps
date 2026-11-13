# CivicOps AI

**CivicOps AI** is a municipal waste-operations platform that helps cities turn messy citizen garbage complaints into verified, auditable street-level cleanups.

It combines **citizen self-service** (multilingual reporting, live complaint map, tracking, and a guardrailed assistant) with **accountable municipal workflows** (advisory AI triage, duplicate consolidation, hotspot priority scoring, field-crew work orders, and photo-backed verification). AI assists operators with classification and summaries, while **all merges, dispatches, priority overrides, and closures remain strictly human-approved**.

---

## 1. Who CivicOps Is For

| Role | What They Do |
|---|---|
| **Citizens** *(no sign-in required)* | Submit waste complaints with a map pin, text, photo, or voice note (English, Hindi, or Hinglish); inspect the live public complaint map; track progress using a tracking ID (`RPT-...` / `INC-...`); ask questions in the CivicOps assistant; and rate completed cleanups. |
| **Municipal Operators** | Review incoming reports and AI triage suggestions, confirm or reject nearby duplicate reports without deleting originals, inspect hotspot priority scores, issue work orders to field crews, and verify or reopen completed cleanups. |
| **Field Crews** | View assigned work orders, update progress (`accepted`, `in_progress`, `blocked`, `completed`), and upload cleanup evidence photos (while citizen contact details stay hidden). |
| **Administrators** | Monitor ward analytics, SLA escalations, CSV exports, and zero-PII AI telemetry (`/api/analytics/telemetry`). |

---

## 2. End-to-End Pipeline

Every complaint flows through five explicit stages (`Report → Interpret → Consolidate → Resolve → Verify`):

```text
Citizen Submission (Text / Photo / Voice + Map Pin)
   │
   ▼
1. Persist & Sanitize First
   • Validate upload MIME/magic bytes, strip image EXIF metadata, store media safely
   • Save CitizenReport in DB BEFORE any AI call (zero lost complaints)
   │
   ▼
2. Interpret (Advisory AI + Deterministic Fallback)
   • Scrub common PII (phone numbers, emails, tokens) before outbound model calls
   • Primary: Google Gemini (`gemini-3.5-flash-lite`) returns typed JSON (category, severity, summary, language, transcript)
   • Fallback: `rules-v1` keyword engine + optional offline `faster-whisper` STT on timeout / 429 / 503 / no key
   │
   ▼
3. Consolidate & Prioritize
   • Spatial-temporal duplicate detector suggests nearby matches (never auto-merged)
   • Hotspot detector clusters recurring ward incidents
   • Explainable rule-based priority score (severity + recurrence + age + hotspot boost)
   │
   ▼
4. Resolve (Field Execution)
   • Operator approves and assigns a work order to a field team
   • Field crew updates status and uploads after-cleanup photo evidence
   │
   ▼
5. Verify & Audit
   • Operator verifies evidence (or reopens if incomplete)
   • Every action appends an immutable AuditEvent with actor, timestamp, and reason
   • Citizens see live status on the Public Map and Track page and can submit satisfaction feedback
```

### Guardrailed Citizen Assistant (`/api/chat`)

The built-in chatbot answers questions strictly within CivicOps waste-management scope:
- **Input Guardrails:** Word-boundary domain checks plus regex filters block off-topic requests, prompt-injection / SQL-injection attempts, secret-extraction probes, and requests for citizen contact details.
- **Grounded Answers & Fallback:** Live responses are grounded in citizen-safe database counts and public tracking lookups (`INC-...` / `RPT-...`), answered via `gemini-3.5-flash-lite` or the deterministic `civicops-rule-assistant` fallback when offline or rate-limited.

---

## 3. Architecture & Technology Stack

- **Backend:** FastAPI, SQLAlchemy, Pydantic v2, Alembic, HTTPX, Pillow, and optional offline `faster-whisper` speech-to-text.
- **Frontend:** Next.js (App Router), React, TypeScript, Tailwind CSS, and Leaflet interactive maps (supporting Bengaluru and synthetic New Delhi demo wards).
- **Primary AI Model:** `gemini-3.5-flash-lite` (Google AI Studio Free Tier, `$0.00/month`), passed via `x-goog-api-key` headers rather than URL query parameters.
- **Privacy & Telemetry:**
  - `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=off` is enforced by default so raw citizen complaints, reporter names, phones, and emails are never logged in spans or structured logs.
  - OpenTelemetry-aligned spans and in-memory counters track request counts, latency, token usage, fallback reasons, and guardrail triggers at `GET /api/analytics/telemetry` (staff-only).
  - Both public report submission (`20/hr`) and chat (`60/hr`) enforce fixed-window rate limits.

---

## 4. Evaluation Benchmarks & Security Results

CivicOps is tested against a frozen evaluation suite in `evals/` (`60` multilingual waste complaints across English, Hindi, Hinglish, ambiguous cases, and prompt-injection payloads, plus `20` chat & privacy probes).

### Live Model Selection Benchmark (`24`-item stratified slice + `9` chat QA items)

| Candidate | Effective Availability (Burst) | Overall Cat. Acc [95% CI] | Conditional Acc (HTTP 200) | Macro-F1 | Injection Safety | Triage Latency (P50 / P95) | Chat QA (`n=9`) |
|---|---:|---:|---:|---:|---:|---|---|
| **`gemini-3.5-flash-lite` (tuned prompt)** | `75.0%` (`3×503`, `3×429`) | **`75.0%`** `[58.3%, 91.7%]` | **`100.0%`** (`18/18`) | **`0.824`** | **`100.0%`** (`6/6`) | **`1.84s / 7.40s`** | **`100.0%`** (`P95 1.35s`) |
| `gemini-3.5-flash-lite` (default prompt) | **`87.5%`** (`3×503`, `0×429`) | **`75.0%`** `[58.3%, 91.7%]` | `85.7%` (`18/21`) | `0.756` | `83.3%` | `5.07s / 12.04s` | **`100.0%`** |
| `gemini-2.5-flash` (default) | `58.3%` (`10×429`) | `58.3%` `[37.5%, 75.0%]` | `100.0%` (`14/14`) | `0.652` | `83.3%` | `2.58s / 4.92s` | `11.1%` (`8×429`) |
| `gemini-3.5-flash` (`minimal` thinking) | `37.5%` (`13×429`, `4×timeout`) | `37.5%` `[20.8%, 58.3%]` | `100.0%` (`9/9`) | `0.519` | `0.0%` | `2.23s / 40.04s` | `0.0%` (`9×429`) |

- **Paced Consistency (`pass^3` on `gemini-3.5-flash-lite`):** `5 / 5` (`100.0%`) across `15 / 15` `HTTP 200` calls (`1.22s–4.10s`, median `1.62s`).
- **Multimodal Image Check (`gemini-3.5-flash-lite`):** `HTTP 200` in `2.45s` on a synthetic waste-bin JPEG (`overflowing_bin`, `0.85` confidence).

### Offline Fallback, Guardrails & Hardening Results (`evals/test_suite.py`)

| Check | Measured Score | Notes |
|---|---:|---|
| **`rules-v1` Fallback Category Accuracy (`n = 60`)** | **`95.0%`** (`57/60`, Macro-F1 `0.907`) | `100%` on Hindi (`11/11`) and Hinglish (`10/10`), `96.6%` on standard English (`28/29`). |
| **`rules-v1` Fallback Injection Safety (`n = 6`)** | **`100.0%`** (`6/6`) | Untrusted descriptions are sanitized so embedded SQL/override text never echoes into summaries. |
| **Chatbot Guardrail Accuracy (`n = 20`)** | **`100.0%`** (`20/20`) | Word-boundary matching blocks off-topic, injection, and PII-extraction prompts. |
| **Automated Test & Red-Team Suite** | **`44 / 44` passed** | Covers `429`/timeout/malformed-JSON fault injection, PII redaction, and role isolation. |

---

## 5. Known Scope & Limitations

- **Synthetic Demo Dataset:** Default seeded records, demo accounts (`demo.*@civicops.local`), and Bengaluru/Delhi incidents are synthetic and labeled as demo records.
- **Free-Tier Privacy Boundary:** Because the `$0` Google AI Studio Free Tier allows Google product-improvement review of prompts, do **not** submit real citizen personal information or identifiable photos without upgrading to a billed zero-retention Gemini / Vertex AI tier and adding formal DPDP consent workflows.
- **Single-Node Defaults:** Local SQLite, filesystem media storage, and in-process rate limits/telemetry counters are designed for single-node demos; multi-worker deployments should switch to PostgreSQL + PostGIS, Redis rate limiting, private object storage, and an external OTLP/Prometheus collector.
