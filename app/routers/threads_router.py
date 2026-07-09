from fastapi import APIRouter, HTTPException

from app.agents.content_writer import generate_threads_posts as run_content_writer_agent
from app.schemas import GeneratePostsRequest, PublishThreadRequest, PublishThreadResponse
from app.services.threads.publish_service import publish_thread_post
router = APIRouter()


@router.post("/generate")
def generate_threads_posts(request: GeneratePostsRequest):
    try:
        results = run_content_writer_agent(request.products)
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
