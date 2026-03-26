"""
Neo4j sync layer — keeps Neo4j in sync with PostgreSQL for graph visualization.
Uses Django signals to detect changes, Celery tasks to sync asynchronously.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _safe_delay(task, *args):
    """Dispatch a sync task. Logs errors but does not crash the caller."""
    try:
        task.delay(*args)
    except Exception as exc:
        logger.error(
            "Neo4j sync FAILED (%s, args=%s): %s",
            task.name, args, exc, exc_info=True,
        )


# --------------- Signal receivers ---------------


@receiver(post_save, sender="core.Person")
def on_person_saved(sender, instance, **kwargs):
    _safe_delay(sync_person_node, instance.id)


@receiver(post_save, sender="core.Business")
def on_business_saved(sender, instance, **kwargs):
    _safe_delay(sync_business_node, instance.id)


@receiver(post_save, sender="core.Product")
def on_product_saved(sender, instance, **kwargs):
    _safe_delay(sync_product_node, instance.id)


@receiver(post_save, sender="core.Lead")
def on_lead_saved(sender, instance, **kwargs):
    _safe_delay(sync_lead_relationship, instance.person_id, instance.product_id, instance.stage, instance.score)


@receiver(post_delete, sender="core.Person")
def on_person_deleted(sender, instance, **kwargs):
    _safe_delay(delete_neo4j_node, "Person", instance.id)


@receiver(post_delete, sender="core.Business")
def on_business_deleted(sender, instance, **kwargs):
    _safe_delay(delete_neo4j_node, "Business", instance.id)


@receiver(post_delete, sender="core.Product")
def on_product_deleted(sender, instance, **kwargs):
    _safe_delay(delete_neo4j_node, "Product", instance.id)


# --------------- Celery tasks ---------------


@shared_task(queue="default", bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def sync_person_node(self, person_id: str):
    from core.models import Person
    from core.graph.driver import get_driver

    try:
        person = Person.objects.select_related("company").get(id=person_id)
    except Person.DoesNotExist:
        return

    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MERGE (p:Person {id: $id})
            SET p.name = $name, p.email = $email, p.title = $title,
                p.score = $score, p.source = $source,
                p.linkedin_url = $linkedin_url, p.location = $location,
                p.ai_tag_status = $ai_tag_status, p.ai_persona = $ai_persona
            """,
            id=person.id,
            name=person.name,
            email=person.email,
            title=person.title or "",
            score=person.score,
            source=person.source or "",
            linkedin_url=person.linkedin_url or "",
            location=person.location or "",
            ai_tag_status=person.ai_tag_status or "",
            ai_persona=person.ai_persona or "",
        )
        if person.company_id:
            session.run(
                """
                MATCH (p:Person {id: $pid})
                OPTIONAL MATCH (p)-[old:WORKS_AT]->()
                DELETE old
                WITH p
                MATCH (b:Business {id: $bid})
                MERGE (p)-[:WORKS_AT]->(b)
                """,
                pid=person.id,
                bid=person.company_id,
            )
        else:
            session.run(
                """
                MATCH (p:Person {id: $pid})-[r:WORKS_AT]->()
                DELETE r
                """,
                pid=person.id,
            )


@shared_task(queue="default", bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def sync_business_node(self, business_id: str):
    from core.models import Business
    from core.graph.driver import get_driver

    try:
        biz = Business.objects.get(id=business_id)
    except Business.DoesNotExist:
        return

    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MERGE (b:Business {id: $id})
            SET b.name = $name, b.industry = $industry,
                b.size = $size, b.website = $website
            """,
            id=biz.id,
            name=biz.name,
            industry=biz.industry or "",
            size=biz.size or "",
            website=biz.website or "",
        )


@shared_task(queue="default", bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def sync_product_node(self, product_id: str):
    from core.models import Product
    from core.graph.driver import get_driver

    try:
        prod = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return

    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MERGE (p:Product {id: $id})
            SET p.name = $name, p.url = $url, p.description = $description
            """,
            id=prod.id,
            name=prod.name,
            url=prod.url or "",
            description=prod.description or "",
        )


@shared_task(queue="default", bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def sync_lead_relationship(self, person_id: str, product_id: str, stage: str, score: float):
    from core.graph.driver import get_driver

    driver = get_driver()
    with driver.session() as session:
        session.run(
            """
            MATCH (p:Person {id: $pid})
            MATCH (prod:Product {id: $prod_id})
            MERGE (p)-[r:IS_LEAD_FOR]->(prod)
            SET r.stage = $stage, r.score = $score
            """,
            pid=person_id,
            prod_id=product_id,
            stage=stage,
            score=score,
        )


@shared_task(queue="default", bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def delete_neo4j_node(self, label: str, node_id: str):
    from core.graph.driver import get_driver

    driver = get_driver()
    with driver.session() as session:
        session.run(
            f"MATCH (n:{label} {{id: $id}}) DETACH DELETE n",
            id=node_id,
        )
