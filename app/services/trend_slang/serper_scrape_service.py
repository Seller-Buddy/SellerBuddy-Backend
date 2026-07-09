import logging
import re

import requests


logger = logging.getLogger(__name__)


def scrape_url_content(url: str) -> dict:
    logger.info("Scraping trend/slang url=%s", url)
    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            )
        },
        timeout=30,
    )
    response.raise_for_status()

    html = response.text
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else None

    return {
        "title": title,
        "raw_content": html,
    }
