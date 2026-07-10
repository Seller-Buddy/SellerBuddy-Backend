import logging

from app.core.llm_service import call_llm, parse_llm_json
from app.prompts.cs_prompts import build_safety_review_prompt


logger = logging.getLogger(__name__)

RISKY_PHRASES = ["무조건", "100%", "확정", "보장", "반드시 가능", "절대", "법적으로"]


def review_cs_response(
    draft_reply: str,
    decision: dict,
    missing_info: list[str],
    matched_policies: list[dict],
) -> dict:
    review = review_by_rules(draft_reply, decision, missing_info, matched_policies)

    try:
        parsed = parse_llm_json(call_llm(build_safety_review_prompt(draft_reply, decision, missing_info, matched_policies)))
        issues = merge_unique(review["issues"], normalize_issue_list(parsed.get("issues")))
        risk_level = max_risk(review["risk_level"], normalize_risk_level(parsed.get("risk_level")))
        requires_approval = normalize_bool(parsed.get("requires_operator_approval")) or review["requires_operator_approval"]
        approval_reason = parsed.get("approval_reason") or review.get("approval_reason")
        if requires_approval and not approval_reason:
            approval_reason = "운영자 확인이 필요한 CS 응대입니다."
        return {
            "requires_operator_approval": requires_approval,
            "risk_level": risk_level,
            "issues": issues,
            "approval_reason": approval_reason,
        }
    except Exception as e:
        logger.warning("CS 안전 검수 LLM 실패, 규칙 기반으로 대체: %s", e)
        return review


def review_by_rules(
    draft_reply: str,
    decision: dict,
    missing_info: list[str],
    matched_policies: list[dict],
) -> dict:
    issues: list[str] = []

    for phrase in RISKY_PHRASES:
        if phrase in draft_reply:
            issues.append(f"확답 위험 표현 포함: {phrase}")

    if missing_info:
        issues.append("판단에 필요한 정보가 일부 누락되어 있습니다.")
    if not matched_policies:
        issues.append("정책 근거가 없습니다.")
    if decision["decision"] != "likely_possible":
        issues.append("처리 가능 여부에 운영자 확인이 필요합니다.")

    risk_level = "high" if not matched_policies else "medium" if issues else "low"
    requires_operator_approval = bool(issues)
    return {
        "requires_operator_approval": requires_operator_approval,
        "risk_level": risk_level,
        "issues": issues,
        "approval_reason": " / ".join(issues) if requires_operator_approval else None,
    }


def normalize_issue_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def normalize_risk_level(value) -> str:
    risk_level = str(value or "").strip().lower()
    return risk_level if risk_level in {"low", "medium", "high"} else "low"


def normalize_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1"}:
            return True
        if normalized in {"false", "no", "n", "0", "null", "none", ""}:
            return False
    return bool(value)


def max_risk(left: str, right: str) -> str:
    ranks = {"low": 0, "medium": 1, "high": 2}
    return left if ranks[left] >= ranks[right] else right


def merge_unique(left: list[str], right: list[str]) -> list[str]:
    merged: list[str] = []
    for item in [*left, *right]:
        if item not in merged:
            merged.append(item)
    return merged
