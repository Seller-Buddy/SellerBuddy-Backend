from app.agents.trend_slang import prepare_trend_context_for_writer
from app.services.content_writer.insight_service import create_product_insight
from app.services.content_writer.parser_service import normalize_products
from app.services.content_writer.review_service import review_post
from app.services.content_writer.writer_service import create_thread_post


def generate_threads_posts(raw_products: list[dict]) -> list[dict]:
    trend_context = prepare_trend_context_for_writer()
    normalized_products = normalize_products(raw_products)
    results = []

    for product in normalized_products:
        insight = create_product_insight(product)
        post = create_thread_post(product, insight, trend_context)
        reviewed_post = review_post(post)
        results.append({
            "product_id": product["product_id"],
            "post": reviewed_post,
        })

    return results
