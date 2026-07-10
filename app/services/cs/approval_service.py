def apply_operator_approval_policy(safety_review: dict, category: str, missing_info: list[str]) -> dict:
    review = dict(safety_review)

    if category in {"complaint", "defective_item"}:
        review["requires_operator_approval"] = True
        review["risk_level"] = max_risk(review.get("risk_level", "low"), "medium")
        add_issue(review, "클레임/불량 문의는 운영자 확인 후 응대해야 합니다.")

    if missing_info:
        review["requires_operator_approval"] = True
        review["risk_level"] = max_risk(review.get("risk_level", "low"), "medium")

    if review["requires_operator_approval"] and not review.get("approval_reason"):
        review["approval_reason"] = "운영자 검토 후 답변 전송이 필요합니다."

    return review


def add_issue(review: dict, issue: str) -> None:
    issues = review.setdefault("issues", [])
    if issue not in issues:
        issues.append(issue)
    if not review.get("approval_reason"):
        review["approval_reason"] = issue


def max_risk(left: str, right: str) -> str:
    ranks = {"low": 0, "medium": 1, "high": 2}
    left = left if left in ranks else "low"
    right = right if right in ranks else "low"
    return left if ranks[left] >= ranks[right] else right
