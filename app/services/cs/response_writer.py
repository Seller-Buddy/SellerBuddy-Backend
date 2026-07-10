import re

RISKY_PHRASES = ["무조건", "100%", "확정", "보장", "반드시 가능", "절대", "법적으로"]


def write_customer_reply(
    category_label: str,
    customer_message: str,
    order_context: dict,
    missing_info: list[str],
    matched_policies: list[dict],
    decision: dict,
) -> str:
    return build_fallback_reply(category_label, missing_info, matched_policies, decision)


def build_fallback_reply(
    category_label: str,
    missing_info: list[str],
    matched_policies: list[dict],
    decision: dict,
) -> str:
    policy_summary = build_safe_policy_summary(matched_policies)
    policy_sentence = f"관련 정책 기준은 다음과 같습니다: {policy_summary} " if policy_summary else ""
    decision_reason = str(decision.get("decision_reason") or "").strip()
    reason_sentence = f"판단 근거는 {decision_reason} " if decision_reason else ""

    if missing_info:
        return (
            f"고객님, 문의 감사합니다. {category_label} 처리 가능 여부를 정확히 확인하기 위해 "
            f"{', '.join(missing_info)} 정보를 추가로 확인 부탁드립니다. "
            f"{policy_sentence}필요한 정보를 확인한 뒤 가능한 처리 방향을 안내드리겠습니다."
        ).strip()

    if decision["decision"] == "likely_possible":
        return (
            f"고객님, 문의 감사합니다. 전달주신 내용과 정책 기준을 함께 보면 {category_label} 처리 가능성이 높습니다. "
            f"{policy_sentence}{reason_sentence}정확한 접수를 위해 주문 정보와 상품 상태를 확인한 뒤 안내드리겠습니다."
        ).strip()

    if decision["decision"] == "unlikely":
        return (
            f"고객님, 문의 감사합니다. 확인 가능한 정책 기준상 현재 내용만으로는 {category_label} 처리가 어려울 수 있습니다. "
            f"{policy_sentence}{reason_sentence}다만 예외 여부는 운영자가 한 번 더 확인 후 안내드리겠습니다."
        ).strip()

    if not matched_policies:
        return (
            f"고객님, 문의 감사합니다. 현재 등록된 정책에서 {category_label} 문의에 직접 적용할 근거를 찾지 못했습니다. "
            "정확한 안내를 위해 운영자가 관련 기준을 추가로 확인한 뒤 처리 방향을 안내드리겠습니다."
        )

    return (
        f"고객님, 문의 감사합니다. {category_label} 처리 가능 여부는 추가 확인이 필요합니다. "
        f"{policy_sentence}{reason_sentence}주문 정보와 상품 상태를 확인한 뒤 가능한 처리 방향을 안내드리겠습니다."
    ).strip()


def build_safe_policy_summary(matched_policies: list[dict], max_sentences: int = 2) -> str:
    if not matched_policies:
        return ""

    excerpt = str(matched_policies[0].get("excerpt") or "").strip()
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", excerpt) if sentence.strip()]
    safe_sentences = [
        sentence
        for sentence in sentences
        if not any(phrase.lower() in sentence.lower() for phrase in RISKY_PHRASES)
    ]
    selected = safe_sentences[:max_sentences]
    return " ".join(selected)
