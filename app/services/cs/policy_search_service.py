import hashlib
import logging
import os
import re
from typing import Any

from app.core.llm_service import call_passage_embedding, call_query_embedding
from app.services.cs.context_utils import compact_text


logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_NAME = "shopbuddy_policies"
DEFAULT_DB_PATH = "chroma_db"


class PolicySearchError(RuntimeError):
    pass


def ingest_policy_documents(documents: list[dict], reset_collection: bool = False) -> dict:
    chunks = build_policy_chunks(documents)
    if not chunks:
        raise ValueError("저장할 정책 문서 내용이 없습니다.")

    collection = get_policy_collection(reset_collection=reset_collection)
    embeddings = call_passage_embedding([chunk["text"] for chunk in chunks])

    collection.upsert(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
        embeddings=embeddings,
    )

    logger.info("정책 문서 ChromaDB 저장 완료: document_count=%s chunk_count=%s", len(documents), len(chunks))
    return {
        "message": "정책 문서 저장 성공",
        "collection_name": get_collection_name(),
        "stored_document_count": len(documents),
        "stored_chunk_count": len(chunks),
    }


def search_policy_documents(
    category: str,
    customer_message: str,
    order_context: dict[str, Any] | None = None,
    top_k: int = 3,
) -> list[dict]:
    try:
        collection = get_policy_collection(reset_collection=False)
        if collection.count() == 0:
            logger.warning("ChromaDB 정책 컬렉션이 비어 있습니다.")
            return []

        query_text = build_policy_query(category, customer_message, order_context or {})
        query_embedding = call_query_embedding([query_text])[0]
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=max(1, min(top_k, 10)),
            include=["documents", "metadatas", "distances"],
        )
        return normalize_chroma_results(results)
    except Exception as e:
        logger.exception("ChromaDB 정책 검색 실패: %s", e)
        raise PolicySearchError("정책 검색 중 ChromaDB 또는 임베딩 처리 오류가 발생했습니다.") from e


def build_policy_query(category: str, customer_message: str, order_context: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"문의 유형: {category}",
            f"고객 문의: {customer_message}",
            f"주문/상품 정보: {order_context}",
        ]
    )


def get_policy_collection(reset_collection: bool = False):
    chromadb = import_chromadb()
    client = chromadb.PersistentClient(path=get_chroma_db_path())
    collection_name = get_collection_name()

    if reset_collection:
        try:
            client.delete_collection(collection_name)
        except Exception:
            logger.info("삭제할 기존 ChromaDB 컬렉션이 없습니다: collection=%s", collection_name)

    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def import_chromadb():
    try:
        import chromadb
    except ImportError as e:
        raise RuntimeError("chromadb 패키지가 설치되어 있지 않습니다. requirements.txt 설치가 필요합니다.") from e
    return chromadb


def get_chroma_db_path() -> str:
    return os.getenv("CHROMA_DB_PATH", os.path.join(os.getcwd(), DEFAULT_DB_PATH))


def get_collection_name() -> str:
    return os.getenv("CHROMA_POLICY_COLLECTION", DEFAULT_COLLECTION_NAME)


def build_policy_chunks(documents: list[dict]) -> list[dict]:
    chunks: list[dict] = []
    for document_index, document in enumerate(documents):
        title = compact_text(document.get("title") or f"policy_{document_index + 1}")
        category = compact_text(document.get("category"))
        source = compact_text(document.get("source"))
        content = str(document.get("content") or "")

        for chunk_index, text in enumerate(split_policy_content(content)):
            normalized_text = compact_text(text)
            if not normalized_text:
                continue

            chunk_id = build_chunk_id(title, category, source, chunk_index, normalized_text)
            chunks.append(
                {
                    "id": chunk_id,
                    "text": normalized_text,
                    "metadata": {
                        "title": title,
                        "category": category,
                        "source": source,
                        "chunk_index": chunk_index,
                    },
                }
            )
    return chunks


def split_policy_content(content: str) -> list[str]:
    paragraphs = [compact_text(block) for block in re.split(r"\n{2,}", content) if compact_text(block)]
    chunks: list[str] = []

    for paragraph in paragraphs:
        if len(paragraph) <= 900:
            chunks.append(paragraph)
            continue
        chunks.extend(paragraph[index : index + 800] for index in range(0, len(paragraph), 800))

    return chunks


def build_chunk_id(title: str, category: str, source: str, chunk_index: int, text: str) -> str:
    digest = hashlib.sha1(f"{title}|{category}|{source}|{chunk_index}|{text}".encode("utf-8")).hexdigest()
    return f"policy_{digest}"


def normalize_chroma_results(results: dict) -> list[dict]:
    documents = first_result_list(results.get("documents"))
    metadatas = first_result_list(results.get("metadatas"))
    distances = first_result_list(results.get("distances"))

    matches: list[dict] = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        metadata = metadata or {}
        matches.append(
            {
                "title": metadata.get("title") or "정책 문서",
                "excerpt": trim_excerpt(str(document or "")),
                "score": distance_to_score(distance),
                "category": metadata.get("category") or None,
                "source": metadata.get("source") or None,
            }
        )
    return matches


def first_result_list(value) -> list:
    if not value:
        return []
    first = value[0]
    return first if isinstance(first, list) else value


def distance_to_score(distance) -> float:
    try:
        numeric_distance = float(distance)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, 1.0 - numeric_distance), 4)


def trim_excerpt(text: str, max_length: int = 350) -> str:
    text = compact_text(text)
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."
