from app.services.cs.context_utils import get_context_value, infer_bool, text_has_any


FIELD_ALIASES = {
    "order_id": ["order_id", "orderId", "주문번호", "주문 번호"],
    "received_at": ["received_at", "receivedAt", "수령일", "배송완료일", "받은날"],
    "used": ["used", "사용여부", "사용 여부"],
    "tag_removed": ["tag_removed", "tagRemoved", "택제거", "택 제거"],
    "product_name": ["product_name", "productName", "상품명", "제품명"],
    "order_status": ["order_status", "orderStatus", "주문상태", "주문 상태"],
    "delivery_status": ["delivery_status", "deliveryStatus", "배송상태", "배송 상태"],
    "tracking_number": ["tracking_number", "trackingNumber", "운송장", "송장번호", "송장 번호"],
    "issue_detail": ["issue_detail", "issueDetail", "하자내용", "불량내용", "파손내용", "상세내용"],
}


def check_missing_information(category: str, customer_message: str, order_context: dict) -> list[str]:
    missing: list[str] = []

    if category in {"refund", "exchange"}:
        add_if_missing(missing, "수령일", has_received_at(customer_message, order_context))
        add_if_missing(missing, "사용 여부", infer_used(customer_message, order_context) is not None)
        add_if_missing(missing, "택 제거 여부", infer_tag_removed(customer_message, order_context) is not None)
    elif category == "defective_item":
        add_if_missing(missing, "불량/파손 상세 내용", has_issue_detail(customer_message, order_context))
        add_if_missing(missing, "주문번호 또는 상품명", has_any_field(order_context, ["order_id", "product_name"]))
    elif category == "shipping":
        add_if_missing(missing, "주문번호", has_field(order_context, "order_id"))
        add_if_missing(missing, "배송 상태 또는 운송장 번호", has_any_field(order_context, ["delivery_status", "tracking_number"]))
    elif category == "cancellation":
        add_if_missing(missing, "주문번호", has_field(order_context, "order_id"))
        add_if_missing(missing, "출고/배송 시작 여부", has_order_status(customer_message, order_context))

    return missing


def add_if_missing(missing: list[str], label: str, present: bool) -> None:
    if not present and label not in missing:
        missing.append(label)


def has_field(order_context: dict, field: str) -> bool:
    return get_context_value(order_context, FIELD_ALIASES[field]) is not None


def has_any_field(order_context: dict, fields: list[str]) -> bool:
    return any(has_field(order_context, field) for field in fields)


def has_received_at(customer_message: str, order_context: dict) -> bool:
    return has_field(order_context, "received_at") or text_has_any(
        customer_message,
        ["오늘 받", "어제 받", "수령", "배송 완료", "받았", "도착했", "received", "delivered", "yesterday"],
    )


def infer_used(customer_message: str, order_context: dict) -> bool | None:
    return infer_bool(
        order_context,
        FIELD_ALIASES["used"],
        customer_message,
        true_keywords=["사용했", "착용했", "입었", "신었", "써봤", "사용함", "used", "worn"],
        false_keywords=["미사용", "사용 안", "착용 안", "입지 않았", "새상품", "unused", "not used", "new item"],
    )


def infer_tag_removed(customer_message: str, order_context: dict) -> bool | None:
    return infer_bool(
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


def has_issue_detail(customer_message: str, order_context: dict) -> bool:
    return has_field(order_context, "issue_detail") or text_has_any(
        customer_message,
        ["불량", "파손", "하자", "오염", "찢어", "깨져", "고장", "사진"],
    )


def has_order_status(customer_message: str, order_context: dict) -> bool:
    return has_field(order_context, "order_status") or text_has_any(
        customer_message,
        ["출고 전", "출고 후", "배송 전", "배송 시작", "배송중", "발송"],
    )
