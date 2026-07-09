from app.core.llm_service import call_llm, parse_llm_json
from app.prompts.trend_slang_prompts import build_trend_extraction_prompt


TREND_ARRAY_KEYS = [
    "keywords",
    "slang_expressions",
    "hook_patterns",
    "writing_patterns",
    "cta_patterns",
    "tone_features",
    "avoid_expressions",
]


def extract_trend_data(source_type: str, title: str | None, cleaned_content: str) -> dict:
    result = call_llm(build_trend_extraction_prompt(source_type, title, cleaned_content))
    parsed = parse_llm_json(result)

    normalized = {
        key: filter_items(key, normalize_str_list(parsed.get(key)))
        for key in TREND_ARRAY_KEYS
    }
    normalized["summary"] = normalize_summary(str(parsed.get("summary") or "").strip())
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

    return filtered[:8]


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
    if len(item) > 60:
        return True
    if key in {"hook_patterns", "cta_patterns", "slang_expressions"} and len(item) > 35:
        return True
    if key == "slang_expressions" and " " in item and len(item.split()) > 6:
        return True
    return False


def normalize_summary(summary: str) -> str:
    if not summary:
        return ""
    cleaned = " ".join(summary.split())
    if len(cleaned) > 220:
        cleaned = cleaned[:217].rstrip() + "..."
    return cleaned
