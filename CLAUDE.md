# GraphCRM — CLAUDE.md

## Project Overview

**GraphCRM** is a CRM backend built with Django 5, using PostgreSQL as the primary data store for all CRM data (people, businesses, leads, products, actions). Neo4j is used only for graph visualization (the graph explorer). The system ingests leads from external apps via RabbitMQ, scores them, and runs LLM-based tagging using the Claude API. The UI is the Django Admin panel powered by Django Unfold with Alpine.js for client-side reactivity.

**Stack:**
- Backend: Django 5, Django REST Framework, Django Channels
- UI: Django Unfold (admin theme) + Alpine.js (reactivity)
- Databases: PostgreSQL (primary CRM store + auth), Neo4j (graph visualization only), ClickHouse (analytics events)
- Messaging: RabbitMQ (pika), Celery workers
- LLM: Anthropic Claude API (`anthropic` Python SDK)
- Infrastructure: Docker Compose, Redis (Celery broker + channels)

**Project root:** `crm-backend/` (standard Django project layout)

---

## File Tree

> **Keep this section current.** Every time a file is created, renamed, moved, or deleted, update this tree in the same response (see §16 of `instruction.md`).

```
crm-backend/
├── docker-compose.yml                      # All 7 services
├── Makefile                                # dev/migrate/seed/test/worker shortcuts
├── start.sh                                # Full stack startup script
├── Dockerfile
├── manage.py
├── requirements.txt
├── .env / .env.example
├── settings/
│   ├── base.py                             # Shared settings
│   ├── dev.py                              # DEBUG=True, eager Celery
│   └── prod.py                             # Hardened production settings
├── core/
│   ├── __init__.py
│   ├── models.py                           # ExternalApp, Person, Business, Product, Lead, Action, Source, ReferralSource, Contact models
│   ├── auth.py                             # ExternalAppKeyAuthentication (X-API-Key header)
│   ├── admin.py                            # Unfold admin — User/Group + ExternalApp + dashboard callback
│   ├── admin_views.py                      # Custom views for Neo4j data (People, Businesses, Leads, Graph)
│   ├── celery.py                           # Celery app, two queues (default + llm)
│   ├── urls.py                             # Root URL conf — /api/ + /admin/ + /admin/neo4j/*
│   ├── asgi.py                             # ASGI entry (Channels + HTTP)
│   ├── wsgi.py
│   ├── templates/
│   │   └── admin/
│   │       ├── index.html                  # Unfold dashboard with KPI cards + stage distribution
│   │       └── neo4j/
│   │           ├── people_list.html        # People list with search, pagination, AI status
│   │           ├── person_detail.html      # Person detail with AI tags, actions, company
│   │           ├── business_list.html      # Business list with search, pagination
│   │           ├── business_detail.html    # Business detail with people list + convert to lead
│   │           ├── lead_list.html          # Lead list with stage/product/persona filters
│   │           ├── product_list.html       # Product list with search, pagination, CRUD
│   │           ├── product_detail.html     # Product detail with leads list, edit/delete
│   │           ├── contact_list.html       # Contact staging inbox: classify as person/business, convert to lead
│   │           ├── import_list.html        # Import contacts: LinkedIn scrape, CSV/XLSX upload, bulk actions
│   │           ├── pipeline.html           # Kanban-style sales pipeline board
│   │           └── graph_explorer.html     # Interactive force-directed graph (canvas)
│   ├── importers/
│   │   ├── __init__.py
│   │   └── file_parser.py                  # CSV/XLSX parsing + validation for contact imports
│   ├── db/
│   │   ├── __init__.py
│   │   └── queries.py                      # PostgreSQL query layer (primary store, 30 ORM functions)
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── driver.py                       # Singleton Neo4j driver
│   │   ├── schema.py                       # CREATE CONSTRAINT statements
│   │   ├── models.py                       # Python dataclasses (Person, Business…)
│   │   ├── queries.py                      # Neo4j Cypher queries (graph visualization only)
│   │   └── sync.py                         # Django signals → Celery tasks → Neo4j sync
│   ├── messaging/
│   │   ├── __init__.py
│   │   ├── routing.py                      # Exchange, queue, routing key constants
│   │   ├── events.py                       # Pydantic event schemas
│   │   ├── publisher.py                    # CRMPublisher (pika, retry)
│   │   └── consumer.py                     # Base consumer class + DLQ
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── lead_tasks.py                   # process_incoming_lead Celery task
│   │   ├── action_tasks.py                 # process_action_logged
│   │   └── scoring_tasks.py                # recalculate_lead_score
│   ├── consumers/
│   │   ├── __init__.py
│   │   └── lead_consumer.py                # RabbitMQ consumer → dispatches lead_tasks
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── schema.py                       # AITagResult + VALID_TAGS
│   │   ├── prompt_builder.py               # build_system_prompt / build_user_prompt
│   │   ├── tagger.py                       # LeadTagger class (Claude API)
│   │   ├── tasks.py                        # tag_lead_with_llm Celery task (llm queue)
│   │   └── consumer.py                     # RabbitMQ consumer for llm_tagging queue
│   ├── api/
│   │   ├── __init__.py
│   │   ├── urls.py                         # All /api/ URL routing
│   │   ├── serializers/
│   │   │   └── __init__.py                 # DRF serializers
│   │   └── views/
│   │       ├── __init__.py
│   │       ├── contacts.py                 # POST /api/contacts/ (external contact creation)
│   │       ├── people.py                   # GET/POST /api/people/
│   │       ├── businesses.py               # GET/POST /api/businesses/
│   │       ├── leads.py                    # GET/PATCH /api/leads/
│   │       ├── graph.py                    # GET /api/graph/snapshot/
│   │       ├── analytics.py               # GET /api/analytics/summary/
│   │       ├── actions.py                  # POST /api/people/{id}/actions/
│   │       └── ai_tags.py                  # GET/POST/PATCH /api/people/{id}/ai-tags/
│   ├── websocket/
│   │   ├── __init__.py
│   │   ├── consumers.py                    # Django Channels WS consumer
│   │   └── routing.py                      # ws/crm/ → CRMConsumer
│   └── management/
│       ├── __init__.py
│       └── commands/
│           ├── __init__.py
│           ├── start_consumer.py           # python manage.py start_consumer
│           ├── start_llm_consumer.py       # python manage.py start_llm_consumer
│           ├── seed_users.py               # python manage.py seed_users
│           ├── simulate_bookkeeper_events.py
│           ├── simulate_external_events.py # python manage.py simulate_external_events --source greenforest
│           ├── test_llm_tagger.py          # python manage.py test_llm_tagger --person-id
│           ├── debug_pipeline.py           # python manage.py debug_pipeline --event lead|action|score|llm
│           ├── migrate_neo4j_to_pg.py      # One-time data migration: Neo4j → PostgreSQL
│           └── resync_neo4j.py             # Full re-sync: clear Neo4j and rebuild from PostgreSQL
├── integrations/
│   ├── __init__.py
│   ├── bookkeeper/
│   │   ├── __init__.py
│   │   ├── events.py                       # on_contact_updated / on_business_signup
│   │   └── hooks.py                        # Django signal receivers
│   ├── apify/
│   │   ├── __init__.py
│   │   ├── scraper.py                      # ApifyScraper.start_linkedin_scrape
│   │   ├── webhook.py                      # POST /api/apify/webhook/
│   │   └── transformer.py                  # apify_profile_to_lead_event
│   └── external/
│       ├── __init__.py
│       ├── events.py                       # Generic on_contact_created / on_contact_updated (any source app)
│       └── webhook.py                      # POST /api/external/contacts/ (API key auth)
└── tests/
    ├── __init__.py
    ├── test_lead_pipeline.py
    ├── test_api_people.py
    ├── test_graph_queries.py
    ├── test_scoring.py
    └── test_llm_tagging.py
```

