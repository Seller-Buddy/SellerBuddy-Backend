import json

from app.services.llm_service import call_llm, parse_llm_json


def create_thread_post(product: dict, insight: dict) -> dict:
    prompt = f"""
너는 Threads 마케팅 게시글을 작성하는 에이전트야.

아래 상품 정보와 인사이트를 바탕으로 Threads 게시글 1개를 작성해.
반드시 JSON만 반환해. 설명 문장, 마크다운, 코드블록은 쓰지 마.

조건:
- 500자 이하
- 자연스러운 한국어
- 너무 광고처럼 보이지 않게 작성
- 상품 정보에 없는 기능은 지어내지 말 것
- 과장 표현 금지
- 사용자가 게시 승인 여부를 판단할 수 있도록 완성된 게시글 형태로 작성

상품 정보:
{json.dumps(product, ensure_ascii=False)}

인사이트:
{json.dumps(insight, ensure_ascii=False)}

반환 형식:
{{
  "content": "게시글 내용"
}}
"""

    result = call_llm(prompt)
    post = parse_llm_json(result)

    if not post.get("content"):
        raise ValueError("LLM 게시글 응답에 content가 없습니다.")

    return {"content": str(post["content"])}
