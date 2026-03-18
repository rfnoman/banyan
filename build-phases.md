# GraphCRM — Phase-by-Phase Build Instructions for Claude

> **Stack:** Django 5 · Next.js 14 (App Router) · Neo4j · RabbitMQ · Celery · ClickHouse · PostgreSQL · Claude API  
> **Pattern:** Each phase is a self-contained Claude prompt. Paste the prompt, get working code, move on.

---

## Phase 1 — Project Scaffold & Docker Environment

**Prompt Claude:**
```
Create a monorepo for a CRM system with this structure:

graphcrm/
  backend/          # Django 5 project
  frontend/         # Next.js 14 app
  docker-compose.yml

In docker-compose.yml include these services:
- django (backend, port 8000)
- celery_worker (same image as django, command: celery -A core worker)
- celery_llm_worker (same image, queue: llm — separate worker for LLM tasks)
- nextjs (frontend, port 3000)
- rabbitmq (rabbitmq:3-management, port 5672 + management 15672)
- neo4j (neo4j:5, ports 7474 + 7687, auth neo4j/password)
- postgres (postgres:16, for Django ORM)
- clickhouse (clickhouse/clickhouse-server, port 8123)
- redis (redis:7, for Celery broker)

For Django: create the project with django-admin, install:
django, djangorestframework, django-cors-headers, celery, pika, neo4j-driver,
psycopg2-binary, django-channels, channels-redis, clickhouse-driver,
python-dotenv, anthropic, pydantic

Create a .env.example with all connection strings including ANTHROPIC_API_KEY.
Create backend/core/settings.py with all services configured.
```

---

## Phase 2 — Neo4j Graph Schema & Driver Layer

**Prompt Claude:**
```
In the Django backend (graphcrm/backend), create a Neo4j service layer at:
  core/graph/driver.py      — singleton Neo4j driver using neo4j-driver
  core/graph/schema.py      — all Cypher CREATE CONSTRAINT statements
  core/graph/models.py      — Python dataclasses for Person, Business, Lead, Product, Action
  core/graph/queries.py     — CRUD Cypher query functions

Neo4j nodes and relationships to define:
  (:Person {id, name, title, email, linkedin_url, location, source, score,
            ai_tags, ai_persona, ai_product_fit, ai_urgency, ai_reasoning,
            ai_tagged_at, ai_tag_status, created_at})
  (:Business {id, name, industry, size, website, location, created_at})
  (:Product {id, name})
  (:Lead {id, stage, product_id, score, source, tags, created_at})
  (:Action {id, type, note, channel, timestamp})

  (Person)-[:WORKS_AT]->(Business)
  (Person)-[:IS_LEAD_FOR {stage, score}]->(Product)
  (Person)-[:KNOWS]->(Person)
  (Person)-[:HAS_ACTION]->(Action)
  (Business)-[:HAS_LEAD]->(Lead)

In queries.py create these functions:
  - create_or_merge_person(data: dict) -> str
  - create_or_merge_business(data: dict) -> str
  - link_person_to_business(person_id, business_id, rel_type="WORKS_AT")
  - create_lead_relationship(person_id, product_name, stage, score)
  - log_action(person_id, action_type, note)
  - get_person_with_connections(person_id) -> dict
  - get_graph_snapshot() -> {nodes: [], edges: []}
  - update_ai_tags(person_id, ai_result: dict)   ← stores LLM output
  - get_pending_ai_tagging(limit=50) -> list      ← people not yet AI-tagged
  - get_ai_tag_history(person_id) -> list         ← all past LLM tag versions

Use MERGE so duplicate imports are safe.
```

---

## Phase 3 — RabbitMQ Event Schema & Publisher SDK