---

## Debugging

### Interactive Shell (`shell_plus`)
```bash
# Drop into an IPython REPL with all Django models auto-imported + SQL logging
docker compose exec django python manage.py shell_plus

# One-liner — inspect a person's full Neo4j context
docker compose exec django python manage.py shell_plus --command="
from core.graph.queries import get_person_with_connections
import json; print(json.dumps(get_person_with_connections('PERSON-ID'), indent=2))
"

# One-liner — list all people nodes
docker compose exec django python manage.py shell_plus --command="
from core.graph.driver import get_driver
with get_driver().session() as s:
    for r in s.run('MATCH (p:Person) RETURN p.id, p.name, p.email, p.score LIMIT 20'):
        print(dict(r))
"
```

### Synchronous Pipeline Debugger (`debug_pipeline`)
Runs Celery tasks inline — **no RabbitMQ or worker needed**.
```bash
# Fire a fake lead through the full ingestion pipeline
docker compose exec django python manage.py debug_pipeline --event lead

# Re-score a specific person
docker compose exec django python manage.py debug_pipeline --event score --person-id <uuid>

# Run LLM tagger and print AITagResult (requires ANTHROPIC_API_KEY + person in Neo4j)
docker compose exec django python manage.py debug_pipeline --event llm --person-id <uuid>

# Log a fake action for a person
docker compose exec django python manage.py debug_pipeline --event action --person-id <uuid>
```

