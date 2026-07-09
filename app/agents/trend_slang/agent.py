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
MIN_EXTRACTED_SIGNALS = 3


def collect_trend_slang_data(force_refresh: bool = False) -> dict:
    repository = TrendSlangRepository()
    recent_sources = repository.get_recent_trend_slang_sources(hours=RECENT_HOURS)

    if not force_refresh and _is_recent_cache_sufficient(recent_sources):
        logger.info("Using cached trend/slang sources count=%s", len(recent_sources))
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
                raise ValueError("정제된 본문이 비어 있습니다.")

            extracted = extract_trend_data(
                source_type=item["source_type"],
                title=item.get("source_title") or scraped.get("title"),
                cleaned_content=cleaned_content,
            )
            if not has_meaningful_trend_data(extracted):
                raise ValueError("홍보 게시글 작성에 활용할 만한 추출 결과가 부족합니다.")

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
                    avoid_expressions=extracted["avoid_expressions"],
                    summary=extracted["summary"],
                )
            )
            collected_count += 1
        except Exception as e:
            failed_count += 1
            logger.exception("Failed to process trend/slang url=%s error=%s", url, e)

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
        logger.exception("trend_slang collection failed before writer flow: %s", e)

    return repository.get_recent_trend_context_for_writer(hours=RECENT_HOURS)


def _is_recent_cache_sufficient(sources: list[dict]) -> bool:
    if len(sources) < MIN_RECENT_SOURCES:
        return False

    slang_count = sum(1 for item in sources if item["source_type"] == "slang")
    trend_count = sum(1 for item in sources if item["source_type"] == "trend")
    return slang_count >= 5 and trend_count >= 5


def has_meaningful_trend_data(extracted: dict) -> bool:
    signal_count = 0
    for key in (
        "keywords",
        "slang_expressions",
        "hook_patterns",
        "writing_patterns",
        "cta_patterns",
        "tone_features",
    ):
        if extracted.get(key):
            signal_count += 1

    return signal_count >= MIN_EXTRACTED_SIGNALS and bool(extracted.get("summary"))
