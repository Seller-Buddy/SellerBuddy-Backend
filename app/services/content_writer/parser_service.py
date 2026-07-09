import json
import logging
import re

from app.core.llm_service import call_llm
from app.prompts.content_writer_prompts import build_product_normalization_prompt

logger = logging.getLogger(__name__)


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
    logger.info("상품 정규화 시작: index=%s 기본product_id=%s 원본키=%s", index, fallback_product_id, list(raw.keys()))
    prompt = build_product_normalization_prompt(raw, fallback_product_id)
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

    logger.info(
        "상품 정규화 완료: product_id=%s 상품명=%s 특징수=%s 가격존재=%s",
        normalized["product_id"],
        normalized["product_name"],
        len(normalized["features"]),
        normalized["price"] is not None,
    )
    return normalized


def normalize_products(raw_products: list[dict]) -> list[dict]:
    return [
        normalize_product(raw_product, index)
        for index, raw_product in enumerate(raw_products)
    ]
