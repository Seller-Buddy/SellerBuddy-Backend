import re
from datetime import date, datetime

from app.services.cs.context_utils import get_context_value, infer_bool, text_has_any
from app.services.cs.missing_info_checker import FIELD_ALIASES

DECISION_LABELS = {
    "likely_possible": "가능성 높음",
    "needs_confirmation": "확인 필요",
    "unlikely": "가능성 낮음",
}

RECEIVED_DAYS_ALIASES = [
    "received_days_ago",
    "receivedDaysAgo",
    "days_since_delivery",
    "daysSinceDelivery",
    "수령후경과일",
    "수령 후 경과일",
    "배송완료후경과일",
    "배송 완료 후 경과일",
]


def decide_cs_case(
    category: str,
    customer_message: str,
    order_context: dict,
    missing_info: list[str],
    matched_policies: list[dict],
) -> dict:
    return decide_by_rules(category, customer_message, order_context, missing_info, matched_policies)


def decide_by_rules(
    category: str,
    customer_message: str,
    order_context: dict,
    missing_info: list[str],
    matched_policies: list[dict],
) -> dict:
    if not matched_policies:
        return build_decision("needs_confirmation", "요청에 포함된 정책 문서에서 직접 근거를 찾지 못했습니다.")

    if missing_info:
        return build_decision("needs_confirmation", f"판단에 필요한 정보가 부족합니다: {', '.join(missing_info)}")

    policy_text = " ".join(match["excerpt"] for match in matched_policies)

    if category in {"refund", "exchange"}:
        used = infer_bool(
            order_context,
            FIELD_ALIASES["used"],
            customer_message,
            true_keywords=["사용했", "착용했", "입었", "신었", "사용함", "used", "worn"],
            false_keywords=["미사용", "사용 안", "착용 안", "택 그대로", "새상품", "unused", "not used", "new item"],
        )
        tag_removed = infer_bool(
            order_context,
            FIELD_ALIASES["tag_removed"],
            customer_message,
            true_keywords=["택 제거", "택을 제거", "택 뗐", "라벨 제거", "tag removed", "removed the tag"],
            false_keywords=[
                "택 제거 안",
                "택 안 뗐",
                "택 있음",
                "라벨 있음",
                "택 그대로",
                "tag attached",
                "tag is attached",
                "tag still attached",
                "tag is still attached",
            ],
        )
        if used is True or tag_removed is True:
            return build_decision("unlikely", "사용 또는 택 제거 정황이 있어 교환/환불 가능성이 낮습니다.")
        if used is False and tag_removed is False:
            if has_seven_day_policy(policy_text):
                received_days = infer_received_days(customer_message, order_context)
                if received_days is None:
                    return build_decision("needs_confirmation", "수령 후 7일 이내 조건을 계산할 수 있는 수령일 확인이 필요합니다.")
                if received_days > 7:
                    return build_decision(
                        "unlikely",
                        f"수령 후 {received_days}일이 지나 정책의 7일 이내 조건을 초과했습니다.",
                    )
                return build_decision("likely_possible", "정책 근거상 7일 이내, 미사용, 택 유지 조건을 충족할 가능성이 높습니다.")
            if text_has_any(policy_text, ["미사용", "unused"]) and text_has_any(policy_text, ["택", "tag"]):
                return build_decision("likely_possible", "정책 근거상 미사용, 택 유지 조건을 충족할 가능성이 높습니다.")

    if category == "cancellation":
        order_status = get_context_value(order_context, FIELD_ALIASES["order_status"])
        status_text = f"{order_status or ''} {customer_message}"
        if text_has_any(status_text, ["출고 전", "배송 전", "배송 시작 전", "미출고"]):
            return build_decision("likely_possible", "출고 전 또는 배송 시작 전 상태로 취소 가능성이 높습니다.")
        if text_has_any(
            status_text,
            ["출고 후", "출고됐", "출고 완료", "배송 중", "배송중", "배송 시작", "발송 완료", "발송됐"],
        ):
            return build_decision("unlikely", "이미 출고되었거나 배송이 시작되어 주문 취소 가능성이 낮습니다.")
        return build_decision("needs_confirmation", "주문 취소 가능 여부를 판단하려면 출고 또는 배송 시작 여부 확인이 필요합니다.")

    if category == "shipping":
        return build_decision("needs_confirmation", "배송 문의는 실제 배송 상태와 운송장 확인이 필요합니다.")

    return build_decision("needs_confirmation", "정책 근거는 있으나 고객 상황과 예외 조건을 운영자가 확인해야 합니다.")


def build_decision(decision: str, reason: str) -> dict:
    return {
        "decision": decision,
        "decision_label": DECISION_LABELS[decision],
        "decision_reason": reason,
    }


def has_seven_day_policy(policy_text: str) -> bool:
    return text_has_any(policy_text, ["7일", "7 days", "seven days"])


def infer_received_days(customer_message: str, order_context: dict) -> int | None:
    explicit_days = parse_days_value(get_context_value(order_context, RECEIVED_DAYS_ALIASES))
    if explicit_days is not None:
        return explicit_days

    received_at = parse_date_value(get_context_value(order_context, FIELD_ALIASES["received_at"]))
    if received_at is not None:
        return max(0, (date.today() - received_at).days)

    return infer_received_days_from_text(customer_message)


def parse_days_value(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        days = int(value)
        return days if days >= 0 else None

    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"\d+", text)
    if not match:
        return None
    days = int(match.group())
    return days if days >= 0 else None


def parse_date_value(value) -> date | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    iso_text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_text).date()
    except ValueError:
        pass

    numeric_match = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", text)
    if not numeric_match:
        numeric_match = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", text)
    if not numeric_match:
        return None

    year, month, day = (int(part) for part in numeric_match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def infer_received_days_from_text(customer_message: str) -> int | None:
    text = " ".join((customer_message or "").split()).lower()
    if not text:
        return None

    if text_has_any(text, ["오늘 받", "오늘 수령", "오늘 도착", "received today", "delivered today"]):
        return 0
    if text_has_any(text, ["어제 받", "어제 수령", "어제 도착", "yesterday"]):
        return 1
    if text_has_any(text, ["그저께 받", "그저께 수령", "그저께 도착", "2 days ago"]):
        return 2

    patterns = [
        r"(?:받은\s*지|수령\s*후|배송\s*완료\s*후)\s*(\d+)\s*일",
        r"(\d+)\s*일\s*(?:전|전에)\s*(?:받|수령|도착)",
        r"(?:received|delivered)\s*(\d+)\s*days?\s*ago",
        r"(\d+)\s*days?\s*ago",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None
