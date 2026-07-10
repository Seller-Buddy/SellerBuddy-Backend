import logging
from typing import Any, Literal, TypedDict

from app.core.llm_service import call_llm, parse_llm_json
from app.models.trend_slang import TrendSlangSource
from app.prompts.trend_slang_prompts import build_trend_route_decision_prompt
from app.repositories.trend_slang_repository import TrendSlangRepository
from app.services.trend_slang.content_cleaning_service import clean_html_content
from app.services.trend_slang.serper_scrape_service import scrape_url_content
from app.services.trend_slang.serper_search_service import (
    DEFAULT_QUERY_BY_SOURCE_TYPE,
    search_trend_slang_urls_by_type,
)
from app.services.trend_slang.trend_extraction_service import extract_trend_data

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - dependency is declared in requirements.txt
    END = "__end__"
    StateGraph = None


logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 24 * 7
RETENTION_DAYS = 30
MIN_RECENT_SOURCES = 10
SOURCE_TYPES = ("slang", "trend")
TARGET_COUNTS = {"slang": 5, "trend": 5}
MAX_ATTEMPTS_PER_TYPE = 3
MAX_TOTAL_CANDIDATE_URLS = 30


class TrendRouteDecision(TypedDict):
    next_action: str
    target_source_type: str
    reason: str
    query_hint: str | None


class TrendCollectionState(TypedDict, total=False):
    force_refresh: bool
    cached: bool
    finished: bool
    target_counts: dict[str, int]
    success_counts: dict[str, int]
    attempt_counts: dict[str, int]
    seen_urls: list[str]
    candidate_urls: list[dict[str, Any]]
    failed_urls: list[dict[str, str]]
    saved_sources: list[dict[str, str | None]]
    errors: list[str]
    last_route_decision: TrendRouteDecision | None
    searched_url_count: int
    total_urls: int
    collected_count: int
    failed_count: int


def collect_trend_slang_data(force_refresh: bool = False) -> dict:
    repository = TrendSlangRepository()
    repository.delete_sources_older_than(days=RETENTION_DAYS)
    recent_sources = repository.get_recent_trend_slang_sources(hours=CACHE_TTL_HOURS)
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

    return run_trend_collection_graph(repository, recent_sources, force_refresh)


def prepare_trend_context_for_writer(force_refresh: bool = False) -> dict:
    repository = TrendSlangRepository()

    try:
        collect_trend_slang_data(force_refresh=force_refresh)
    except Exception as e:
        logger.exception("writer 실행 전 trend_slang 준비 실패: 오류=%s", e)

    return repository.get_recent_trend_context_for_writer(hours=CACHE_TTL_HOURS)


def _is_recent_cache_sufficient(sources: list[dict]) -> bool:
    if len(sources) < MIN_RECENT_SOURCES:
        return False

    slang_count = sum(1 for item in sources if item["source_type"] == "slang")
    trend_count = sum(1 for item in sources if item["source_type"] == "trend")
    return slang_count >= 5 and trend_count >= 5


def has_meaningful_trend_data(extracted: dict) -> bool:
    return bool(extracted.get("keywords") or extracted.get("slang_expressions"))


def run_trend_collection_graph(
    repository: TrendSlangRepository,
    recent_sources: list[dict],
    force_refresh: bool,
) -> dict:
    initial_state = build_initial_state(recent_sources, force_refresh)

    if StateGraph is None:
        logger.warning("langgraph 패키지가 없어 기존 보충 검색 루프로 trend_slang 수집을 실행합니다.")
        final_state = run_fallback_collection_loop(repository, initial_state)
    else:
        graph = build_trend_collection_graph(repository)
        final_state = graph.invoke(initial_state)

    return {
        "cached": bool(final_state.get("cached", False)),
        "total_urls": final_state.get("total_urls", 0),
        "collected_count": final_state.get("collected_count", 0),
        "failed_count": final_state.get("failed_count", 0),
    }