**Prompt Claude:**
```
Create a shared RabbitMQ publisher SDK that any of our apps can import.

Create: graphcrm/backend/core/messaging/

  publisher.py     — RabbitMQ publisher using pika
  events.py        — Pydantic event schemas
  consumer.py      — Base consumer class with error handling + DLQ support
  routing.py       — Exchange and queue definitions

Exchange design:
  Exchange name: crm.topic  |  Type: topic  |  Durable: true

Queues and routing keys:
  crm.leads.ingest        ← lead.created.*, lead.scraped.*, lead.updated.*
  crm.leads.llm_tagging   ← lead.saved.*   (triggers LLM analysis after lead saved)
  crm.actions.process     ← action.logged.*
  crm.companies.sync      ← company.created.*, company.updated.*
  crm.deadletter          ← all failed messages

Event schemas (Pydantic):
  LeadCreatedEvent:
    event_type: str = "lead.created"
    source_app: str
    source_product: str
    person: {name, email, title, company, linkedin_url, location}
    company: {name, industry, size, website}
    trigger: str             # "contact_updated" | "business_signup" | "invoice_sent"
    score_hints: dict
    raw_context: str         # free-text from source app for LLM to read
    timestamp: datetime

  LeadSavedEvent:              ← published internally after lead written to Neo4j
    event_type: str = "lead.saved"
    person_id: str
    source_app: str
    trigger: str
    raw_context: str           # passed through to LLM

  ActionLoggedEvent:
    event_type, person_email, action_type, note, source_app

  CompanyUpdatedEvent:
    event_type, company_name, updates, source_app

  AITagRequestEvent:           ← published from UI "Re-analyze" button
    event_type: str = "lead.tag_requested"
    person_id: str
    requested_by: str          # username
    timestamp: datetime

In publisher.py create CRMPublisher with:
  publish_lead(), publish_action(), publish_company(),
  publish_lead_saved(), publish_ai_tag_request()

Include connection retry logic (3 attempts, exponential backoff).
```

---

## Phase 4 — Celery Workers & Lead Processing Pipeline

**Prompt Claude:**
```
In graphcrm/backend, create the Celery task pipeline.

Create: core/tasks/
  lead_tasks.py, action_tasks.py, scoring_tasks.py

In lead_tasks.py, task: process_incoming_lead(event_data: dict)
  Steps:
  1. Validate via LeadCreatedEvent pydantic schema
  2. Deduplicate — check Neo4j by email
  3. create_or_merge_person() in Neo4j
  4. create_or_merge_business() in Neo4j
  5. link_person_to_business()
  6. create_lead_relationship() — stage="New Lead"
  7. Compute initial score:
       base=40, +20 senior title, +15 is_paid, +10 large company,
       +10 linkedin source, +5 linkedin_url present
  8. Write score to Neo4j
  9. Write event to ClickHouse lead_events table
  10. Publish LeadSavedEvent to crm.leads.llm_tagging queue
  11. If score >= 75: publish to crm.leads.scored

In scoring_tasks.py:
  recalculate_lead_score(person_id): ClickHouse 30-day actions → update Neo4j score

Create RabbitMQ consumer: core/consumers/lead_consumer.py
  run with: python manage.py start_consumer

ClickHouse schema:
  CREATE TABLE lead_events (
    person_id String, event_type String, source_app String,
    score Float32, stage String, timestamp DateTime
  ) ENGINE = MergeTree() ORDER BY (person_id, timestamp)
```

---

## Phase 5 — Django REST API

**Prompt Claude:**
```
Create the Django REST API for the Next.js CRM frontend.

Create: core/api/views/ — people.py, businesses.py, leads.py, graph.py,
                          analytics.py, actions.py, ai_tags.py

Endpoints:

  People:
    GET  /api/people/
    POST /api/people/
    GET  /api/people/{id}/
    POST /api/people/{id}/actions/

  Businesses:
    GET  /api/businesses/
    POST /api/businesses/
    GET  /api/businesses/{id}/

  Leads:
    GET   /api/leads/               — ?product=&stage=&score_min=&ai_persona=
    PATCH /api/leads/{id}/stage/
    POST  /api/leads/{id}/actions/

  Graph:
    GET  /api/graph/snapshot/
    POST /api/graph/edge/

  Analytics:
    GET /api/analytics/summary/
    GET /api/analytics/events/

  AI Tagging (new):
    GET  /api/people/{id}/ai-tags/         — get current + history of AI tags
    POST /api/people/{id}/ai-tags/retag/   — trigger on-demand LLM re-tag
    PATCH /api/people/{id}/ai-tags/        — user overrides AI tags manually
      body: {tags, persona, product_fit, urgency, override_note}

All views read/write Neo4j. PostgreSQL only for auth.
CORS for localhost:3000.
```

---

## Phase 6 — Django Channels WebSocket (Live Feed)

