import logging

from app.core.llm_service import call_llm, parse_llm_json
from app.prompts.cs_prompts import build_inquiry_classification_prompt
from app.services.cs.context_utils import text_has_any


logger = logging.getLogger(__name__)

CATEGORY_LABELS = {
    "refund": "환불",
    "exchange": "교환",
    "shipping": "배송",
    "cancellation": "취소",
    "product_question": "상품 문의",
    "defective_item": "불량/파손",
    "complaint": "불만/클레임",
    "other": "기타",
}


def classify_inquiry(customer_message: str, order_context: dict) -> dict:
    try:
        parsed = parse_llm_json(call_llm(build_inquiry_classification_prompt(customer_message, order_context)))
        category = normalize_category(parsed.get("category"))
        return {
            "category": category,
            "category_label": CATEGORY_LABELS[category],
            "inquiry_summary": str(parsed.get("inquiry_summary") or customer_message).strip()[:300],
            "urgency": normalize_urgency(parsed.get("urgency")),
        }
    except Exception as e:
        logger.warning("CS 문의 분류 LLM 실패, 규칙 기반으로 대체: %s", e)
        category = classify_by_keywords(customer_message)
        return {
            "category": category,
            "category_label": CATEGORY_LABELS[category],
            "inquiry_summary": customer_message.strip()[:300],
            "urgency": "medium" if category in {"complaint", "defective_item"} else "low",
        }


def normalize_category(value) -> str:
    category = str(value or "").strip().lower()
    return category if category in CATEGORY_LABELS else "other"


def normalize_urgency(value) -> str:
    urgency = str(value or "").strip().lower()
    return urgency if urgency in {"low", "medium", "high"} else "low"


def classify_by_keywords(customer_message: str) -> str:
    if text_has_any(customer_message, ["환불", "반품", "돈", "결제취소", "refund", "return"]):
        return "refund"
    if text_has_any(customer_message, ["교환", "사이즈", "색상 변경", "exchange"]):
        return "exchange"
    if text_has_any(customer_message, ["배송", "송장", "운송장", "도착", "출고", "배송지", "shipping", "delivery"]):
        return "shipping"
    if text_has_any(customer_message, ["취소", "주문 취소", "cancel"]):
        return "cancellation"
    if text_has_any(customer_message, ["불량", "파손", "하자", "오염", "고장", "defect", "broken", "damaged"]):
        return "defective_item"
    if text_has_any(customer_message, ["화나요", "불만", "신고", "컴플레인", "complaint"]):
        return "complaint"
    if text_has_any(customer_message, ["재질", "사이즈표", "색상", "무게", "성분", "문의", "question"]):
        return "product_question"
    return "other"