def build_initial_state(recent_sources: list[dict], force_refresh: bool) -> TrendCollectionState:
    success_counts = count_sources_by_type(recent_sources)
    return {
        "force_refresh": force_refresh,
        "cached": False,
        "finished": False,
        "target_counts": dict(TARGET_COUNTS),
        "success_counts": success_counts,
        "attempt_counts": {source_type: 0 for source_type in SOURCE_TYPES},
        "seen_urls": [source["source_url"] for source in recent_sources if source.get("source_url")],
        "candidate_urls": [],
        "failed_urls": [],
        "saved_sources": [],
        "errors": [],
        "last_route_decision": None,
        "searched_url_count": 0,
        "total_urls": 0,
        "collected_count": 0,
        "failed_count": 0,
    }


def build_trend_collection_graph(repository: TrendSlangRepository):
    workflow = StateGraph(TrendCollectionState)
    workflow.add_node("route", llm_route_decision_node)
    workflow.add_node("search_more", search_more_urls_node)
    workflow.add_node("crawl_candidate", lambda state: crawl_candidate_node(state, repository))
    workflow.add_node("finish", finish_collection_node)

    workflow.set_entry_point("route")
    workflow.add_conditional_edges(
        "route",
        route_next_step,
        {
            "search_more": "search_more",
            "crawl_candidates": "crawl_candidate",
            "finish": "finish",
        },
    )
    workflow.add_edge("search_more", "route")
    workflow.add_edge("crawl_candidate", "route")
    workflow.add_edge("finish", END)
    return workflow.compile()


def llm_route_decision_node(state: TrendCollectionState) -> TrendCollectionState:
    fallback = build_deterministic_route_decision(state)

    try:
        parsed = parse_llm_json(call_llm(build_trend_route_decision_prompt(build_route_state_summary(state))))
        decision = normalize_route_decision(parsed, fallback)
    except Exception as e:
        logger.warning("trend_slang LLM 라우터 실패, 규칙 기반 분기로 대체: %s", e)
        decision = fallback

    logger.info(
        "trend_slang 라우터 판단: next=%s target=%s reason=%s",
        decision["next_action"],
        decision["target_source_type"],
        decision["reason"],
    )
    return {**state, "last_route_decision": decision}


def route_next_step(state: TrendCollectionState) -> Literal["search_more", "crawl_candidates", "finish"]:
    if targets_met(state):
        return "finish"

    decision = state.get("last_route_decision") or {}
    next_action = decision.get("next_action")
    if next_action == "finish":
        return "finish"

    if state.get("candidate_urls"):
        if next_action != "search_more" or not can_search_any_missing_type(state):
            return "crawl_candidates"

    if can_search_any_missing_type(state):
        if next_action in {"search_more", "crawl_candidates"}:
            return "search_more" if not state.get("candidate_urls") else "crawl_candidates"
        return "search_more"

    return "finish"


def search_more_urls_node(state: TrendCollectionState) -> TrendCollectionState:
    next_state = clone_state(state)
    route_decision = next_state.get("last_route_decision") or {}
    source_types = choose_search_source_types(next_state, route_decision)

    for source_type in source_types:
        if not can_search_type(next_state, source_type):
            continue

        query = build_search_query(source_type, route_decision.get("query_hint"))
        seen_urls = set(next_state["seen_urls"])
        remaining_candidate_budget = MAX_TOTAL_CANDIDATE_URLS - next_state["searched_url_count"]
        if remaining_candidate_budget <= 0:
            break

        limit = min(5, remaining_candidate_budget)
        next_state["attempt_counts"][source_type] += 1
        try:
            results = search_trend_slang_urls_by_type(
                source_type=source_type,
                query=query,
                seen_urls=seen_urls,
                limit=limit,
            )
        except Exception as e:
            message = f"{source_type} 검색 실패: {e}"
            logger.exception("trend_slang 보충 검색 실패: %s", message)
            next_state["errors"].append(message)
            continue

        next_state["candidate_urls"].extend(results)
        next_state["seen_urls"].extend(item["source_url"] for item in results)
        next_state["searched_url_count"] += len(results)
        next_state["total_urls"] += len(results)
        logger.info("trend_slang 보충 검색 완료: source_type=%s 후보수=%s", source_type, len(results))

    return next_state


