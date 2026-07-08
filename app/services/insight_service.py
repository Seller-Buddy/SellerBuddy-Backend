import json

from app.services.llm_service import call_llm, parse_llm_json


def create_product_insight(product: dict) -> dict:
    prompt = f"""
너는 상품 정보를 분석해서 Threads 게시글 작성을 위한 핵심 포인트를 추출하는 에이전트야.

아래 상품 정보를 보고 반드시 JSON만 반환해.
설명 문장, 마크다운, 코드블록은 절대 쓰지 마.

상품 정보:
{json.dumps(product, ensure_ascii=False)}

반환 형식:
{{
  "target_customer": "핵심 타겟 고객",
  "pain_point": "고객이 겪는 불편함",
  "main_benefits": ["핵심 장점1", "핵심 장점2", "핵심 장점3"],
  "content_angle": "Threads 게시글 방향",
  "selling_point": "가장 강조할 판매 포인트",
  "avoid_claims": ["피해야 할 과장 표현1", "피해야 할 과장 표현2"]
}}
"""

    result = call_llm(prompt)
    return parse_llm_json(result)
