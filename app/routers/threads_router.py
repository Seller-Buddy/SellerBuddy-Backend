from fastapi import APIRouter, HTTPException

from app.schemas import GeneratePostsRequest
from app.services.parser_service import normalize_products
from app.services.insight_service import create_product_insight
from app.services.writer_service import create_thread_post
from app.services.review_service import review_post
router = APIRouter()


@router.post("/generate")
def generate_threads_posts(request: GeneratePostsRequest):
    try:
        normalized_products = normalize_products(request.products)

        results = []

        for product in normalized_products:
            insight = create_product_insight(product)
            post = create_thread_post(product, insight)
            reviewed_post = review_post(post)

            results.append({
                "product_id": product["product_name"],
                "post": reviewed_post
            })

        return {
            "message": "게시글 생성 성공",
            "count": len(results),
            "results": results
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