**Prompt Claude:**
```
Add real-time WebSocket support using Django Channels.

Create: core/websocket/consumers.py, routing.py

WebSocket at: ws://localhost:8000/ws/crm/
On connect: send last 10 lead events
Subscribe to group: "crm_live_feed"

Broadcast after process_incoming_lead():
  { "type": "new_lead", person, score, stage, source_app, timestamp }

Broadcast after LLM tagging completes (new):
  {
    "type": "ai_tags_ready",
    "person_id": "...",
    "person_name": "...",
    "tags": [...],
    "persona": "...",
    "product_fit": "...",
    "urgency": "...",
    "reasoning": "..."
  }

Broadcast when user manually overrides AI tags (new):
  { "type": "ai_tags_overridden", "person_id": "...", "by": "username" }

Use Redis channel layer. Update docker-compose to use daphne.
```

---

## Phase 7 — Next.js Frontend (Full CRM)

**Prompt Claude:**
```
Build the Next.js 14 (App Router) frontend for GraphCRM.

app/
  layout.tsx, page.tsx
  people/page.tsx, businesses/page.tsx, leads/page.tsx
  pipeline/page.tsx, graph/page.tsx, analytics/page.tsx

components/
  ui/                   — Button, Input, Modal, Table, Badge
  people/               — PersonTable, AddPersonModal, PersonDetail
  businesses/           — BusinessTable, AddBusinessModal
  leads/                — LeadTable, LeadFilters, LeadDetailPanel
  pipeline/             — KanbanBoard, KanbanCard
  graph/                — ForceGraph (react-force-graph-2d)
  analytics/            — KPICard, FunnelChart, EventTimeline
  live/                 — LiveFeedDrawer
  ai/                   — AITagBadge, AITagPanel, AITagOverrideModal (see Phase 11)

lib/
  api.ts, neo4j-graph.ts, websocket.ts (useRealtimeFeed hook)

Key details:
- Server Components for people/businesses list pages
- Client Components for LeadDetailPanel, Graph, Pipeline, AI tag panel
- react-force-graph-2d for graph view
- SWR for client-side fetching
- Dark Tailwind theme
- TypeScript throughout
- Loading skeletons for all tables
```

---

## Phase 8 — Bookkeeper App Integration

**Prompt Claude:**
```
Create the Bookkeeper app integration in integrations/bookkeeper/

  events.py      — on_contact_updated(), on_business_signup(), on_invoice_sent()
  hooks.py       — Django signal receivers
  README.md

on_contact_updated(contact: dict):
  → LeadCreatedEvent, trigger="contact_updated"
  → raw_context = f"{contact['name']} is a {contact['title']} at {contact['company']}.
                    They updated their profile. Industry: {contact['industry']}.
                    Note from app: {contact.get('notes', '')}"

on_business_signup(business: dict):
  → LeadCreatedEvent, trigger="business_signup"
  → raw_context = f"New business signup: {business['name']},
                    industry: {business['industry']},
                    plan: {business['plan']}, size: {business['size']} employees."

Always populate raw_context — it's the free-text the LLM will use for tagging.

Management command: manage.py simulate_bookkeeper_events
  — sends 5 fake events of each type including realistic raw_context strings
```

---

## Phase 9 — Apify LinkedIn Integration

**Prompt Claude:**
```
Create: integrations/apify/
  scraper.py, webhook.py, transformer.py

ApifyScraper.start_linkedin_scrape(search_url, product) -> run_id
  webhook_url = /api/apify/webhook/

transformer.py: apify_profile_to_lead_event(profile, product) -> LeadCreatedEvent
  raw_context = f"{profile['name']}, {profile['headline']} at {profile['company']}.
                  {profile.get('summary', '')} Mutual connections: {profile.get('mutualCount',0)}."

POST /api/apify/webhook/ → transform → publish to RabbitMQ

Management command: manage.py trigger_linkedin_scrape --url "..." --product "ProductA"
```

---

## Phase 10 — Testing, Auth & Production Hardening

**Prompt Claude:**
```
1. JWT auth (djangorestframework-simplejwt), login page in Next.js
2. Seed command: manage.py seed_users (3 team users)

3. Tests in backend/tests/:
   - test_lead_pipeline.py    — mock RabbitMQ → Celery → Neo4j
   - test_api_people.py       — CRUD
   - test_graph_queries.py    — Cypher unit tests
   - test_scoring.py          — scoring logic
   - test_llm_tagging.py      — mock Anthropic API, validate tag schema

4. Makefile: dev, migrate, seed, test, worker, consumer, llm-worker

5. Structured JSON logging for all Celery tasks and LLM calls
   (log: model used, tokens, latency, person_id, tags returned)

6. settings/base.py, dev.py, prod.py
7. Final README.md with full setup guide
```

