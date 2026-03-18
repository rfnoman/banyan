import json
import uuid
from datetime import datetime, timezone
from .driver import get_driver


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_or_merge_person(data: dict) -> str:
    person_id = data.get("id") or str(uuid.uuid4())
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MERGE (p:Person {email: $email})
            ON CREATE SET
                p.id = $id,
                p.name = $name,
                p.title = $title,
                p.linkedin_url = $linkedin_url,
                p.location = $location,
                p.source = $source,
                p.score = $score,
                p.created_at = $created_at
            ON MATCH SET
                p.name = $name,
                p.title = $title,
                p.linkedin_url = CASE WHEN $linkedin_url IS NOT NULL THEN $linkedin_url ELSE p.linkedin_url END,
                p.location = CASE WHEN $location IS NOT NULL THEN $location ELSE p.location END
            """,
            id=person_id,
            email=data.get("email", ""),
            name=data.get("name", ""),
            title=data.get("title"),
            linkedin_url=data.get("linkedin_url"),
            location=data.get("location"),
            source=data.get("source"),
            score=float(data.get("score", 0)),
            created_at=_now(),
        )
    return person_id


def create_or_merge_business(data: dict) -> str:
    business_id = data.get("id") or str(uuid.uuid4())
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MERGE (b:Business {name: $name})
            ON CREATE SET
                b.id = $id,
                b.industry = $industry,
                b.size = $size,
                b.website = $website,
                b.location = $location,
                b.created_at = $created_at
            ON MATCH SET
                b.industry = CASE WHEN $industry IS NOT NULL THEN $industry ELSE b.industry END,
                b.size = CASE WHEN $size IS NOT NULL THEN $size ELSE b.size END,
                b.website = CASE WHEN $website IS NOT NULL THEN $website ELSE b.website END
            """,
            id=business_id,
            name=data.get("name", ""),
            industry=data.get("industry"),
            size=data.get("size"),
            website=data.get("website"),
            location=data.get("location"),
            created_at=_now(),
        )
    return business_id


def link_person_to_business(person_id: str, business_id: str, rel_type: str = "WORKS_AT"):
    driver = get_driver()
    with driver.session() as session:
        session.run(
            f"""
            MATCH (p:Person {{id: $person_id}})
            MATCH (b:Business {{id: $business_id}})
            MERGE (p)-[:{rel_type}]->(b)
            """,
            person_id=person_id,
            business_id=business_id,
        )


def create_lead_relationship(person_id: str, product_name: str, stage: str, score: float):
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MERGE (prod:Product {name: $product_name})
            ON CREATE SET prod.id = $product_id, prod.url = null, prod.description = null, prod.created_at = $created_at
            WITH prod
            MATCH (p:Person {id: $person_id})
            MERGE (p)-[r:IS_LEAD_FOR]->(prod)
            SET r.stage = $stage, r.score = $score, r.updated_at = $updated_at
            """,
            person_id=person_id,
            product_name=product_name,
            product_id=str(uuid.uuid4()),
            stage=stage,
            score=score,
            updated_at=_now(),
            created_at=_now(),
        )


def log_action(person_id: str, action_type: str, note: str = "", channel: str = ""):
    action_id = str(uuid.uuid4())
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MATCH (p:Person {id: $person_id})
            CREATE (a:Action {
                id: $action_id,
                type: $action_type,
                note: $note,
                channel: $channel,
                timestamp: $timestamp
            })
            CREATE (p)-[:HAS_ACTION]->(a)
            """,
            person_id=person_id,
            action_id=action_id,
            action_type=action_type,
            note=note,
            channel=channel,
            timestamp=_now(),
        )
    return action_id


