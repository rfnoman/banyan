# GraphCRM — RabbitMQ Integration Guide

Send contact events from your application to GraphCRM via RabbitMQ. When your app creates or updates a contact, publish a message and the CRM will automatically:

- Create or update the Person and Business in Neo4j (idempotent — safe to send duplicates)
- Compute a lead score (0–100)
- Trigger AI tagging via Claude API
- Track your app as a referral source on the contact

---

## Quick Start

### 1. Connection

Connect to the same RabbitMQ instance the CRM uses:

```
Host:     rabbitmq (or localhost if running outside Docker)
Port:     5672
Username: guest
Password: guest
Vhost:    /
```

**Connection URL:** `amqp://guest:guest@rabbitmq:5672/`

### 2. Publish a Message

| Parameter       | Value                               |
|-----------------|-------------------------------------|
| **Exchange**    | `crm.topic`                         |
| **Routing Key** | `lead.created.<your_app_name>`      |
| **Content-Type**| `application/json`                  |
| **Delivery Mode**| `2` (persistent)                   |

Replace `<your_app_name>` with your application's identifier (e.g., `greenforest`, `bookkeeper`, `billing_app`). This value is stored as the referral source on the contact.

### 3. Message Body (JSON)

```json
{
  "event_type": "lead.created",
  "source_app": "your_app_name",
  "source_product": "ProductA",
  "person": {
    "name": "Jane Smith",
    "email": "jane@example.com",
    "title": "VP of Engineering",
    "company": "Acme Corp",
    "linkedin_url": "https://linkedin.com/in/janesmith",
    "location": "New York, NY"
  },
  "company": {
    "name": "Acme Corp",
    "industry": "Technology",
    "size": "200",
    "website": "https://acme.com"
  },
  "trigger": "contact_created",
  "score_hints": {
    "is_paid": true
  },
  "raw_context": "Jane Smith is a VP of Engineering at Acme Corp. She signed up for a demo of our analytics product. Industry: Technology.",
  "timestamp": "2026-03-15T10:00:00Z"
}
```

---

## Field Reference

### Required Fields

| Field              | Type   | Description                                                  |
|--------------------|--------|--------------------------------------------------------------|
| `source_app`       | string | Your app identifier. Must match the routing key suffix.      |
| `person.name`      | string | Contact's full name.                                         |
| `person.email`     | string | Contact's email. Used as the unique key for deduplication.   |
| `raw_context`      | string | Free-text description of the contact. **This is the primary input to the AI tagger** — include as much relevant context as possible (role, interests, how they were acquired, notes). |

### Optional Fields

| Field                | Type    | Default      | Description                                              |
|----------------------|---------|--------------|----------------------------------------------------------|
| `event_type`         | string  | `lead.created` | Always `"lead.created"` for new/updated contacts.      |
| `source_product`     | string  | `ProductA`   | Which CRM product this lead is associated with.          |
| `person.title`       | string  | `null`       | Job title. Senior titles (VP, Director, CTO, CEO, Founder) boost the lead score by +20. |
| `person.company`     | string  | `null`       | Company name (also used in CompanyData if provided).     |
| `person.linkedin_url`| string  | `null`       | LinkedIn profile URL. Adds +5 to lead score.             |
| `person.location`    | string  | `null`       | Geographic location.                                     |
| `company.name`       | string  | `"Unknown"`  | Company name. Used as unique key for business dedup.     |
| `company.industry`   | string  | `null`       | Industry vertical.                                       |
| `company.size`       | string  | `null`       | Employee count as string (e.g., `"200"`). Size >= 100 adds +10 to score. |
| `company.website`    | string  | `null`       | Company website URL.                                     |
| `trigger`            | string  | —            | What caused this event (e.g., `contact_created`, `contact_updated`, `signup`, `invoice_paid`). |
| `score_hints`        | object  | `{}`         | Hints for scoring. Currently supports `is_paid` (bool) — adds +15 to score if true. |
| `timestamp`          | string  | now (UTC)    | ISO 8601 timestamp.                                      |

### Routing Keys

The CRM listens for these routing key patterns on the `crm.topic` exchange:

| Pattern            | Queue                | What Happens                                 |
|--------------------|----------------------|----------------------------------------------|
| `lead.created.*`   | `crm.leads.ingest`   | Full pipeline: create person/business, score, trigger AI tagging |
| `lead.updated.*`   | `crm.leads.ingest`   | Same pipeline (MERGE is idempotent)          |
| `action.logged.*`  | `crm.actions.process` | Log an action (email, call, meeting) on a person |
| `company.updated.*`| `crm.companies.sync`  | Update company/business data                 |

For contact creation/updates, use `lead.created.<your_app_name>` or `lead.updated.<your_app_name>`.

---

## Code Examples

### Python (pika)

```python
import json
import pika
from datetime import datetime, timezone

connection = pika.BlockingConnection(
    pika.URLParameters("amqp://guest:guest@rabbitmq:5672/")
)
channel = connection.channel()

# Declare the exchange (idempotent — safe to call every time)
channel.exchange_declare(exchange="crm.topic", exchange_type="topic", durable=True)

message = {
    "event_type": "lead.created",
    "source_app": "greenforest",
    "source_product": "ProductA",
    "person": {
        "name": "Jane Smith",
        "email": "jane@example.com",
        "title": "VP of Engineering",
        "company": "Acme Corp",
    },
    "company": {
        "name": "Acme Corp",
        "industry": "Technology",
        "size": "200",
    },
    "trigger": "contact_created",
    "score_hints": {"is_paid": True},
    "raw_context": "Jane Smith is VP of Engineering at Acme Corp. Signed up for analytics demo.",
    "timestamp": datetime.now(timezone.utc).isoformat(),
}

channel.basic_publish(
    exchange="crm.topic",
    routing_key="lead.created.greenforest",
    body=json.dumps(message, default=str),
    properties=pika.BasicProperties(
        delivery_mode=2,  # persistent
        content_type="application/json",
    ),
)

connection.close()
```

### Node.js (amqplib)

```javascript
const amqp = require("amqplib");

async function publishContact(contact) {
  const conn = await amqp.connect("amqp://guest:guest@rabbitmq:5672/");
  const ch = await conn.createChannel();

  await ch.assertExchange("crm.topic", "topic", { durable: true });

  const message = {
    event_type: "lead.created",
    source_app: "greenforest",
    source_product: "ProductA",
    person: {
      name: contact.name,
      email: contact.email,
      title: contact.title || null,
      company: contact.company || null,
    },
    company: {
      name: contact.company || "Unknown",
      industry: contact.industry || null,
      size: contact.companySize || null,
    },
    trigger: "contact_created",
    score_hints: { is_paid: contact.isPaid || false },
    raw_context: `${contact.name} is a ${contact.title} at ${contact.company}. ${contact.notes || ""}`,
    timestamp: new Date().toISOString(),
  };

  ch.publish(
    "crm.topic",
    "lead.created.greenforest",
    Buffer.from(JSON.stringify(message)),
    { persistent: true, contentType: "application/json" }
  );

  await ch.close();
  await conn.close();
}
```

### Django (using CRM's publisher directly)

If your app runs in the same Django project:

```python
from integrations.external.events import on_contact_created, on_contact_updated

# When a contact is created in your app
on_contact_created(
    contact={
        "name": "Jane Smith",
        "email": "jane@example.com",
        "title": "VP of Engineering",
        "company": "Acme Corp",
        "industry": "Technology",
        "company_size": "200",
        "is_paid": True,
        "product": "ProductA",
        "notes": "Signed up for analytics demo",
    },
    source_app="greenforest",
)

# When a contact is updated
on_contact_updated(
    contact={...},
    source_app="greenforest",
)
```

Or use Django signals:

```python
from integrations.external.hooks import greenforest_contact_created

greenforest_contact_created.send(
    sender=self.__class__,
    contact={"name": "Jane Smith", "email": "jane@example.com", ...},
)
```

---

## Alternative: HTTP Webhook

If your app cannot connect to RabbitMQ directly, use the HTTP webhook instead.

### Setup

1. Register your app in the CRM admin panel (`/admin/core/externalapp/add/`)
2. Copy the auto-generated API key

### Endpoint

```
POST /api/external/contacts/
```

### Headers

```
Content-Type: application/json
X-API-Key: <your_api_key>
```

### Request Body

