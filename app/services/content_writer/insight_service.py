from app.core.llm_service import call_llm, parse_llm_json
from app.prompts.content_writer_prompts import build_product_insight_prompt


def create_product_insight(product: dict) -> dict:
    result = call_llm(build_product_insight_prompt(product))
    return parse_llm_json(result)
