"""LinkedIn profile scraper using the open-source linkedin-api package."""
import logging
import os
import re

logger = logging.getLogger(__name__)

LINKEDIN_EMAIL = os.environ.get("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.environ.get("LINKEDIN_PASSWORD", "")


def _extract_vanity_name(linkedin_url: str) -> str:
    """Extract the vanity name (public identifier) from a LinkedIn profile URL.

    Handles URLs like:
        https://www.linkedin.com/in/johndoe
        https://linkedin.com/in/johndoe/
        linkedin.com/in/johndoe?param=value
    """
    match = re.search(r"linkedin\.com/in/([^/?#]+)", linkedin_url)
    if not match:
        raise ValueError(f"Could not extract profile ID from URL: {linkedin_url}")
    return match.group(1).strip("/")


class LinkedInScraper:
    """Scrapes LinkedIn profiles using linkedin-api (requires LinkedIn credentials)."""

    def __init__(self, email: str = None, password: str = None):
        self.email = email or LINKEDIN_EMAIL
        self.password = password or LINKEDIN_PASSWORD
        self._api = None

    @property
    def is_configured(self) -> bool:
        return bool(self.email and self.password)

    def _get_api(self):
        """Lazily initialize the LinkedIn API client."""
        if self._api is None:
            if not self.is_configured:
                raise ValueError(
                    "LinkedIn credentials not configured. "
                    "Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables."
                )
            from linkedin_api import Linkedin
            self._api = Linkedin(self.email, self.password)
        return self._api

    def scrape_profile(self, linkedin_url: str) -> dict:
        """Scrape a single LinkedIn profile by URL.

        Returns a dict with profile data and contact info merged together.
        """
        vanity_name = _extract_vanity_name(linkedin_url)
        api = self._get_api()

        logger.info("Scraping LinkedIn profile: %s", vanity_name)

        profile = api.get_profile(vanity_name)
        try:
            contact_info = api.get_profile_contact_info(vanity_name)
        except Exception as exc:
            logger.warning("Could not fetch contact info for %s: %s", vanity_name, exc)
            contact_info = {}

        # Merge contact info into profile dict for downstream processing
        profile["_contact_info"] = contact_info
        profile["_linkedin_url"] = linkedin_url

        return profile
