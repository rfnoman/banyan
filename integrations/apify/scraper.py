import logging
import os
import requests

logger = logging.getLogger(__name__)

APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
LINKEDIN_SCRAPER_ACTOR = "apify/linkedin-profile-scraper"


class ApifyScraper:
    def __init__(self, token: str = None):
        self.token = token or APIFY_API_TOKEN
        self.base_url = "https://api.apify.com/v2"

    def start_linkedin_scrape(self, search_url: str, product: str, webhook_url: str = None) -> str:
        if not self.token:
            raise ValueError("APIFY_API_TOKEN not set")

        payload = {
            "startUrls": [{"url": search_url}],
            "proxy": {"useApifyProxy": True},
        }
        if webhook_url:
            payload["webhooks"] = [{
                "eventTypes": ["ACTOR.RUN.SUCCEEDED"],
                "requestUrl": webhook_url,
                "payloadTemplate": f'{{"product": "{product}", "items": {{{{resource.defaultDatasetId}}}}}}',
            }]

        response = requests.post(
            f"{self.base_url}/acts/{LINKEDIN_SCRAPER_ACTOR}/runs",
            params={"token": self.token},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        run_id = response.json()["data"]["id"]
        logger.info("Apify LinkedIn scrape started: run_id=%s product=%s", run_id, product)
        return run_id

    def fetch_dataset(self, dataset_id: str) -> list:
        response = requests.get(
            f"{self.base_url}/datasets/{dataset_id}/items",
            params={"token": self.token, "format": "json"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
