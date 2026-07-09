import logging

from app.core.llm_service import call_llm, parse_llm_json
from app.prompts.trend_slang_prompts import build_trend_extraction_prompt

logger = logging.getLogger(__name__)


TREND_ARRAY_KEYS = [
    "keywords",
    "slang_expressions",
    "hook_patterns",
    "writing_patterns",
    "cta_patterns",
    "tone_features",
]

MAX_ITEM_LENGTH = 18
MAX_ITEMS_PER_KEY = 5


def extract_trend_data(source_type: str, title: str | None, cleaned_content: str) -> dict:
    logger.info(
        "trend_slang LLM 추출 시작: source_type=%s",
        source_type,
    )
    result = call_llm(build_trend_extraction_prompt(source_type, title, cleaned_content))
    parsed = parse_llm_json(result)

    normalized = {
        key: filter_items(key, normalize_str_list(parsed.get(key)))
        for key in TREND_ARRAY_KEYS
    }
    logger.info(
        "trend_slang 핵심 추출 완료: source_type=%s 키워드=%s 유행어=%s 훅=%s 작성패턴=%s CTA=%s 톤=%s",
        source_type,
        len(normalized["keywords"]),
        len(normalized["slang_expressions"]),
        len(normalized["hook_patterns"]),
        len(normalized["writing_patterns"]),
        len(normalized["cta_patterns"]),
        len(normalized["tone_features"]),
    )
    return normalized


def normalize_str_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def filter_items(key: str, items: list[str]) -> list[str]:
    filtered: list[str] = []
    seen: set[str] = set()

    for item in items:
        normalized = " ".join(item.split())
        if not normalized:
            continue
        if should_drop_item(key, normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        filtered.append(normalized)

    return filtered[:MAX_ITEMS_PER_KEY]


def should_drop_item(key: str, item: str) -> bool:
    lower = item.lower()
    banned_fragments = [
        "유튜브",
        "구독",
        "좋아요",
        "판매됩니다",
        "책임을 지지 않습니다",
        "개인정보",
        "이용약관",
        "로그인",
        "회원가입",
        "문의하세요",
        "문의하세요!",
        "브랜드 마케팅",
        "인플루언서 마케팅",
        "플랫폼",
    ]
    if any(fragment in item or fragment in lower for fragment in banned_fragments):
        return True
    if len(item) > MAX_ITEM_LENGTH:
        return True
    if key in {"hook_patterns", "cta_patterns", "slang_expressions"} and len(item) > MAX_ITEM_LENGTH:
        return True
    if key == "slang_expressions" and " " in item:
        return True
    return False
