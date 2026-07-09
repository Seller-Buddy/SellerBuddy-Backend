import logging
import os
from urllib.parse import urlparse

import requests


logger = logging.getLogger(__name__)

SERPER_SEARCH_URL = "https://google.serper.dev/search"

SEARCH_TARGETS = [
    ("slang", "2026 한국 유행어 밈 신조어 Z세대 SNS 표현 모음"),
    ("trend", "2026 SNS 카피라이팅 후킹 문구 CTA 작성법 짧은 콘텐츠 패턴"),
]

EXCLUDED_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "x.com",
    "twitter.com",
    "tistory.com",
    "www.tistory.com",
}

EXCLUDED_URL_KEYWORDS = [
    "/video/",
    "/reel/",
    "/shorts/",
    "watch?v=",
]


def search_trend_slang_urls() -> list[dict]:
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        raise ValueError("SERPER_API_KEY가 설정되어 있지 않습니다.")

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    collected: list[dict] = []
    seen_urls: set[str] = set()

    for source_type, query in SEARCH_TARGETS:
        logger.info("Searching Serper for source_type=%s query=%s", source_type, query)
        response = requests.post(
            SERPER_SEARCH_URL,
            headers=headers,
            json={"q": query, "gl": "kr", "hl": "ko", "num": 5},
            timeout=30,
        )

        if not response.ok:
            raise RuntimeError(
                f"Serper 검색 실패 ({source_type}): {response.status_code} {response.text}"
            )

        organic_results = response.json().get("organic", [])
        for item in organic_results[:5]:
            url = item.get("link")
            if not url or url in seen_urls or should_skip_url(url):
                continue
            seen_urls.add(url)
            collected.append(
                {
                    "source_type": source_type,
                    "source_url": url,
                    "source_title": item.get("title"),
                }
            )

    return collected


def should_skip_url(url: str) -> bool:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if domain in EXCLUDED_DOMAINS:
        return True

    lowered_url = url.lower()
    if any(keyword in lowered_url for keyword in EXCLUDED_URL_KEYWORDS):
        return True

    return False