### Neo4j Direct Queries
```bash
# From Neo4j Browser at http://localhost:7474 (neo4j / password):
MATCH (p:Person) RETURN p LIMIT 20
MATCH (p:Person)-[:WORKS_AT]->(b:Business) RETURN p.name, b.name LIMIT 20
MATCH (p:Person) WHERE p.ai_tag_status IS NOT NULL RETURN p.name, p.ai_tags, p.ai_persona

# From shell_plus (parameterised):
docker compose exec django python manage.py shell_plus --command="
from core.graph.driver import get_driver
with get_driver().session() as s:
    r = s.run('MATCH (p:Person {id: \$id}) RETURN p', id='PERSON-ID')
    print(dict(r.single()['p']))
"
```

### RabbitMQ Queue Inspection
```bash
# List all queues with depth and consumer count
docker compose exec rabbitmq rabbitmqctl list_queues name messages consumers

# Inspect dead-letter queue
docker compose exec rabbitmq rabbitmqctl list_queues name messages | grep deadletter

# Purge the dead-letter queue after investigating
docker compose exec rabbitmq rabbitmqctl purge_queue crm.deadletter
```

### ClickHouse Analytics Queries
```bash
# Recent lead events
docker compose exec clickhouse clickhouse-client --query \
  "SELECT person_id, event_type, score, stage, timestamp FROM lead_events ORDER BY timestamp DESC LIMIT 20"

# Score distribution
docker compose exec clickhouse clickhouse-client --query \
  "SELECT stage, avg(score) as avg_score, count() as count FROM lead_events GROUP BY stage"
```

### Celery Task One-Off (force sync)
```bash
# Call any task directly from shell_plus — bypasses queue even without CELERY_TASK_ALWAYS_EAGER
docker compose exec django python manage.py shell_plus --command="
from core.tasks.lead_tasks import process_incoming_lead
result = process_incoming_lead.apply(args=[{'event_type': 'lead.created', 'source_app': 'debug', ...}])
print(result.result)
"
```

### API Endpoint Testing
```bash
# Get a JWT token
curl -s -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}' | python3 -m json.tool

# Use the token (replace TOKEN)
curl -s -H "Authorization: Bearer TOKEN" http://localhost:8000/api/people/ | python3 -m json.tool
curl -s -H "Authorization: Bearer TOKEN" http://localhost:8000/api/graph/snapshot/ | python3 -m json.tool
curl -s -H "Authorization: Bearer TOKEN" http://localhost:8000/api/analytics/summary/ | python3 -m json.tool
```

---

## Common Commands

### Docker
```bash
# Start all services
docker compose up -d

# Rebuild after dependency changes
docker compose up -d --build

# Tail all logs
docker compose logs -f

# Tail specific service
docker compose logs -f django
docker compose logs -f celery_worker
docker compose logs -f celery_llm_worker
```

### Django Management
```bash
# Run migrations
docker compose exec django python manage.py migrate

# Create superuser
docker compose exec django python manage.py createsuperuser

# Seed test users
docker compose exec django python manage.py seed_users

# Simulate Bookkeeper events (integration test)
docker compose exec django python manage.py simulate_bookkeeper_events

# Trigger LinkedIn scrape
docker compose exec django python manage.py trigger_linkedin_scrape --url "..." --product "ProductA"

# Test LLM tagger on a specific person
docker compose exec django python manage.py test_llm_tagger --person-id <id>

# Start RabbitMQ lead consumer
docker compose exec django python manage.py start_consumer

# Start RabbitMQ LLM consumer
docker compose exec django python manage.py start_llm_consumer
```

### Makefile Shortcuts
```bash
make start        # build, migrate, seed, tail logs
make dev          # docker compose up -d
make migrate      # run Django migrations
make seed         # seed_users + simulate_bookkeeper_events
make test         # run all backend tests
make worker       # start Celery default worker
make consumer     # start RabbitMQ lead consumer
make llm-worker   # start Celery LLM queue worker
```

### Running Tests
```bash
# All tests
docker compose exec django python manage.py test tests/

# Individual test modules
docker compose exec django python manage.py test tests.test_lead_pipeline
docker compose exec django python manage.py test tests.test_api_people
docker compose exec django python manage.py test tests.test_graph_queries
docker compose exec django python manage.py test tests.test_scoring
docker compose exec django python manage.py test tests.test_llm_tagging
```

### Celery Workers
```bash
# Default worker (leads, actions, scoring)
celery -A core worker -l info

# LLM-dedicated worker (separate queue to avoid blocking)
celery -A core worker -Q llm -l info -c 2
```

---

## Environment Variables

See `.env.example`. Key variables:

```
ANTHROPIC_API_KEY=          # Required for LLM tagging
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
POSTGRES_DB=graphcrm
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
REDIS_URL=redis://redis:6379/0
CLICKHOUSE_HOST=clickhouse
```

---

## Service URLs (local dev)