def crawl_candidate_node(state: TrendCollectionState, repository: TrendSlangRepository) -> TrendCollectionState:
    next_state = clone_state(state)
    if not next_state["candidate_urls"]:
        return next_state

    item = next_state["candidate_urls"].pop(0)
    url = item["source_url"]
    try:
        scraped = scrape_url_content(url)
        cleaned_content = clean_html_content(scraped["raw_content"])
        if not cleaned_content:
            raise ValueError(f"정제된 본문이 비어 있습니다. raw_length={len(scraped['raw_content'])}")

        extracted = extract_trend_data(
            source_type=item["source_type"],
            title=item.get("source_title") or scraped.get("title"),
            cleaned_content=cleaned_content,
        )
        if not has_meaningful_trend_data(extracted):
            raise ValueError(
                "홍보 게시글 작성에 활용할 만한 추출 결과가 부족합니다. "
                f"keywords={len(extracted['keywords'])} "
                f"slang={len(extracted['slang_expressions'])}"
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
        next_state["success_counts"][item["source_type"]] += 1
        next_state["collected_count"] += 1
        next_state["saved_sources"].append(
            {
                "source_type": item["source_type"],
                "source_url": url,
                "source_title": item.get("source_title") or scraped.get("title"),
            }
        )
        logger.info("trend_slang URL 처리 성공: source_type=%s url=%s", item["source_type"], url)
    except Exception as e:
        next_state["failed_count"] += 1
        next_state["failed_urls"].append(
            {
                "source_type": item["source_type"],
                "source_url": url,
                "error": str(e),
            }
        )
        logger.exception(
            "trend_slang URL 처리 실패: url=%s source_type=%s 제목=%s 오류=%s",
            url,
            item["source_type"],
            item.get("source_title"),
            e,
        )

    return next_state


def finish_collection_node(state: TrendCollectionState) -> TrendCollectionState:
    logger.info(
        "trend_slang 수집 종료: success=%s attempts=%s collected=%s failed=%s",
        state.get("success_counts"),
        state.get("attempt_counts"),
        state.get("collected_count", 0),
        state.get("failed_count", 0),
    )
    return {**state, "finished": True}


def run_fallback_collection_loop(
    repository: TrendSlangRepository,
    state: TrendCollectionState,
) -> TrendCollectionState:
    next_state = clone_state(state)
    while not targets_met(next_state) and (next_state["candidate_urls"] or can_search_any_missing_type(next_state)):
        if not next_state["candidate_urls"]:
            next_state = search_more_urls_node({**next_state, "last_route_decision": build_deterministic_route_decision(next_state)})
        if next_state["candidate_urls"]:
            next_state = crawl_candidate_node(next_state, repository)
    return finish_collection_node(next_state)


def build_route_state_summary(state: TrendCollectionState) -> dict:
    return {
        "target_counts": state.get("target_counts", TARGET_COUNTS),
        "success_counts": state.get("success_counts", {}),
        "attempt_counts": state.get("attempt_counts", {}),
        "max_attempts_per_type": MAX_ATTEMPTS_PER_TYPE,
        "candidate_count": len(state.get("candidate_urls", [])),
        "failed_url_count": len(state.get("failed_urls", [])),
        "searched_url_count": state.get("searched_url_count", 0),
        "max_total_candidate_urls": MAX_TOTAL_CANDIDATE_URLS,
        "recent_errors": state.get("errors", [])[-3:],
        "recent_failed_urls": state.get("failed_urls", [])[-3:],
    }


def build_deterministic_route_decision(state: TrendCollectionState) -> TrendRouteDecision:
    if targets_met(state):
        return {
            "next_action": "finish",
            "target_source_type": "none",
            "reason": "slang과 trend 목표 개수를 모두 충족했습니다.",
            "query_hint": None,
        }
    if state.get("candidate_urls"):
        return {
            "next_action": "crawl_candidates",
            "target_source_type": "none",
            "reason": "처리 가능한 후보 URL이 남아 있습니다.",
            "query_hint": None,
        }

    missing_types = [source_type for source_type in SOURCE_TYPES if can_search_type(state, source_type)]
    if missing_types:
        target_source_type = "both" if len(missing_types) > 1 else missing_types[0]
        return {
            "next_action": "search_more",
            "target_source_type": target_source_type,
            "reason": "타입별 목표 개수에 도달하지 못해 보충 검색이 필요합니다.",
            "query_hint": None,
        }

    return {
        "next_action": "finish",
        "target_source_type": "none",
        "reason": "검색 시도 제한 또는 후보 URL 제한에 도달했습니다.",
        "query_hint": None,
    }


def normalize_route_decision(parsed: dict, fallback: TrendRouteDecision) -> TrendRouteDecision:
    next_action = str(parsed.get("next_action") or "").strip()
    target_source_type = str(parsed.get("target_source_type") or "").strip()
    if next_action not in {"search_more", "crawl_candidates", "finish"}:
        next_action = fallback["next_action"]
    if target_source_type not in {"slang", "trend", "both", "none"}:
        target_source_type = fallback["target_source_type"]
    query_hint = parsed.get("query_hint")
    return {
        "next_action": next_action,
        "target_source_type": target_source_type,
        "reason": str(parsed.get("reason") or fallback["reason"]).strip(),
        "query_hint": str(query_hint).strip() if query_hint else None,
    }


def choose_search_source_types(state: TrendCollectionState, decision: dict) -> list[str]:
    target_source_type = decision.get("target_source_type")
    if target_source_type == "both":
        return [source_type for source_type in SOURCE_TYPES if can_search_type(state, source_type)]
    if target_source_type in SOURCE_TYPES and can_search_type(state, target_source_type):
        return [target_source_type]
    return [source_type for source_type in SOURCE_TYPES if can_search_type(state, source_type)]


def build_search_query(source_type: str, query_hint: str | None) -> str:
    if query_hint:
        return query_hint
    return DEFAULT_QUERY_BY_SOURCE_TYPE[source_type]


def can_search_any_missing_type(state: TrendCollectionState) -> bool:
    return any(can_search_type(state, source_type) for source_type in SOURCE_TYPES)


def can_search_type(state: TrendCollectionState, source_type: str) -> bool:
    success_counts = state.get("success_counts", {})
    attempt_counts = state.get("attempt_counts", {})
    target_counts = state.get("target_counts", TARGET_COUNTS)
    if success_counts.get(source_type, 0) >= target_counts[source_type]:
        return False
    if attempt_counts.get(source_type, 0) >= MAX_ATTEMPTS_PER_TYPE:
        return False
    return state.get("searched_url_count", 0) < MAX_TOTAL_CANDIDATE_URLS


def targets_met(state: TrendCollectionState) -> bool:
    success_counts = state.get("success_counts", {})
    target_counts = state.get("target_counts", TARGET_COUNTS)
    return all(success_counts.get(source_type, 0) >= target_counts[source_type] for source_type in SOURCE_TYPES)


def count_sources_by_type(sources: list[dict]) -> dict[str, int]:
    return {
        source_type: sum(1 for source in sources if source.get("source_type") == source_type)
        for source_type in SOURCE_TYPES
    }


def clone_state(state: TrendCollectionState) -> TrendCollectionState:
    return {
        **state,
        "target_counts": dict(state.get("target_counts", TARGET_COUNTS)),
        "success_counts": dict(state.get("success_counts", {})),
        "attempt_counts": dict(state.get("attempt_counts", {})),
        "seen_urls": list(state.get("seen_urls", [])),
        "candidate_urls": list(state.get("candidate_urls", [])),
        "failed_urls": list(state.get("failed_urls", [])),
        "saved_sources": list(state.get("saved_sources", [])),
        "errors": list(state.get("errors", [])),
    }
