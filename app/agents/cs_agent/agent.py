import logging

from app.schemas import CsAnalyzeRequest
from app.services.cs import (
    apply_operator_approval_policy,
    check_missing_information,
    classify_inquiry,
    decide_cs_case,
    review_cs_response,
    search_policy_documents,
    write_customer_reply,
)


logger = logging.getLogger(__name__)


def analyze_cs_case(request: CsAnalyzeRequest) -> dict:
    customer_message = request.customer_message.strip()
    if not customer_message:
        raise ValueError("customer_message가 비어 있습니다.")

    order_context = request.order_context or {}

    logger.info("CS 분석 시작: message_length=%s", len(customer_message))

    classification = classify_inquiry(customer_message, order_context)
    missing_info = check_missing_information(classification["category"], customer_message, order_context)
    matched_policies = search_policy_documents(classification["category"], customer_message, order_context)
    decision = decide_cs_case(
        classification["category"],
        customer_message,
        order_context,
        missing_info,
        matched_policies,
    )
    draft_reply = write_customer_reply(
        classification["category_label"],
        customer_message,
        order_context,
        missing_info,
        matched_policies,
        decision,
    )
    safety_review = review_cs_response(draft_reply, decision, missing_info, matched_policies)
    safety_review = apply_operator_approval_policy(safety_review, classification["category"], missing_info)

    logger.info(
        "CS 분석 완료: category=%s decision=%s approval=%s",
        classification["category"],
        decision["decision"],
        safety_review["requires_operator_approval"],
    )

    return {
        "message": "CS 문의 분석 성공",
        "inquiry_summary": classification["inquiry_summary"],
        "category": classification["category"],
        "category_label": classification["category_label"],
        "missing_info": missing_info,
        "matched_policies": matched_policies,
        "decision": decision["decision"],
        "decision_label": decision["decision_label"],
        "decision_reason": decision["decision_reason"],
        "draft_reply": draft_reply,
        "safety_review": safety_review,
        "workflow": build_workflow(classification, missing_info, matched_policies, decision, safety_review),
    }


def build_workflow(
    classification: dict,
    missing_info: list[str],
    matched_policies: list[dict],
    decision: dict,
    safety_review: dict,
) -> list[dict]:
    return [
        {"agent": "inquiry_classifier", "label": "문의 접수/분류 Agent", "status": "completed", "result": classification["category_label"]},
        {"agent": "missing_info_checker", "label": "정보 확인 Agent", "status": "completed", "result": missing_info},
        {"agent": "policy_search", "label": "정책 검색 Agent", "status": "completed", "result": {"matched_count": len(matched_policies)}},
        {"agent": "decision", "label": "판단 Agent", "status": "completed", "result": decision["decision_label"]},
        {"agent": "response_writer", "label": "답변 작성 Agent", "status": "completed", "result": "draft_reply_created"},
        {"agent": "safety_review", "label": "안전 검수 Agent", "status": "completed", "result": safety_review["risk_level"]},
        {
            "agent": "operator_approval",
            "label": "운영자 승인 Agent",
            "status": "completed",
            "result": {
                "requires_operator_approval": safety_review["requires_operator_approval"],
                "approval_reason": safety_review.get("approval_reason"),
            },
        },
    ]