| Service | URL |
|---|---|
| Django Admin (Unfold) | http://localhost:8000/admin/ |
| Django API | http://localhost:8000/api/ |
| WebSocket | ws://localhost:8000/ws/crm/ |
| Neo4j Browser | http://localhost:7474 |
| RabbitMQ Management | http://localhost:15672 |
| ClickHouse HTTP | http://localhost:8123 |

---

## Admin Panel (Django Unfold + Alpine.js)

The admin panel uses [Django Unfold](https://unfoldadmin.com/) for a modern, responsive UI with Tailwind-based styling and dark mode support. Alpine.js is used for client-side reactivity (live updates, modals, filters, interactive components).

**Features:**
- **Dashboard** (`/admin/`): KPI cards (people, businesses, leads, avg score), lead stage distribution, pending AI tagging queue
- **People** (`/admin/neo4j/people/`): Searchable list with score, AI status; drill into detail view with AI analysis, actions, company info
- **Businesses** (`/admin/neo4j/businesses/`): Searchable, paginated list
- **Leads** (`/admin/neo4j/leads/`): Filterable by stage, product, and AI persona
- **Graph Explorer** (`/admin/neo4j/graph/`): Interactive force-directed graph visualization (canvas-based, pan/zoom, tooltips)
- **Auth** (`/admin/auth/`): Standard Django User/Group management with Unfold styling

**Architecture notes:**
- Since CRM data lives in Neo4j (not Django ORM), the People/Businesses/Leads/Graph views are custom Django views registered at `/admin/neo4j/*`, not standard ModelAdmin classes.
- The dashboard callback (`core.admin.dashboard_callback`) fetches live analytics from Neo4j via `get_analytics_summary()`.
- `UNFOLD` config is in `settings/base.py` — sidebar navigation, site title, environment badge, and dashboard callback are all defined there.
- Templates extend `admin/base_site.html` (Unfold's base) and use Tailwind utility classes + Material Symbols icons.
- Alpine.js handles all client-side interactivity (dropdowns, modals, live search, WebSocket event rendering) — no separate frontend build step needed.

**Login:** admin / password (from `seed_users` command)

---

## Key Architectural Rules

1. **PostgreSQL is the primary store** for all CRM data (Person, Business, Product, Lead, Action, Source, ReferralSource). Neo4j is kept only for graph visualization (`get_graph_snapshot`). All queries go through `core/db/queries.py` (Django ORM). Changes are synced to Neo4j via `core/graph/sync.py` (Django signals → Celery tasks).
2. **Two Celery queues**: `default` for fast tasks (lead ingestion, scoring, Neo4j sync), `llm` for slow LLM calls. Never mix them.
3. **Idempotent writes** — use `update_or_create` / `get_or_create` in PostgreSQL (mirrors Neo4j MERGE pattern).
4. **AI tag overrides preserve history** — never delete AI-generated tags. Store override separately and keep original in history.
5. **raw_context** must always be populated when publishing `LeadCreatedEvent` — it is the primary LLM input.
6. **Django Admin is the only UI** — there is NO separate frontend app. All UI work MUST follow these rules:
   - **Templates**: Extend Unfold's `admin/base_site.html`. Use Tailwind utility classes and Material Symbols icons.
   - **Reactivity**: Use Alpine.js (`x-data`, `x-on`, `x-show`, `x-bind`, `x-effect`, etc.) for all client-side interactivity — dropdowns, modals, live search, filtering, form validation, WebSocket event rendering.
   - **Custom views**: CRM data pages (People, Businesses, Leads, Graph) are custom Django views under `/admin/neo4j/*` in `core/admin_views.py`, NOT ModelAdmin classes.
   - **AJAX/fetch**: For dynamic data loading, use `fetch()` calls to the DRF `/api/` endpoints from within Alpine.js components in templates.
   - **No npm/Node.js**: Alpine.js is loaded via CDN `<script>` tag. No build step, no bundler, no package.json for the UI.
   - When asked to build a feature or UI change, ALWAYS implement it using Django templates + Unfold styling + Alpine.js. Never introduce React, Vue, Next.js, or any other JS framework.

---

## LLM Integration

- Claude model: `claude-sonnet-4-20250514`
- Tags must come from the allowed vocabulary in `core/llm/schema.py`
- All LLM inputs/outputs must be logged to PostgreSQL `llm_calls` table
- Use `manage.py test_llm_tagger --person-id X` to test without the full RabbitMQ pipeline
- Separate `celery_llm_worker` container handles only the `llm` queue

---

## Build Phases Reference

1. Docker scaffold
2. Neo4j schema + queries
3. RabbitMQ SDK
4. Celery pipeline
5. Django REST API
6. WebSocket (Django Channels)
7. Bookkeeper integration
8. Apify integration
9. Auth + tests + hardening
10. LLM lead tagging (Claude API)
11. Admin UI enhancements (Alpine.js reactivity)
