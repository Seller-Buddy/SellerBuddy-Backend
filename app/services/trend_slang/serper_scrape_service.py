import logging
import re

import requests


logger = logging.getLogger(__name__)


def scrape_url_content(url: str) -> dict:
    logger.info("trend_slang 크롤링 시작: url=%s", url)
    try:
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
    except requests.RequestException as e:
        logger.exception("trend_slang 크롤링 요청 실패: url=%s 오류=%s", url, e)
        raise
    logger.info(
        "trend_slang 크롤링 응답 수신: url=%s 상태코드=%s HTML길이=%s",
        url,
        response.status_code,
        len(response.text or ""),
    )
    try:
        response.raise_for_status()
    except requests.HTTPError:
        logger.exception("trend_slang 크롤링 응답 실패: url=%s 상태코드=%s 응답일부=%s", url, response.status_code, response.text[:500])
        raise

    html = response.text
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else None

    return {
        "title": title,
        "raw_content": html,
    }
