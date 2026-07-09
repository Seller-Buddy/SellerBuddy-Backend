import logging

logger = logging.getLogger(__name__)


def review_post(post: dict) -> dict:
    content = str(post.get("content", ""))
    issues = []

    if not content:
        issues.append("게시글 내용이 비어 있음")

    if len(content) > 500:
        issues.append("Threads 500자 제한 초과")

    banned_phrases = ["무조건", "100%", "완치", "치료", "1위", "최고의"]

    for phrase in banned_phrases:
        if phrase in content:
            issues.append(f"위험/과장 표현 포함: {phrase}")

    if issues:
        logger.warning("게시글 검수 실패: 이슈=%s 글자수=%s", issues, len(content))
        raise ValueError(", ".join(issues))

    logger.info("게시글 검수 통과: 글자수=%s", len(content))
    return {"content": content}
