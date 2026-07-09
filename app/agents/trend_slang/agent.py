import logging

from app.models.trend_slang import TrendSlangSource
from app.repositories.trend_slang_repository import TrendSlangRepository
from app.services.trend_slang.content_cleaning_service import clean_html_content
from app.services.trend_slang.serper_scrape_service import scrape_url_content
from app.services.trend_slang.serper_search_service import search_trend_slang_urls
from app.services.trend_slang.trend_extraction_service import extract_trend_data


logger = logging.getLogger(__name__)

RECENT_HOURS = 24
MIN_RECENT_SOURCES = 10


def collect_trend_slang_data(force_refresh: bool = False) -> dict:
    repository = TrendSlangRepository()
    recent_sources = repository.get_recent_trend_slang_sources(hours=RECENT_HOURS)
    logger.info(
        "trend_slang 수집 시작: 강제새로고침=%s 최근소스수=%s",
        force_refresh,
        len(recent_sources),
    )

    if not force_refresh and _is_recent_cache_sufficient(recent_sources):
        logger.info("trend_slang 캐시 사용: 최근소스수=%s", len(recent_sources))
        return {
            "cached": True,
            "total_urls": len(recent_sources),
            "collected_count": len(recent_sources),
            "failed_count": 0,
        }

    search_results = search_trend_slang_urls()
    collected_count = 0
    failed_count = 0

    for item in search_results:
        url = item["source_url"]
        try:
            scraped = scrape_url_content(url)
            cleaned_content = clean_html_content(scraped["raw_content"])
            if not cleaned_content:
                raise ValueError(
                    f"정제된 본문이 비어 있습니다. raw_length={len(scraped['raw_content'])}"
                )

            extracted = extract_trend_data(
                source_type=item["source_type"],
                title=item.get("source_title") or scraped.get("title"),
                cleaned_content=cleaned_content,
            )
            if not has_meaningful_trend_data(extracted):
                raise ValueError(
                    "홍보 게시글 작성에 활용할 만한 추출 결과가 부족합니다. "
                    f"keywords={len(extracted['keywords'])} "
                    f"slang={len(extracted['slang_expressions'])} "
                    f"hooks={len(extracted['hook_patterns'])} "
                    f"writing={len(extracted['writing_patterns'])} "
                    f"cta={len(extracted['cta_patterns'])} "
                    f"tone={len(extracted['tone_features'])}"
                )

            repository.save_source(
                TrendSlangSource(
                    source_type=item["source_type"],
                    source_url=url,
                    source_title=item.get("source_title") or scraped.get("title"),
                    raw_content=scraped["raw_content"],
                    cleaned_content=cleaned_content,
                    keywords=extracted["keywords"],
                    slang_expressions=extracted["slang_expressions"],
                    hook_patterns=extracted["hook_patterns"],
                    writing_patterns=extracted["writing_patterns"],
                    cta_patterns=extracted["cta_patterns"],
                    tone_features=extracted["tone_features"],
                )
            )
            collected_count += 1
            logger.info(
                "trend_slang DB 저장 완료: source_type=%s 제목=%s 주소=%s 저장값=%s",
                item["source_type"],
                item.get("source_title") or scraped.get("title") or "",
                url,
                {
                    "keywords": extracted["keywords"],
                    "slang_expressions": extracted["slang_expressions"],
                    "hook_patterns": extracted["hook_patterns"],
                    "writing_patterns": extracted["writing_patterns"],
                    "cta_patterns": extracted["cta_patterns"],
                    "tone_features": extracted["tone_features"],
                },
            )
        except Exception as e:
            failed_count += 1
            logger.exception(
                "trend_slang URL 처리 실패: url=%s source_type=%s 제목=%s 오류=%s",
                url,
                item["source_type"],
                item.get("source_title"),
                e,
            )

    return {
        "cached": False,
        "total_urls": len(search_results),
        "collected_count": collected_count,
        "failed_count": failed_count,
    }


def prepare_trend_context_for_writer(force_refresh: bool = False) -> dict:
    repository = TrendSlangRepository()

    try:
        collect_trend_slang_data(force_refresh=force_refresh)
    except Exception as e:
        logger.exception("writer 실행 전 trend_slang 준비 실패: 오류=%s", e)

    return repository.get_recent_trend_context_for_writer(hours=RECENT_HOURS)


def _is_recent_cache_sufficient(sources: list[dict]) -> bool:
    if len(sources) < MIN_RECENT_SOURCES:
        return False

    slang_count = sum(1 for item in sources if item["source_type"] == "slang")
    trend_count = sum(1 for item in sources if item["source_type"] == "trend")
    return slang_count >= 5 and trend_count >= 5


def has_meaningful_trend_data(extracted: dict) -> bool:
    return bool(extracted.get("keywords") or extracted.get("slang_expressions"))
