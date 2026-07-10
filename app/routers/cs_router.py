import logging

from fastapi import APIRouter, HTTPException

from app.agents.cs_agent import analyze_cs_case
from app.schemas import (
    CsAnalyzeRequest,
    CsAnalyzeResponse,
    CsPolicyIngestRequest,
    CsPolicyIngestResponse,
    CsPolicySearchRequest,
    CsPolicySearchResponse,
)
from app.services.cs import ingest_policy_documents, search_policy_documents


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=CsAnalyzeResponse)
def analyze_customer_support_case(request: CsAnalyzeRequest):
    logger.info("CS 분석 요청 수신: message_length=%s", len(request.customer_message or ""))
    try:
        return analyze_cs_case(request)
    except ValueError as e:
        logger.warning("CS 분석 요청 실패: 입력 오류=%s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("CS 분석 요청 실패: 예상하지 못한 오류=%s", e)
        raise HTTPException(status_code=502, detail="CS 문의 분석 중 외부 처리 오류가 발생했습니다.")


@router.post("/policies/ingest", response_model=CsPolicyIngestResponse)
def ingest_customer_support_policies(request: CsPolicyIngestRequest):
    logger.info("CS 정책 저장 요청 수신: document_count=%s reset=%s", len(request.documents), request.reset_collection)
    try:
        documents = [document.model_dump() for document in request.documents]
        return ingest_policy_documents(documents, reset_collection=request.reset_collection)
    except ValueError as e:
        logger.warning("CS 정책 저장 요청 실패: 입력 오류=%s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("CS 정책 저장 요청 실패: 저장/임베딩 오류=%s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/policies/search", response_model=CsPolicySearchResponse)
def search_customer_support_policies(request: CsPolicySearchRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query가 비어 있습니다.")

    try:
        matches = search_policy_documents(
            category=request.category or "other",
            customer_message=query,
            order_context=request.order_context,
            top_k=request.top_k,
        )
    except Exception as e:
        logger.exception("CS 정책 검색 요청 실패: 검색/임베딩 오류=%s", e)
        raise HTTPException(status_code=502, detail="정책 검색 중 외부 처리 오류가 발생했습니다.")

    return {
        "message": "정책 검색 성공",
        "matches": matches,
    }