```json
{
  "event_type": "contact_created",
  "contacts": [
    {
      "name": "Jane Smith",
      "email": "jane@example.com",
      "title": "VP of Engineering",
      "company": "Acme Corp",
      "industry": "Technology",
      "company_size": "200",
      "website": "https://acme.com",
      "linkedin_url": "https://linkedin.com/in/janesmith",
      "location": "New York, NY",
      "notes": "Signed up for analytics demo",
      "is_paid": true,
      "product": "ProductA"
    }
  ]
}
```

**Single-contact shorthand** — omit the `contacts` array and put fields at the top level:

```json
{
  "event_type": "contact_created",
  "name": "Jane Smith",
  "email": "jane@example.com",
  "title": "VP of Engineering",
  "company": "Acme Corp"
}
```

### Response

```json
{"processed": 1, "errors": 0}
```

### Event Types

| `event_type`       | Description                  |
|--------------------|------------------------------|
| `contact_created`  | New contact from your app    |
| `contact_updated`  | Existing contact was updated |

### cURL Example

```bash
curl -X POST http://localhost:8000/api/external/contacts/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{
    "event_type": "contact_created",
    "contacts": [
      {
        "name": "Jane Smith",
        "email": "jane@example.com",
        "title": "VP of Engineering",
        "company": "Acme Corp",
        "industry": "Technology",
        "is_paid": true,
        "product": "ProductA",
        "notes": "Interested in our analytics product"
      }
    ]
  }'
```

---

## How the CRM Processes Your Message

```
Your App publishes message
    │
    ▼
RabbitMQ exchange: crm.topic
    │  routing key: lead.created.<your_app>
    ▼
Queue: crm.leads.ingest
    │
    ▼
LeadConsumer → dispatches to Celery task
    │
    ▼
process_incoming_lead task:
    ├── MERGE Person node (deduplicated by email)
    ├── MERGE Business node (deduplicated by company name)
    ├── Link Person → Business (WORKS_AT relationship)
    ├── Track referral source (REFERRED_FROM → Source node)
    ├── Compute lead score (base 40 + bonuses, max 100)
    ├── Create IS_LEAD_FOR → Product relationship
    ├── Write analytics event to ClickHouse
    └── Publish LeadSavedEvent → triggers AI tagging (Claude API)
```

### Scoring Breakdown

| Condition                          | Points |
|------------------------------------|--------|
| Base score                         | +40    |
| Senior title (VP, Director, C-suite, Founder) | +20 |
| `is_paid: true` in score_hints     | +15    |
| Company size >= 100                | +10    |
| Source app contains "linkedin"     | +10    |
| Has linkedin_url                   | +5     |
| **Maximum**                        | **100**|

### Referral Source Tracking

Every message creates a `REFERRED_FROM` relationship between the Person and a Source node named after your `source_app`. If the same contact is sent from multiple apps, all sources are tracked:

```
(Person) -[:REFERRED_FROM {first_seen, last_seen, event_count}]-> (Source {name: "greenforest"})
(Person) -[:REFERRED_FROM {first_seen, last_seen, event_count}]-> (Source {name: "billing_app"})
```

Query referral sources in Neo4j:
```cypher
MATCH (p:Person {email: "jane@example.com"})-[r:REFERRED_FROM]->(s:Source)
RETURN s.name, r.first_seen, r.last_seen, r.event_count
```

---

## Troubleshooting

### Message not being consumed?

```bash
# Check queue depth — messages should be 0 if consumer is running
docker compose exec rabbitmq rabbitmqctl list_queues name messages consumers

# Check if consumer is running
docker compose logs celery_worker | tail -20

# Check dead-letter queue for failed messages
docker compose exec rabbitmq rabbitmqctl list_queues name messages | grep deadletter
```

### Contact not appearing in Neo4j?

```bash
# Check Celery worker logs
docker compose logs celery_worker | grep "Processing lead"

# Query Neo4j directly
docker compose exec django python manage.py shell_plus --command="
from core.graph.queries import get_person_with_connections
import json; print(json.dumps(get_person_with_connections('PERSON-ID'), indent=2))
"
```

### Test without RabbitMQ

```bash
# Simulate events (bypasses RabbitMQ, publishes directly)
docker compose exec django python manage.py simulate_external_events --source your_app_name

# Or use the synchronous pipeline debugger
docker compose exec django python manage.py debug_pipeline --event lead
```