---

## Phase 11 — LLM Lead Tagging (Claude API)

> This is the most nuanced phase. Read the full design before prompting.

### Design Overview

```
RabbitMQ                   Celery (llm queue)            Neo4j
crm.leads.llm_tagging  →   tag_lead_with_llm(person_id)  → update ai_tags
crm.ai.tag_requested   →   (same task, on-demand)        → broadcast via WS
```

**Two trigger paths:**
1. **Automatic** — every saved lead publishes a `LeadSavedEvent` → LLM worker picks it up
2. **Manual** — user clicks "Re-analyze" in UI → POST `/api/people/{id}/ai-tags/retag/` → publishes `AITagRequestEvent` → same Celery task

**LLM Output Schema (structured JSON):**
```json
{
  "tags": ["decision-maker", "high-intent", "technical-buyer"],
  "persona": "Technical Executive",
  "product_fit": "ProductA",
  "urgency": "high",
  "reasoning": "Sarah is a VP of Engineering at a 150-person SaaS company
                 that recently raised Series B. Her title and company stage
                 suggest strong budget authority and a clear need for
                 developer tooling. The contact_updated trigger from Bookkeeper
                 suggests active engagement with our ecosystem.",
  "suggested_stage": "Qualified",
  "confidence": 0.87
}
```

**Tag vocabulary (Claude must choose from these):**

| Tag Category | Options |
|---|---|
| Role | `decision-maker` `influencer` `champion` `end-user` `blocker` |
| Intent | `high-intent` `evaluating` `early-research` `not-ready` |
| Buyer type | `technical-buyer` `economic-buyer` `executive-sponsor` |
| Temperature | `hot` `warm` `cold` |
| Source quality | `inbound` `outbound` `referral` `scraped` |

