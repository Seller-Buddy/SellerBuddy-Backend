import json
import re

from app.services.llm_service import call_llm


def extract_json_text(response: str) -> str:
    if not response:
        raise ValueError("상품 정규화 LLM 응답이 비어 있습니다.")

    content = response.strip()

    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    return content


def parse_price(value) -> int | None:
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, str):
        digits = re.sub(r"[^0-9]", "", value)
        if digits:
            return int(digits)

    return None


def normalize_features(value) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        parts = re.split(r"[,/\n]|(?:\s*·\s*)", value)
        cleaned = [part.strip() for part in parts if part.strip()]
        return cleaned if cleaned else [value.strip()]

    text = str(value).strip()
    return [text] if text else []


def normalize_product(raw: dict, index: int) -> dict:
    fallback_product_id = f"p{index + 1:03d}"

    prompt = f"""
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

    response = call_llm(prompt)
    json_text = extract_json_text(response)

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError("상품 정규화 LLM 응답을 JSON으로 해석할 수 없습니다.") from e

    if not isinstance(parsed, dict):
        raise ValueError("상품 정규화 LLM 응답은 JSON 객체여야 합니다.")

    normalized = {
        "product_id": str(parsed.get("product_id") or fallback_product_id),
        "product_name": parsed.get("product_name"),
        "price": parse_price(parsed.get("price")),
        "category": parsed.get("category"),
        "features": normalize_features(parsed.get("features")),
        "target_customer": parsed.get("target_customer"),
        "pain_point": parsed.get("pain_point"),
        "product_url": parsed.get("product_url"),
    }

    if normalized["product_name"] is None or not str(normalized["product_name"]).strip():
        raise ValueError(f"{normalized['product_id']}: 상품명을 추론할 수 없습니다.")

    normalized["product_name"] = str(normalized["product_name"]).strip()
    normalized["category"] = str(normalized["category"]).strip() if normalized["category"] else None
    normalized["target_customer"] = (
        str(normalized["target_customer"]).strip() if normalized["target_customer"] else None
    )
    normalized["pain_point"] = str(normalized["pain_point"]).strip() if normalized["pain_point"] else None
    normalized["product_url"] = str(normalized["product_url"]).strip() if normalized["product_url"] else None

    return normalized


def normalize_products(raw_products: list[dict]) -> list[dict]:
    return [
        normalize_product(raw_product, index)
        for index, raw_product in enumerate(raw_products)
    ]