def get_person_with_connections(person_id: str) -> dict:
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (p:Person {id: $person_id})
            OPTIONAL MATCH (p)-[:WORKS_AT]->(b:Business)
            OPTIONAL MATCH (p)-[:IS_LEAD_FOR]->(prod:Product)
            OPTIONAL MATCH (p)-[:HAS_ACTION]->(a:Action)
            RETURN p,
                   collect(DISTINCT b) AS businesses,
                   collect(DISTINCT prod) AS products,
                   collect(DISTINCT a) AS actions
            """,
            person_id=person_id,
        )
        record = result.single()
        if not record:
            return {}
        person = dict(record["p"])
        businesses = [dict(b) for b in record["businesses"] if b]
        products = [dict(p) for p in record["products"] if p]
        actions = [dict(a) for a in record["actions"] if a]
        return {
            **person,
            "company": businesses[0] if businesses else {},
            "products": products,
            "actions": actions,
        }


def get_graph_snapshot() -> dict:
    driver = get_driver()
    with driver.session() as session:
        nodes_result = session.run(
            """
            MATCH (n)
            WHERE n:Person OR n:Business OR n:Product
            RETURN id(n) AS neo_id, labels(n) AS labels, properties(n) AS props
            LIMIT 500
            """
        )
        nodes = []
        for record in nodes_result:
            node = {
                "id": str(record["neo_id"]),
                "label": record["labels"][0] if record["labels"] else "Unknown",
                **{k: v for k, v in record["props"].items() if k in ("id", "name", "email", "title")},
            }
            nodes.append(node)

        edges_result = session.run(
            """
            MATCH (a)-[r]->(b)
            WHERE (a:Person OR a:Business) AND (b:Person OR b:Business OR b:Product)
            RETURN a.id AS source, b.id AS target, type(r) AS rel_type
            LIMIT 1000
            """
        )
        edges = [
            {
                "source": str(r["source"]),
                "target": str(r["target"]),
                "type": r["rel_type"],
            }
            for r in edges_result
        ]
    return {"nodes": nodes, "edges": edges}


def update_ai_tags(person_id: str, ai_result: dict):
    tags = ai_result.get("tags", [])
    tags_json = json.dumps(tags)

    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MATCH (p:Person {id: $person_id})
            SET p.ai_tags = $tags,
                p.ai_persona = $persona,
                p.ai_product_fit = $product_fit,
                p.ai_urgency = $urgency,
                p.ai_reasoning = $reasoning,
                p.ai_tagged_at = $ai_tagged_at,
                p.ai_tag_status = $ai_tag_status,
                p.ai_suggested_stage = $suggested_stage,
                p.ai_confidence = $confidence,
                p.ai_model_used = $model_used,
                p.ai_tokens_used = $tokens_used
            """,
            person_id=person_id,
            tags=tags_json,
            persona=ai_result.get("persona", ""),
            product_fit=ai_result.get("product_fit", ""),
            urgency=ai_result.get("urgency", "medium"),
            reasoning=ai_result.get("reasoning", ""),
            ai_tagged_at=ai_result.get("ai_tagged_at", _now()),
            ai_tag_status=ai_result.get("ai_tag_status", "auto"),
            suggested_stage=ai_result.get("suggested_stage", ""),
            confidence=float(ai_result.get("confidence", 0.0)),
            model_used=ai_result.get("model_used", ""),
            tokens_used=int(ai_result.get("tokens_used", 0)),
        )


def get_pending_ai_tagging(limit: int = 50) -> list:
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (p:Person)
            WHERE p.ai_tag_status IS NULL OR p.ai_tag_status = ''
            RETURN p.id AS id, p.name AS name, p.email AS email
            LIMIT $limit
            """,
            limit=limit,
        )
        return [dict(r) for r in result]


def get_ai_tag_history(person_id: str) -> list:
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (p:Person {id: $person_id})
            RETURN p.ai_tags AS tags,
                   p.ai_persona AS persona,
                   p.ai_product_fit AS product_fit,
                   p.ai_urgency AS urgency,
                   p.ai_reasoning AS reasoning,
                   p.ai_tagged_at AS ai_tagged_at,
                   p.ai_tag_status AS ai_tag_status,
                   p.ai_suggested_stage AS suggested_stage,
                   p.ai_confidence AS confidence,
                   p.ai_model_used AS model_used,
                   p.ai_tokens_used AS tokens_used
            """,
            person_id=person_id,
        )
        record = result.single()
        if not record or not record["ai_tagged_at"]:
            return []
        tags = record["tags"]
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        return [
            {
                "tags": tags or [],
                "persona": record["persona"],
                "product_fit": record["product_fit"],
                "urgency": record["urgency"],
                "reasoning": record["reasoning"],
                "ai_tagged_at": record["ai_tagged_at"],
                "ai_tag_status": record["ai_tag_status"],
                "suggested_stage": record["suggested_stage"],
                "confidence": record["confidence"],
                "model_used": record["model_used"],
                "tokens_used": record["tokens_used"],
            }
        ]


def update_person_score(person_id: str, score: float):
    driver = get_driver()
    with driver.session() as session:
        session.run(
            "MATCH (p:Person {id: $person_id}) SET p.score = $score",
            person_id=person_id,
            score=score,
        )


def get_business_by_id(business_id: str) -> dict:
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (b:Business {id: $business_id}) RETURN b",
            business_id=business_id,
        )
        record = result.single()
        if not record:
            return {}
        return dict(record["b"])