**Prompt Claude:**
```
In graphcrm/backend, build the LLM lead tagging system using the Anthropic Python SDK.

Create: core/llm/

  tagger.py          — LeadTagger class (main LLM logic)
  prompt_builder.py  — builds the system + user prompt from person context
  schema.py          — Pydantic schema for LLM output validation
  consumer.py        — RabbitMQ consumer for crm.leads.llm_tagging queue
  tasks.py           — Celery task: tag_lead_with_llm(person_id, context)

─────────────────────────────────────────────────────────────────────
FILE: core/llm/schema.py
─────────────────────────────────────────────────────────────────────
from pydantic import BaseModel, field_validator
from typing import Literal

VALID_TAGS = {
  "decision-maker","influencer","champion","end-user","blocker",
  "high-intent","evaluating","early-research","not-ready",
  "technical-buyer","economic-buyer","executive-sponsor",
  "hot","warm","cold","inbound","outbound","referral","scraped"
}

class AITagResult(BaseModel):
    tags: list[str]
    persona: str
    product_fit: str          # must be one of our product names
    urgency: Literal["high", "medium", "low"]
    reasoning: str            # 2-4 sentences, human-readable
    suggested_stage: str      # one of the STAGES list
    confidence: float         # 0.0 to 1.0

    @field_validator("tags")
    def validate_tags(cls, v):
        invalid = set(v) - VALID_TAGS
        if invalid:
            raise ValueError(f"Invalid tags: {invalid}")
        return v

─────────────────────────────────────────────────────────────────────
FILE: core/llm/prompt_builder.py
─────────────────────────────────────────────────────────────────────
def build_system_prompt(products: list[str]) -> str:
    return f"""You are a B2B sales intelligence assistant for a software company
that sells these products: {', '.join(products)}.

Your job is to analyze incoming leads and assign structured tags based on
the person's role, company context, and how they entered our CRM.

You must respond ONLY with a valid JSON object matching this exact schema:
{{
  "tags": [list of tags from the allowed vocabulary],
  "persona": "short persona label (e.g. Technical Executive, SMB Founder)",
  "product_fit": "the most relevant product name from {products}",
  "urgency": "high | medium | low",
  "reasoning": "2-4 sentence explanation of your tagging decision",
  "suggested_stage": "one of: New Lead, Contacted, Qualified, Demo, Proposal",
  "confidence": 0.0 to 1.0
}}

Allowed tags: decision-maker, influencer, champion, end-user, blocker,
high-intent, evaluating, early-research, not-ready, technical-buyer,
economic-buyer, executive-sponsor, hot, warm, cold, inbound, outbound,
referral, scraped.

Do not include explanation outside the JSON. Do not wrap in markdown code blocks.
"""

def build_user_prompt(person: dict, company: dict, raw_context: str,
                      trigger: str, source_app: str) -> str:
    return f"""Analyze this incoming lead and assign appropriate tags.

PERSON:
  Name: {person.get('name')}
  Title: {person.get('title', 'Unknown')}
  Email: {person.get('email')}
  Location: {person.get('location', 'Unknown')}
  LinkedIn: {'Yes' if person.get('linkedin_url') else 'No'}
  Current Score: {person.get('score', 0)}

COMPANY:
  Name: {company.get('name', 'Unknown')}
  Industry: {company.get('industry', 'Unknown')}
  Size: {company.get('size', 'Unknown')} employees
  Website: {company.get('website', 'Unknown')}

HOW THIS LEAD ENTERED THE CRM:
  Source App: {source_app}
  Trigger: {trigger}
  Context: {raw_context}

EXISTING TAGS (if any): {person.get('tags', [])}

Based on all of the above, return the JSON tag object.
"""

─────────────────────────────────────────────────────────────────────
FILE: core/llm/tagger.py
─────────────────────────────────────────────────────────────────────
import json, anthropic
from .prompt_builder import build_system_prompt, build_user_prompt
from .schema import AITagResult
from core.graph.queries import get_person_with_connections, update_ai_tags

class LeadTagger:
    def __init__(self):
        self.client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from env
        self.products = settings.CRM_PRODUCTS # ["ProductA","ProductB","ProductC"]

    def tag_person(self, person_id: str, raw_context: str = "",
                   trigger: str = "", source_app: str = "") -> AITagResult:

        # 1. Fetch full person + company context from Neo4j
        person_data = get_person_with_connections(person_id)
        company_data = person_data.get("company", {})

        # 2. Build prompts
        system = build_system_prompt(self.products)
        user = build_user_prompt(person_data, company_data,
                                  raw_context, trigger, source_app)

        # 3. Call Claude API
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": user}]
        )

        # 4. Parse + validate response
        raw_json = response.content[0].text.strip()
        result_dict = json.loads(raw_json)
        result = AITagResult(**result_dict)

        # 5. Write to Neo4j — store full result + metadata
        update_ai_tags(person_id, {
            **result.model_dump(),
            "ai_tagged_at": datetime.utcnow().isoformat(),
            "ai_tag_status": "auto",          # "auto" | "manual" | "overridden"
            "model_used": "claude-sonnet-4-20250514",
            "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
        })

        return result

    def retag_person(self, person_id: str, requested_by: str) -> AITagResult:
        """On-demand retag triggered from the UI"""
        person_data = get_person_with_connections(person_id)
        result = self.tag_person(
            person_id,
            raw_context=person_data.get("ai_reasoning", ""),
            trigger="manual_retag",
            source_app=f"ui:{requested_by}"
        )
        # mark as manual trigger
        update_ai_tags(person_id, {"ai_tag_status": "manual"})
        return result

─────────────────────────────────────────────────────────────────────
FILE: core/llm/tasks.py
─────────────────────────────────────────────────────────────────────
Create a Celery task routed to the "llm" queue:

  @app.task(queue="llm", bind=True, max_retries=3,
            autoretry_for=(Exception,), retry_backoff=True)
  def tag_lead_with_llm(self, person_id: str, raw_context: str = "",
                         trigger: str = "", source_app: str = "",
                         requested_by: str = None):
      tagger = LeadTagger()
      if requested_by:
          result = tagger.retag_person(person_id, requested_by)
      else:
          result = tagger.tag_person(person_id, raw_context, trigger, source_app)

      # Broadcast result via WebSocket
      channel_layer = get_channel_layer()
      async_to_sync(channel_layer.group_send)("crm_live_feed", {
          "type": "ai_tags_ready",
          "person_id": person_id,
          "tags": result.tags,
          "persona": result.persona,
          "product_fit": result.product_fit,
          "urgency": result.urgency,
          "reasoning": result.reasoning,
          "confidence": result.confidence,
          "suggested_stage": result.suggested_stage,
      })
      return result.model_dump()

─────────────────────────────────────────────────────────────────────
FILE: core/llm/consumer.py
─────────────────────────────────────────────────────────────────────
Create a RabbitMQ consumer that listens to TWO queues:

  crm.leads.llm_tagging  — LeadSavedEvent → dispatch tag_lead_with_llm.delay()
  crm.ai.tag_requested   — AITagRequestEvent → dispatch with requested_by set

Run with: python manage.py start_llm_consumer

─────────────────────────────────────────────────────────────────────
API ENDPOINTS: core/api/views/ai_tags.py
─────────────────────────────────────────────────────────────────────
GET  /api/people/{id}/ai-tags/
  Response:
  {
    "current": { tags, persona, product_fit, urgency, reasoning,
                 confidence, suggested_stage, ai_tagged_at,
                 ai_tag_status, model_used },
    "history": [ ...previous versions with timestamps ],
    "override": null | { tags, persona, ..., overridden_by, override_note }
  }

POST /api/people/{id}/ai-tags/retag/
  Publishes AITagRequestEvent to RabbitMQ.
  Returns: { "status": "queued", "message": "Re-analysis in progress..." }
  Frontend polls via WebSocket for the ai_tags_ready event.

PATCH /api/people/{id}/ai-tags/
  Body: { tags, persona, product_fit, urgency, override_note }
  Writes to Neo4j with ai_tag_status = "overridden"
  Broadcasts ai_tags_overridden via WebSocket.
  Keeps the AI version in history — never deletes it.
  Returns: updated tag object

─────────────────────────────────────────────────────────────────────
MANAGEMENT COMMAND: manage.py test_llm_tagger
─────────────────────────────────────────────────────────────────────
  Takes a --person-id flag, runs the tagger, prints the result to stdout.
  Useful for testing the LLM pipeline without the full RabbitMQ flow.
```

