from app.core.llm_service import call_llm, parse_llm_json
from app.prompts.content_writer_prompts import build_thread_post_prompt


def create_thread_post(product: dict, insight: dict, trend_context: dict | None = None) -> dict:
    result = call_llm(build_thread_post_prompt(product, insight, trend_context))
    post = parse_llm_json(result)

    if not post.get("content"):
        raise ValueError("LLM 게시글 응답에 content가 없습니다.")

    return {"content": str(post["content"])}
