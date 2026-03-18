# GraphCRM — Claude Working Instructions

This file contains binding instructions for Claude when working on the GraphCRM project. Follow these rules precisely in every conversation.

---

## 1. Before Writing Any Code

1. **Read the relevant existing file(s) first.** Never propose changes to code you haven't read.
2. **Check the phase** you are working in against `build-phases.md`. Understand which components exist before adding new ones.
3. **Confirm the Docker service is relevant** — e.g., if writing Neo4j queries, the `neo4j` service must be in `docker-compose.yml`.
4. **Do not scaffold the entire project in one shot unless explicitly asked.** Work phase by phase as described in `build-phases.md`.
5. **Debug before assuming.** If a flow appears broken, use `debug_pipeline` or `shell_plus` to inspect live data and call functions directly before changing any code. See `## Debugging` in `CLAUDE.md` for the full command reference. Prefer `debug_pipeline --event <type>` for end-to-end flow tests and `shell_plus --command` for targeted data inspection.

---

## 2. File and Code Conventions

### Python / Django
- Python 3.12+, Django 5.x
- Type hints on all function signatures
- Pydantic for all data validation (events, LLM output schemas)
- Settings split into `settings/base.py`, `settings/dev.py`, `settings/prod.py`
- Environment variables loaded via `python-dotenv`; never hardcode credentials
- All Django apps live under `backend/core/` or `backend/integrations/`
- Use `MERGE` (never `CREATE`) for all Neo4j writes to ensure idempotency
- Log all Celery task execution and all LLM API calls with structured JSON (`task_name`, `person_id`, `duration_ms`, `status`)

### TypeScript / Next.js
- Next.js 14 App Router; use Server Components for list pages, Client Components for interactive panels
- TypeScript strict mode throughout
- SWR for client-side data fetching
- Dark Tailwind theme — match the existing design system
- All API calls go through `lib/api.ts`; never call `fetch` directly from components

### General
- No magic strings — use constants files for stages, tag vocabularies, queue names, routing keys
- No `print()` statements in production code — use Python `logging` or Django logger
- No `console.log` in production frontend code
- All new REST endpoints must have a corresponding entry in Phase 5 of `build-phases.md`; if deviating, explain why

---

## 3. Neo4j Rules

- Driver is a singleton — use `core/graph/driver.py`, do not create new driver instances inline
- All Cypher goes in `core/graph/queries.py` — no inline Cypher in views or tasks
- Always use parameterised queries — never f-string Cypher (injection risk)
- Node IDs are UUIDs generated in Python, not by Neo4j
- Relationships are defined in `core/graph/schema.py` — do not create ad-hoc relationship types
- Allowed relationship types: `WORKS_AT`, `IS_LEAD_FOR`, `KNOWS`, `HAS_ACTION`, `HAS_LEAD`

---

## 4. RabbitMQ / Messaging Rules

- Exchange: `crm.topic` (topic, durable)
- Queue and routing key definitions live exclusively in `core/messaging/routing.py`
- All events are Pydantic models defined in `core/messaging/events.py`
- Use `CRMPublisher` from `core/messaging/publisher.py` — never publish raw pika calls from tasks or views
- Dead-letter queue: `crm.deadletter` — all failed messages route here; do not silently swallow them
- Connection retry: 3 attempts with exponential backoff (already in publisher.py)

---

## 5. Celery Rules

- Two queues only: `default` (fast) and `llm` (slow)
- LLM tasks **must** be routed to the `llm` queue — never run LLM calls on the default worker
- Tasks are defined in `core/tasks/` (lead, action, scoring) and `core/llm/tasks.py`
- All tasks use `bind=True`, `max_retries=3`, `autoretry_for=(Exception,)`, `retry_backoff=True`
- Log task start, success, and failure with `person_id` and duration

---

## 6. LLM / Claude API Rules

- Model: `claude-sonnet-4-20250514` (do not change without updating `CLAUDE.md`)
- Always use `anthropic.Anthropic()` — reads `ANTHROPIC_API_KEY` from environment
- System prompt is built by `core/llm/prompt_builder.build_system_prompt()`; user prompt by `build_user_prompt()`
- All LLM output is validated through `AITagResult` Pydantic model in `core/llm/schema.py`
- Never accept raw LLM output without validation
- Write every LLM call result to PostgreSQL `llm_calls` table: `person_id`, `model`, `input_tokens`, `output_tokens`, `latency_ms`, `result_json`, `timestamp`
- **Override ≠ delete**: When a user overrides AI tags, write to Neo4j with `ai_tag_status="overridden"` and preserve the AI version in history
- Tag vocabulary is fixed — defined in `VALID_TAGS` in `core/llm/schema.py`. Do not expand it without updating the system prompt and validator

---

## 7. REST API Rules