def get_people_by_business(business_id: str) -> list:
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (p:Person)-[:WORKS_AT]->(b:Business {id: $business_id})
            RETURN p
            ORDER BY p.name
            """,
            business_id=business_id,
        )
        return [dict(r["p"]) for r in result]


def get_all_people(limit: int = 100, offset: int = 0) -> list:
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[:WORKS_AT]->(b:Business)
            RETURN p, b
            ORDER BY p.created_at DESC
            SKIP $offset LIMIT $limit
            """,
            limit=limit,
            offset=offset,
        )
        people = []
        for record in result:
            person = dict(record["p"])
            if record["b"]:
                person["company"] = dict(record["b"])
            people.append(person)
        return people


def get_all_businesses(limit: int = 100, offset: int = 0) -> list:
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (b:Business) RETURN b ORDER BY b.created_at DESC SKIP $offset LIMIT $limit",
            limit=limit,
            offset=offset,
        )
        return [dict(r["b"]) for r in result]


def get_leads(product: str = None, stage: str = None, score_min: float = None,
              ai_persona: str = None, limit: int = 100) -> list:
    filters = []
    params = {"limit": limit}

    if product:
        filters.append("prod.name = $product")
        params["product"] = product
    if stage:
        filters.append("r.stage = $stage")
        params["stage"] = stage
    if score_min is not None:
        filters.append("p.score >= $score_min")
        params["score_min"] = score_min
    if ai_persona:
        filters.append("p.ai_persona = $ai_persona")
        params["ai_persona"] = ai_persona

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    query = f"""
        MATCH (p:Person)-[r:IS_LEAD_FOR]->(prod:Product)
        OPTIONAL MATCH (p)-[:WORKS_AT]->(b:Business)
        {where_clause}
        RETURN p, r, prod, b
        ORDER BY p.score DESC
        LIMIT $limit
    """
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, **params)
        leads = []
        for record in result:
            person = dict(record["p"])
            rel = dict(record["r"])
            product_node = dict(record["prod"])
            company = dict(record["b"]) if record["b"] else {}
            leads.append({**person, "lead_stage": rel.get("stage"), "product": product_node, "company": company})
        return leads


def update_lead_stage(person_id: str, stage: str) -> int:
    """Update stage on all IS_LEAD_FOR relationships for a person. Returns count updated."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (p:Person {id: $person_id})-[r:IS_LEAD_FOR]->(:Product)
            SET r.stage = $stage
            RETURN count(r) AS updated
            """,
            person_id=person_id,
            stage=stage,
        )
        record = result.single()
        return record["updated"] if record else 0


def get_analytics_summary() -> dict:
    driver = get_driver()
    with driver.session() as session:
        counts = session.run(
            """
            MATCH (p:Person) WITH count(p) AS people
            MATCH (b:Business) WITH people, count(b) AS businesses
            MATCH (p2:Person)-[:IS_LEAD_FOR]->(prod:Product) WITH people, businesses, count(p2) AS leads
            RETURN people, businesses, leads
            """
        ).single()

        stage_dist = session.run(
            """
            MATCH (p:Person)-[r:IS_LEAD_FOR]->(:Product)
            RETURN r.stage AS stage, count(*) AS count
            ORDER BY count DESC
            """
        )

        score_avg = session.run(
            "MATCH (p:Person) WHERE p.score > 0 RETURN avg(p.score) AS avg_score"
        ).single()

    return {
        "people": counts["people"] if counts else 0,
        "businesses": counts["businesses"] if counts else 0,
        "leads": counts["leads"] if counts else 0,
        "avg_score": round(score_avg["avg_score"] or 0, 2) if score_avg else 0,
        "stage_distribution": [{"stage": r["stage"], "count": r["count"]} for r in stage_dist],
    }


def get_all_products(limit: int = 500, offset: int = 0) -> list:
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (prod:Product) RETURN prod ORDER BY prod.name SKIP $offset LIMIT $limit",
            limit=limit,
            offset=offset,
        )
        return [dict(r["prod"]) for r in result]


def get_product_by_id(product_id: str) -> dict:
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (prod:Product {id: $product_id}) RETURN prod",
            product_id=product_id,
        )
        record = result.single()
        if not record:
            return {}
        return dict(record["prod"])


