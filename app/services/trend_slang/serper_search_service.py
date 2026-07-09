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
        logger.info("Serper 검색 시작: source_type=%s 검색어=%s", source_type, query)
        try:
            response = requests.post(
                SERPER_SEARCH_URL,
                headers=headers,
                json={"q": query, "gl": "kr", "hl": "ko", "num": 10},
                timeout=30,
            )
        except requests.RequestException as e:
            logger.exception("Serper 요청 실패: source_type=%s 검색어=%s 오류=%s", source_type, query, e)
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

        organic_results = response.json().get("organic", [])
        logger.info(
            "Serper 검색 결과 수신: organic_count=%s source_type=%s",
            len(organic_results),
            source_type,
        )
        accepted_count = 0
        for item in organic_results:
            if accepted_count >= 5:
                break
            url = item.get("link")
            if not url:
                logger.warning("Serper 결과에 URL 없음: source_type=%s item=%s", source_type, item)
                continue
            if url in seen_urls:
                logger.info("trend_slang 중복 URL 제외: url=%s", url)
                continue
            if should_skip_url(url):
                logger.warning("trend_slang 필터링 URL 제외: url=%s source_type=%s", url, source_type)
                continue
            seen_urls.add(url)
            collected.append(
                {
                    "source_type": source_type,
                    "source_url": url,
                    "source_title": item.get("title"),
                }
            )
            accepted_count += 1

    logger.info("trend_slang 후보 URL 수집 완료: 후보수=%s", len(collected))
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
