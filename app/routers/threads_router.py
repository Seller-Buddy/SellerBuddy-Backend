import logging

from fastapi import APIRouter, HTTPException

from app.agents.content_writer import generate_threads_posts as run_content_writer_agent
from app.schemas import GeneratePostsRequest, PublishThreadRequest, PublishThreadResponse
from app.services.threads.publish_service import publish_thread_post
router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate")
def generate_threads_posts(request: GeneratePostsRequest):
    logger.info("게시글 생성 요청 수신: 상품 수=%s", len(request.products))
    try:
        results = run_content_writer_agent(request.products)
        logger.info("게시글 생성 요청 완료: 결과 수=%s", len(results))
        return {
            "message": "게시글 생성 성공",
            "count": len(results),
            "results": results
        }

    except ValueError as e:
        logger.warning("게시글 생성 요청 실패: 입력/검수 오류=%s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("게시글 생성 요청 실패: 예상하지 못한 오류=%s", e)
        raise HTTPException(status_code=502, detail="게시글 생성 중 외부 처리 오류가 발생했습니다.")


@router.post("/publish", response_model=PublishThreadResponse)
def publish_threads_post(request: PublishThreadRequest):
    content = request.content.strip()
    logger.info("Threads 게시 요청 수신: 글자 수=%s", len(content))

    if not content:
        raise HTTPException(status_code=400, detail="content가 비어 있습니다.")

    if len(content) > 500:
        raise HTTPException(status_code=400, detail="content는 500자를 초과할 수 없습니다.")

    try:
        threads_post_id = publish_thread_post(content)
    except ValueError as e:
        logger.warning("Threads 게시 요청 실패: 입력 오류=%s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception("Threads 게시 요청 실패: 외부 API 오류=%s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Threads 게시 요청 실패: 예상하지 못한 오류=%s", e)
        raise HTTPException(status_code=502, detail="Threads 게시 중 외부 처리 오류가 발생했습니다.")

    logger.info("Threads 게시 요청 완료: threads_post_id=%s", threads_post_id)
    return {
        "message": "Threads 게시 성공",
        "threads_post_id": threads_post_id,
        "status": "success",
    }
