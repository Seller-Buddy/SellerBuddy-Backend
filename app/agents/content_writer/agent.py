import logging

from app.agents.trend_slang import prepare_trend_context_for_writer
from app.services.content_writer.insight_service import create_product_insight
from app.services.content_writer.parser_service import normalize_products
from app.services.content_writer.review_service import review_post
from app.services.content_writer.writer_service import create_thread_post

logger = logging.getLogger(__name__)


def generate_threads_posts(raw_products: list[dict]) -> list[dict]:
    logger.info("content_writer 시작: 원본 상품 수=%s", len(raw_products))
    trend_context = prepare_trend_context_for_writer()
    logger.info(
        "트렌드 컨텍스트 준비 완료: 키워드=%s 유행어=%s 훅=%s 작성패턴=%s CTA=%s 톤=%s",
        len(trend_context.get("keywords", [])),
        len(trend_context.get("slang_expressions", [])),
        len(trend_context.get("hook_patterns", [])),
        len(trend_context.get("writing_patterns", [])),
        len(trend_context.get("cta_patterns", [])),
        len(trend_context.get("tone_features", [])),
    )
    normalized_products = normalize_products(raw_products)
    logger.info("상품 정규화 완료: 상품 수=%s", len(normalized_products))
    results = []

    for product in normalized_products:
        logger.info(
            "상품별 게시글 생성 시작: product_id=%s 상품명=%s",
            product.get("product_id"),
            product.get("product_name"),
        )
        insight = create_product_insight(product)
        post = create_thread_post(product, insight, trend_context)
        reviewed_post = review_post(post)
        results.append({
            "product_id": product["product_id"],
            "post": reviewed_post,
        })

    logger.info("content_writer 완료: 결과 수=%s", len(results))
    return results
