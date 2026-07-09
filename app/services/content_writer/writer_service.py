import logging

from app.core.llm_service import call_llm, parse_llm_json
from app.prompts.content_writer_prompts import build_thread_post_prompt

logger = logging.getLogger(__name__)


def create_thread_post(product: dict, insight: dict, trend_context: dict | None = None) -> dict:
    logger.info(
        "Threads 게시글 생성 시작: product_id=%s 트렌드컨텍스트존재=%s",
        product.get("product_id"),
        bool(trend_context),
    )
    result = call_llm(build_thread_post_prompt(product, insight, trend_context))
    post = parse_llm_json(result)

    if not post.get("content"):
        raise ValueError("LLM 게시글 응답에 content가 없습니다.")

    content = str(post["content"])
    logger.info("Threads 게시글 생성 완료: product_id=%s 글자수=%s", product.get("product_id"), len(content))
    return {"content": content}