def get_product_with_leads(product_id: str) -> dict:
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (prod:Product {id: $product_id})
            OPTIONAL MATCH (p:Person)-[r:IS_LEAD_FOR]->(prod)
            OPTIONAL MATCH (p)-[:WORKS_AT]->(b:Business)
            RETURN prod,
                   collect(DISTINCT {
                       person: properties(p),
                       stage: r.stage,
                       score: r.score,
                       company: properties(b)
                   }) AS leads
            """,
            product_id=product_id,
        )
        record = result.single()
        if not record:
            return {}
        product = dict(record["prod"])
        leads = []
        for lead in record["leads"]:
            if lead["person"]:
                entry = dict(lead["person"])
                entry["lead_stage"] = lead["stage"]
                entry["lead_score"] = lead["score"]
                entry["company"] = dict(lead["company"]) if lead["company"] else {}
                leads.append(entry)
        product["leads"] = leads
        return product


def create_or_merge_product(data: dict) -> str:
    product_id = data.get("id") or str(uuid.uuid4())
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MERGE (prod:Product {name: $name})
            ON CREATE SET
                prod.id = $id,
                prod.url = $url,
                prod.description = $description,
                prod.created_at = $created_at
            ON MATCH SET
                prod.url = CASE WHEN $url IS NOT NULL THEN $url ELSE prod.url END,
                prod.description = CASE WHEN $description IS NOT NULL THEN $description ELSE prod.description END
            """,
            id=product_id,
            name=data.get("name", ""),
            url=data.get("url"),
            description=data.get("description"),
            created_at=_now(),
        )
    return product_id


def update_product(product_id: str, data: dict):
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MATCH (prod:Product {id: $product_id})
            SET prod.url = $url, prod.description = $description
            """,
            product_id=product_id,
            url=data.get("url"),
            description=data.get("description"),
        )


def delete_product(product_id: str):
    driver = get_driver()
    with driver.session() as session:
        session.run(
            "MATCH (prod:Product {id: $product_id}) DETACH DELETE prod",
            product_id=product_id,
        )


# --------------- Import queries ---------------

IMPORT_SOURCES = ["apify_linkedin", "csv_import", "xlsx_import", "api_external"]


def get_imported_people(
    sources: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    search: str = "",
) -> list:
    sources = sources or IMPORT_SOURCES
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (p:Person)
            WHERE p.source IN $sources
              AND ($search = '' OR toLower(p.name) CONTAINS toLower($search)
                   OR toLower(p.email) CONTAINS toLower($search))
            OPTIONAL MATCH (p)-[:WORKS_AT]->(b:Business)
            RETURN p, b.name AS company_name
            ORDER BY p.created_at DESC
            SKIP $offset LIMIT $limit
            """,
            sources=sources,
            search=search,
            offset=offset,
            limit=limit,
        )
        people = []
        for record in result:
            person = dict(record["p"])
            person["company_name"] = record["company_name"] or ""
            people.append(person)
        return people


def get_imported_people_count(
    sources: list[str] | None = None,
    search: str = "",
) -> int:
    sources = sources or IMPORT_SOURCES
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (p:Person)
            WHERE p.source IN $sources
              AND ($search = '' OR toLower(p.name) CONTAINS toLower($search)
                   OR toLower(p.email) CONTAINS toLower($search))
            RETURN count(p) AS total
            """,
            sources=sources,
            search=search,
        )
        record = result.single()
        return record["total"] if record else 0


def bulk_link_people_to_business(person_ids: list[str], business_id: str):
    driver = get_driver()
    with driver.session() as session:
        for pid in person_ids:
            session.run(
                """
                MATCH (p:Person {id: $person_id})
                MATCH (b:Business {id: $business_id})
                MERGE (p)-[:WORKS_AT]->(b)
                """,
                person_id=pid,
                business_id=business_id,
            )


def add_referral_source(person_id: str, source_app: str, trigger: str):
    """Track that this person was referred from a specific external app."""
    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MATCH (p:Person {id: $person_id})
            MERGE (s:Source {name: $source_app})
            ON CREATE SET s.id = $source_id, s.created_at = $now
            MERGE (p)-[r:REFERRED_FROM]->(s)
            ON CREATE SET r.first_seen = $now, r.trigger = $trigger
            SET r.last_seen = $now, r.event_count = coalesce(r.event_count, 0) + 1
            """,
            person_id=person_id,
            source_app=source_app,
            source_id=str(uuid.uuid4()),
            trigger=trigger,
            now=_now(),
        )


def get_person_referral_sources(person_id: str) -> list[dict]:
    """Get all apps that referred this person, with timestamps."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (p:Person {id: $person_id})-[r:REFERRED_FROM]->(s:Source)
            RETURN s.name AS source, r.first_seen AS first_seen,
                   r.last_seen AS last_seen, r.event_count AS event_count,
                   r.trigger AS trigger
            ORDER BY r.first_seen
            """,
            person_id=person_id,
        )
        return [dict(r) for r in result]
