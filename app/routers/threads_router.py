from fastapi import APIRouter, HTTPException

from app.schemas import GeneratePostsRequest, PublishThreadRequest, PublishThreadResponse
from app.services.parser_service import normalize_products
from app.services.insight_service import create_product_insight
from app.services.writer_service import create_thread_post
from app.services.review_service import review_post
from app.services.threads_publish_service import publish_thread_post
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
                "product_id": product["product_id"],
                "post": reviewed_post
            })

        return {
            "message": "게시글 생성 성공",
            "count": len(results),
            "results": results
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/publish", response_model=PublishThreadResponse)
def publish_threads_post(request: PublishThreadRequest):
    content = request.content.strip()

    if not content:
        raise HTTPException(status_code=400, detail="content가 비어 있습니다.")

    if len(content) > 500:
        raise HTTPException(status_code=400, detail="content는 500자를 초과할 수 없습니다.")

    try:
        threads_post_id = publish_thread_post(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "message": "Threads 게시 성공",
        "threads_post_id": threads_post_id,
        "status": "success",
    }
