RISKY_PHRASES = ["무조건", "100%", "확정", "보장", "반드시 가능", "절대", "법적으로"]


def review_cs_response(
    draft_reply: str,
    decision: dict,
    missing_info: list[str],
    matched_policies: list[dict],
) -> dict:
    return review_by_rules(draft_reply, decision, missing_info, matched_policies)


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
