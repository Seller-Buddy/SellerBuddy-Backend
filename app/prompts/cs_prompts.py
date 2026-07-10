import json


def _compact(value, max_length: int = 5000) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def build_inquiry_classification_prompt(customer_message: str, order_context: dict) -> str:
    return f"""
너는 쇼핑몰 CS 문의를 접수하고 분류하는 에이전트야.

아래 고객 문의와 주문 정보를 보고 반드시 JSON 객체만 반환해.
설명 문장, 마크다운, 코드블록은 쓰지 마.

category는 아래 중 하나만 사용해:
- refund
- exchange
- shipping
- cancellation
- product_question
- defective_item
- complaint
- other

고객 문의:
{_compact(customer_message, 2500)}

주문/상품 정보:
{_compact(order_context, 2500)}

반환 형식:
{{
  "category": "exchange",
  "category_label": "교환",
  "inquiry_summary": "고객 문의 핵심 요약",
  "urgency": "low 또는 medium 또는 high"
}}
"""
