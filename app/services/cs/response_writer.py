import logging

from app.core.llm_service import call_llm, parse_llm_json
from app.prompts.cs_prompts import build_reply_prompt


logger = logging.getLogger(__name__)


def write_customer_reply(
    category_label: str,
    customer_message: str,
    order_context: dict,
    missing_info: list[str],
    matched_policies: list[dict],
    decision: dict,
) -> str:
    try:
        parsed = parse_llm_json(
            call_llm(
                build_reply_prompt(
                    category_label,
                    customer_message,
                    order_context,
                    missing_info,
                    matched_policies,
                    decision,
                )
            )
        )
        draft_reply = str(parsed.get("draft_reply") or "").strip()
        if draft_reply:
            return draft_reply
    except Exception as e:
        logger.warning("CS 답변 작성 LLM 실패, 규칙 기반으로 대체: %s", e)

    return build_fallback_reply(category_label, missing_info, matched_policies, decision)


def build_fallback_reply(
    category_label: str,
    missing_info: list[str],
    matched_policies: list[dict],
    decision: dict,
) -> str:
    policy_sentence = ""
    if matched_policies:
        policy_sentence = f"관련 정책에는 '{matched_policies[0]['excerpt']}' 내용이 확인됩니다. "

    if missing_info:
        return (
            f"고객님, 문의 감사합니다. {category_label} 처리 가능 여부를 정확히 확인하기 위해 "
            f"{', '.join(missing_info)} 정보를 추가로 확인 부탁드립니다. "
            f"{policy_sentence}확인 후 가능한 처리 방향을 안내드리겠습니다."
        ).strip()

    if decision["decision"] == "likely_possible":
        return (
            f"고객님, 문의 감사합니다. 전달주신 내용과 정책 기준을 함께 보면 {category_label} 처리 가능성이 높습니다. "
            f"{policy_sentence}정확한 접수를 위해 주문 정보와 상품 상태를 최종 확인한 뒤 안내드리겠습니다."
        ).strip()

    if decision["decision"] == "unlikely":
        return (
            f"고객님, 문의 감사합니다. 확인 가능한 정책 기준상 현재 내용만으로는 {category_label} 처리가 어려울 수 있습니다. "
            f"{policy_sentence}다만 예외 여부는 운영자가 한 번 더 확인 후 안내드리겠습니다."
        ).strip()

    return (
        f"고객님, 문의 감사합니다. {category_label} 처리 가능 여부는 추가 확인이 필요합니다. "
        f"{policy_sentence}주문 정보와 상품 상태를 확인한 뒤 가능한 처리 방향을 안내드리겠습니다."
    ).strip()
