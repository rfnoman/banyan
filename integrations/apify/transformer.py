"""Transform raw LinkedIn profile data into normalized dicts for the review form."""


def normalize_profile_for_review(profile: dict) -> dict:
    """Transform a raw linkedin-api profile dict into a flat dict for the review form.

    The profile dict comes from LinkedInScraper.scrape_profile() which merges
    get_profile() output with _contact_info from get_profile_contact_info().

    Returns a dict with empty strings for missing fields (not None),
    so Alpine.js can bind cleanly.
    """
    # Name
    first = profile.get("firstName", "")
    last = profile.get("lastName", "")
    name = f"{first} {last}".strip()

    # Title / headline
    title = profile.get("headline", "")

    # Location
    location = profile.get("geoLocationName", "") or profile.get("locationName", "")

    # Email from contact info
    contact_info = profile.get("_contact_info", {})
    emails = contact_info.get("email_address") or ""
    # email_address can be a string or None
    email = emails if isinstance(emails, str) else ""

    # LinkedIn URL (passed through from scraper)
    linkedin_url = profile.get("_linkedin_url", "")

    # Current company from experience
    company_name = ""
    company_industry = ""
    experience = profile.get("experience", [])
    if experience:
        # Find current position (no end date) or use most recent
        current = None
        for exp in experience:
            time_period = exp.get("timePeriod", {})
            if not time_period.get("endDate"):
                current = exp
                break
        if current is None:
            current = experience[0]

        company_name = current.get("companyName", "")
        # Update title from current position if headline is empty
        if not title:
            title = current.get("title", "")

    # Industry from profile
    company_industry = profile.get("industryName", "")

    return {
        "name": name,
        "email": email,
        "title": title,
        "company_name": company_name,
        "company_industry": company_industry,
        "location": location,
        "linkedin_url": linkedin_url,
    }
