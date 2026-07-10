import re
from typing import Any


def compact_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def get_context_value(order_context: dict[str, Any] | None, aliases: list[str]):
    context = order_context or {}
    lowered_aliases = {alias.lower() for alias in aliases}
    for key, value in context.items():
        if str(key).lower() in lowered_aliases and value not in (None, ""):
            return value
    return None


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9가-힣]+", text.lower())
    stopwords = {"고객", "문의", "상품", "가능", "합니다", "있는", "없는", "the", "and", "for"}
    return [token for token in tokens if len(token) >= 2 and token not in stopwords]


def text_has_any(text: str, keywords: list[str]) -> bool:
    normalized = compact_text(text).lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def infer_bool(
    order_context: dict[str, Any] | None,
    aliases: list[str],
    customer_message: str,
    true_keywords: list[str],
    false_keywords: list[str],
) -> bool | None:
    value = get_context_value(order_context, aliases)
    if isinstance(value, bool):
        return value
    if value is not None:
        text = compact_text(value).lower()
        if text in {"false", "no", "n", "0", "미사용", "사용안함", "사용 안 함", "미제거", "제거안함", "제거 안 함"}:
            return False
        if text in {"true", "yes", "y", "1", "사용", "사용함", "제거", "제거함", "개봉", "개봉함"}:
            return True

    if text_has_any(customer_message, false_keywords):
        return False
    if text_has_any(customer_message, true_keywords):
        return True
    return None