---

## Phase 11 (continued) — Next.js AI Tag UI Components

**Prompt Claude:**
```
Build the AI tagging UI components in the Next.js frontend.

─────────────────────────────────────────────────────────────────────
COMPONENT: components/ai/AITagBadge.tsx
─────────────────────────────────────────────────────────────────────
A compact badge row shown on the LeadTable and KanbanCard.
Props: { tags: string[], persona: string, urgency: "high"|"medium"|"low",
         confidence: number, status: "auto"|"manual"|"overridden"|"pending" }

Render:
- Urgency dot (red/yellow/green) + urgency label
- Persona pill (e.g. "Technical Executive")
- First 2 tags as colored chips (overflow "+N more" tooltip)
- Confidence bar (thin progress, shown on hover)
- If status="overridden": small pencil icon indicating human override
- If status="pending" or null: pulsing "AI analyzing..." skeleton

─────────────────────────────────────────────────────────────────────
COMPONENT: components/ai/AITagPanel.tsx
─────────────────────────────────────────────────────────────────────
Full panel shown in the LeadDetailPanel sidebar (right section).
Props: { personId: string, aiData: AITagData, onOverride, onRetag }

Sections:
1. Header row: "AI Analysis" label + "Re-analyze" button + "Edit" button
   - "Re-analyze" → POST /api/people/{id}/ai-tags/retag/ → show spinner
   - While waiting: subscribe to WebSocket for ai_tags_ready event for this personId
   - On receive: update state with new tags (smooth transition)

2. Tags cloud:
   - All tags as colored chips grouped by category
   - Category labels: Role, Intent, Buyer Type, Temperature, Source

3. Product Fit:
   - Highlighted product name pill
   - Confidence percentage as a circular arc or bar

4. Reasoning box:
   - Light background card
   - AI reasoning text (2-4 sentences)
   - Model used + timestamp in fine print
   - "✨ Generated by Claude" attribution

5. Suggested Stage:
   - Show suggested stage with arrow → current stage
   - "Apply suggestion" button if they differ

6. If status = "overridden":
   - Show override note + who overrode it
   - "View AI original" toggle to compare

─────────────────────────────────────────────────────────────────────
COMPONENT: components/ai/AITagOverrideModal.tsx
─────────────────────────────────────────────────────────────────────
Modal for manually editing/overriding AI tags.
Props: { personId, currentTags: AITagData, onSave, onClose }

Form fields:
- Tags: multi-select chips from VALID_TAGS vocabulary (grouped by category)
  User can toggle tags on/off. Currently active tags highlighted.
- Persona: free text input (with AI suggestion pre-filled)
- Product Fit: select dropdown from product list
- Urgency: radio buttons (High / Medium / Low) with color indicators
- Override Note: textarea — "Why are you overriding?" (required)

On save → PATCH /api/people/{id}/ai-tags/
Show success toast: "Tags updated. AI version preserved in history."

─────────────────────────────────────────────────────────────────────
COMPONENT: components/live/LiveFeedDrawer.tsx (update existing)
─────────────────────────────────────────────────────────────────────
Update the existing LiveFeedDrawer to handle the new WebSocket event types:

  "new_lead"            → existing green card
  "ai_tags_ready"       → purple card with ✨ icon
                           Shows: person name + top 2 tags + persona
                           Clicking it opens that person's detail panel
  "ai_tags_overridden"  → grey card "Tags manually updated by {user}"

─────────────────────────────────────────────────────────────────────
LEADS TABLE UPDATE: components/leads/LeadTable.tsx
─────────────────────────────────────────────────────────────────────
Add two new columns to the leads table:
  "AI Tags"   → render <AITagBadge> component
  "Persona"   → text label from ai_persona field

Add filter in LeadFilters:
  "AI Persona" dropdown — populated from distinct personas in the data
  "Urgency" filter — High / Medium / Low
  "Untagged" toggle — shows only leads with ai_tag_status = null

Use TypeScript. Match existing dark theme.
```

