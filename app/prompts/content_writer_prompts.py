import json


def build_product_normalization_prompt(raw: dict, fallback_product_id: str) -> str:
    return f"""
너는 제각각인 상품 JSON을 표준 상품 JSON으로 정규화하는 에이전트야.

반드시 JSON 객체만 반환해.
설명 문장, 마크다운, 코드블록, 주석은 절대 쓰지 마.

규칙:
- 입력 key 이름은 한국어, 영어, camelCase, snake_case, 축약어여도 의미를 추론해서 매핑해.
- product_id는 원본에 id, product_id, sku, code 같은 값이 있으면 사용하고, 없으면 "{fallback_product_id}"를 사용해.
- product_name은 반드시 채워야 한다. 상품명을 추론할 수 없으면 null로 둬.
- price는 숫자로 변환해. 예: "12,900원" -> 12900
- category, target_customer, pain_point, product_url은 없으면 null
- features는 반드시 문자열 배열로 반환해. 문자열 하나면 의미 단위로 분리해.
- 원본에 없는 사실은 지어내지 마.

반환 스키마:
{{
  "product_id": "문자열",
  "product_name": "상품명 또는 null",
  "price": 12900,
  "category": "카테고리 또는 null",
  "features": ["특징1", "특징2"],
  "target_customer": "타겟 고객 또는 null",
  "pain_point": "고객의 문제/불편함 또는 null",
  "product_url": "상품 URL 또는 null"
}}

입력 상품 JSON:
{json.dumps(raw, ensure_ascii=False)}
"""


def build_product_insight_prompt(product: dict) -> str:
    return f"""
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


def build_thread_post_prompt(product: dict, insight: dict, trend_context: dict | None = None) -> str:
    trend_context_section = ""

    if trend_context:
        trend_context_section = f"""

최근 트렌드/유행어 참고 정보:
{json.dumps(trend_context, ensure_ascii=False)}
"""

    return f"""
너는 Threads 마케팅 게시글을 작성하는 에이전트야.

아래 상품 정보와 인사이트를 바탕으로 Threads 게시글 1개를 작성해.
글을 보는 사람의 구미를 당길 수 있도록 위에 첨부한 트렌드/유행어 참고 정보를 적용해.
반드시 `slang_expressions`에서 유행어 또는 신조어 1개 이상을 자연스럽게 포함해.
반드시 JSON만 반환해. 설명 문장, 마크다운, 코드블록은 쓰지 마.

조건:
- 500자 이하
- 자연스러운 한국어
- 너무 광고처럼 보이지 않게 작성
- 상품 정보에 없는 기능은 지어내지 말 것
- 과장 표현 금지
- 사용자가 게시 승인 여부를 판단할 수 있도록 완성된 게시글 형태로 작성
- 최근 트렌드/유행어 참고 정보 중 최소 1개의 유행어 또는 신조어를 포함할 것
- 유행어는 문장 끝 장식이 아니라 문맥에 자연스럽게 녹일 것

상품 정보:
{json.dumps(product, ensure_ascii=False)}

인사이트:
{json.dumps(insight, ensure_ascii=False)}
{trend_context_section}

반환 형식:
{{
  "content": "게시글 내용"
}}
"""