- All views read/write Neo4j; PostgreSQL is used only for auth
- CORS: `localhost:3000` only in dev (`settings/dev.py`)
- Authentication: JWT via `djangorestframework-simplejwt`; all endpoints except `/api/auth/` require auth
- Response format: follow DRF conventions; no custom envelope wrappers
- Pagination: all list endpoints must be paginated (page + page_size)
- Filtering: use query params as defined in Phase 5 of `build-phases.md`
- HTTP status codes must be correct: 200 OK, 201 Created, 204 No Content, 400 Bad Request, 404 Not Found, 409 Conflict

---

## 8. WebSocket Rules

- WebSocket endpoint: `ws://localhost:8000/ws/crm/`
- Channel group: `crm_live_feed`
- Channel layer backend: Redis
- On connect: send last 10 lead events
- Broadcast event types: `new_lead`, `ai_tags_ready`, `ai_tags_overridden`
- WebSocket consumers live in `core/websocket/consumers.py`

---

## 9. Testing Rules

- Tests live in `backend/tests/`
- Do not mock Neo4j in tests — use a test Neo4j instance
- Do mock the Anthropic API in `test_llm_tagging.py` — use `unittest.mock.patch`
- Do mock RabbitMQ in pipeline tests
- Test file naming: `test_<component>.py`
- Every new Celery task needs at least one happy-path test
- Every new REST endpoint needs at least a GET + POST test

---

## 10. Docker / Infrastructure Rules

- All services defined in `docker-compose.yml` at project root
- Use named volumes for Neo4j, PostgreSQL, ClickHouse data persistence
- Never use `latest` tag for service images — pin to a specific version
- The `celery_llm_worker` service must set `command: celery -A core worker -Q llm`
- Environment variables come from `.env` file (copy `.env.example`)

---

## 11. Security Rules

- Never hardcode API keys, passwords, or secrets in any file
- Never use f-strings to build Cypher queries (use parameterised queries)
- Never use f-strings to build SQL queries (use Django ORM or parameterised queries)
- Validate and sanitize all user input at API boundaries
- Do not expose Neo4j credentials, RabbitMQ credentials, or internal service URLs in API responses
- JWT tokens must be short-lived (access: 15 min, refresh: 7 days)

---

## 12. What NOT to Do

- Do not use `CREATE` in Cypher where `MERGE` should be used
- Do not route LLM tasks to the default Celery queue
- Do not call the Anthropic API directly from a Django view (always via Celery task)
- Do not delete AI tag history when a user overrides tags
- Do not add features beyond what is defined in the current phase
- Do not refactor existing working code unless explicitly asked
- Do not add comments or docstrings to code you didn't write or change
- Do not use `print()` for debugging in any Python file
- Do not add `console.log` in any TypeScript/JavaScript file

---

## 13. Phase Execution Checklist

When implementing a phase, verify:

- [ ] All new files match the structure defined in `build-phases.md`
- [ ] Pydantic models validate all external inputs
- [ ] Neo4j queries use `MERGE` and parameterised variables
- [ ] New Celery tasks are assigned to the correct queue
- [ ] New API endpoints are JWT-protected
- [ ] Docker Compose is updated if a new service or volume is needed
- [ ] `.env.example` is updated if a new env var is added
- [ ] At least a basic test exists for new functionality
- [ ] Structured logging is added to all new tasks and LLM calls

---

## 14. Useful Verification Commands

After each phase, run these to verify correctness:

```bash
# Verify Neo4j data
# Open http://localhost:7474 and run:
MATCH (n) RETURN n LIMIT 50

# Verify RabbitMQ queues are declared
# Open http://localhost:15672 → Queues tab

# Verify lead pipeline end-to-end
docker compose exec django python manage.py simulate_bookkeeper_events

# Verify LLM tagger (Phase 11+)
docker compose exec django python manage.py test_llm_tagger --person-id <id>

# Run all tests
docker compose exec django python manage.py test tests/
```

---

## 15. Reference Files

| File | Purpose |
|---|---|
| `build-phases.md` | Authoritative phase-by-phase build specs |
| `CLAUDE.md` | Commands, conventions, service URLs, **file tree** |
| `instruction.md` | This file — binding working rules |
| `backend/core/llm/schema.py` | LLM output schema and valid tag vocabulary |
| `backend/core/messaging/routing.py` | RabbitMQ exchange, queue, routing key definitions |
| `backend/core/graph/queries.py` | All Neo4j Cypher query functions |

---

## 16. File Tree Maintenance

The `## File Tree` section in `CLAUDE.md` is the **source of truth for file discovery**. It is always loaded into context at conversation start, eliminating the need for Glob/Grep tool calls just to find files.

**Rules:**
- Whenever you **create** a file: add it to the tree with a one-line annotation (purpose + phase).
- Whenever you **rename or move** a file: update its path in the tree.
- Whenever you **delete** a file: remove it from the tree.
- These tree updates must happen **in the same response** as the file operation — never defer them.
- Never let a session end with a stale tree.

**Format for new entries:**
```
│   ├── filename.py    # Short description — Phase N
```
