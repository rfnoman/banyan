import json
import logging
from datetime import datetime, timezone

import anthropic
from django.conf import settings

from .prompt_builder import build_system_prompt, build_user_prompt
from .schema import AITagResult
from core.db.queries import get_person_with_connections, update_ai_tags

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"


class LeadTagger:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.products = settings.CRM_PRODUCTS

    def tag_person(self, person_id: str, raw_context: str = "",
                   trigger: str = "", source_app: str = "") -> AITagResult:
        person_data = get_person_with_connections(person_id)
        if not person_data:
            raise ValueError(f"Person {person_id} not found in Neo4j")

        company_data = person_data.get("company", {})

        system = build_system_prompt(self.products)
        user = build_user_prompt(person_data, company_data, raw_context, trigger, source_app)

        logger.info("Calling Claude for person_id=%s trigger=%s", person_id, trigger)

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        raw_json = response.content[0].text.strip()
        result_dict = json.loads(raw_json)
        result = AITagResult(**result_dict)

        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        logger.info(
            "LLM tagging complete: person_id=%s persona=%s urgency=%s tokens=%d",
            person_id, result.persona, result.urgency, tokens_used,
        )

        update_ai_tags(person_id, {
            **result.model_dump(),
            "ai_tagged_at": datetime.now(timezone.utc).isoformat(),
            "ai_tag_status": "auto",
            "model_used": MODEL,
            "tokens_used": tokens_used,
        })

        return result

    def retag_person(self, person_id: str, requested_by: str) -> AITagResult:
        person_data = get_person_with_connections(person_id)
        result = self.tag_person(
            person_id,
            raw_context=person_data.get("ai_reasoning", ""),
            trigger="manual_retag",
            source_app=f"ui:{requested_by}",
        )
        update_ai_tags(person_id, {"ai_tag_status": "manual"})
        return result