---

## Phase Summary

| Phase | What Gets Built | Est. Complexity |
|-------|----------------|-----------------|
| 1 | Docker scaffold, all services wired | Low |
| 2 | Neo4j schema + Cypher query layer | Medium |
| 3 | RabbitMQ exchange, queues, publisher SDK | Medium |
| 4 | Celery workers, lead scoring pipeline | High |
| 5 | Django REST API (all endpoints) | Medium |
| 6 | Django Channels WebSocket live feed | Medium |
| 7 | Next.js full CRM frontend | High |
| 8 | Bookkeeper integration + simulator | Low |
| 9 | Apify LinkedIn webhook integration | Low |
| 10 | Auth, tests, production hardening | Medium |
| 11 | LLM lead tagging (Claude API) + UI | High |

---

## LLM Integration Tips

**Separate Celery queue is critical.** LLM calls can take 2-5 seconds. Keep them on
the `llm` queue with dedicated workers so slow AI tasks never block fast lead ingestion.

**Always store reasoning.** The `reasoning` field from Claude is the most valuable output
for your team — it explains *why* a lead is tagged a certain way. Surface it prominently.

**Override ≠ delete.** When a user overrides AI tags, keep the AI version in history.
Over time this creates a training signal: you can see where Claude's judgment diverged
from your team's and fine-tune your system prompt accordingly.

**Prompt iteration workflow:**
1. Run `manage.py test_llm_tagger --person-id X` after each prompt change
2. Log all LLM inputs/outputs to a `llm_calls` table in PostgreSQL for review
3. After 50+ leads, compare AI suggested_stage vs human-assigned stage to measure accuracy

**Cost estimate:** claude-sonnet-4 at ~500 tokens per lead = ~$0.0015/lead.
1000 leads/month ≈ $1.50. Negligible.
```

---

## Tips for Using These Prompts

- **Always include context**: Paste the relevant file tree from the previous phase so Claude has context.
- **One phase per Claude session**: Phases 4, 7, and 11 are large — split into sub-tasks if needed.
- **Test pipeline before UI**: Run `simulate_bookkeeper_events` after Phase 4 to validate the full pipeline before building the frontend.
- **Test LLM before wiring**: Run `manage.py test_llm_tagger` after Phase 11 backend before building the UI components.
- **Neo4j Browser**: `http://localhost:7474` — run `MATCH (n) RETURN n` to verify your graph visually.
- **RabbitMQ Management UI**: `http://localhost:15672` — watch the `crm.leads.llm_tagging` queue drain in real time.
