import logging

from app.core.llm_service import call_llm, parse_llm_json
from app.prompts.content_writer_prompts import build_product_insight_prompt

logger = logging.getLogger(__name__)


def create_product_insight(product: dict) -> dict:
    logger.info("상품 인사이트 추출 시작: product_id=%s", product.get("product_id"))
    result = call_llm(build_product_insight_prompt(product))
    insight = parse_llm_json(result)
    logger.info(
        "상품 인사이트 추출 완료: product_id=%s 장점수=%s",
        product.get("product_id"),
        len(insight.get("main_benefits", [])) if isinstance(insight.get("main_benefits"), list) else 0,
    )
    return insight
