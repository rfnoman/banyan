from core.messaging.events import LeadCreatedEvent, PersonData, CompanyData


def apify_profile_to_lead_event(profile: dict, product: str) -> LeadCreatedEvent:
    name = profile.get("name") or f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip()
    company_name = profile.get("company") or profile.get("currentCompany") or "Unknown"
    headline = profile.get("headline") or profile.get("title") or ""

    raw_context = (
        f"{name}, {headline} at {company_name}. "
        f"{profile.get('summary', '')} "
        f"Mutual connections: {profile.get('mutualCount', 0)}."
    ).strip()

    return LeadCreatedEvent(
        source_app="apify_linkedin",
        source_product=product,
        person=PersonData(
            name=name,
            email=profile.get("email") or f"{name.lower().replace(' ', '.')}@linkedin.invalid",
            title=headline,
            company=company_name,
            linkedin_url=profile.get("profileUrl") or profile.get("url"),
            location=profile.get("location"),
        ),
        company=CompanyData(
            name=company_name,
            industry=profile.get("industry"),
            size=str(profile.get("companySize", "")),
            website=profile.get("companyWebsite"),
        ),
        trigger="linkedin_scrape",
        score_hints={"is_paid": False},
        raw_context=raw_context,
    )
