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

DEFAULT_QUERY_BY_SOURCE_TYPE = dict(SEARCH_TARGETS)

EXCLUDED_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "tistory.com",
    "threads.com",
}

EXCLUDED_URL_KEYWORDS = [
    "/video/",
    "/reel/",
    "/shorts/",
    "watch?v=",
]


def search_trend_slang_urls() -> list[dict]:
    collected: list[dict] = []
    seen_urls: set[str] = set()

    for source_type, query in SEARCH_TARGETS:
        results = search_trend_slang_urls_by_type(
            source_type=source_type,
            query=query,
            seen_urls=seen_urls,
            limit=5,
        )
        collected.extend(results)
        seen_urls.update(item["source_url"] for item in results)

    return collected


def search_trend_slang_urls_by_type(
    source_type: str,
    query: str | None = None,
    seen_urls: set[str] | None = None,
    limit: int = 5,
) -> list[dict]:
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        raise ValueError("SERPER_API_KEY가 설정되어 있지 않습니다.")

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    query = query or DEFAULT_QUERY_BY_SOURCE_TYPE[source_type]
    seen_urls = seen_urls or set()
    try:
        response = requests.post(
            SERPER_SEARCH_URL,
            headers=headers,
            json={"q": query, "gl": "kr", "hl": "ko", "num": 10},
            timeout=30,
        )
    except requests.RequestException as e:
        logger.exception("Serper 요청 실패: source_type=%s 오류=%s", source_type, e)
        raise RuntimeError(f"Serper 요청 실패 ({source_type}): {e}") from e

    if not response.ok:
        logger.error(
            "Serper 검색 실패: source_type=%s 상태코드=%s 응답=%s",
            source_type,
            response.status_code,
            response.text,
        )
        raise RuntimeError(
            f"Serper 검색 실패 ({source_type}): {response.status_code} {response.text}"
        )

    collected: list[dict] = []
    organic_results = response.json().get("organic", [])
    for item in organic_results:
        if len(collected) >= limit:
            break
        url = item.get("link")
        if not url:
            logger.warning("Serper 결과에 URL 없음: source_type=%s", source_type)
            continue
        if url in seen_urls:
            continue
        if should_skip_url(url):
            continue
        seen_urls.add(url)
        collected.append(
            {
                "source_type": source_type,
                "source_url": url,
                "source_title": item.get("title"),
            }
        )
        logger.info(
            "찾은 사이트: source_type=%s 이름=%s 주소=%s",
            source_type,
            item.get("title") or "",
            url,
        )
    return collected


def should_skip_url(url: str) -> bool:
    parsed = urlparse(url)
    domain = parsed.netloc.lower().removeprefix("www.")

    if any(domain == excluded or domain.endswith(f".{excluded}") for excluded in EXCLUDED_DOMAINS):
        return True

    lowered_url = url.lower()
    if any(keyword in lowered_url for keyword in EXCLUDED_URL_KEYWORDS):
        return True

    return False
