def build_system_prompt(products: list[str]) -> str:
    return f"""You are a B2B sales intelligence assistant for a software company \
that sells these products: {', '.join(products)}.

Your job is to analyze incoming leads and assign structured tags based on \
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

Allowed tags: decision-maker, influencer, champion, end-user, blocker, \
high-intent, evaluating, early-research, not-ready, technical-buyer, \
economic-buyer, executive-sponsor, hot, warm, cold, inbound, outbound, \
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

EXISTING TAGS (if any): {person.get('ai_tags', [])}

Based on all of the above, return the JSON tag object.
"""
