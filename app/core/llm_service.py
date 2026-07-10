import json
import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=os.getenv("UPSTAGE_API_KEY"),
    base_url="https://api.upstage.ai/v1"
)


def call_llm(prompt: str) -> str:
    if not os.getenv("UPSTAGE_API_KEY"):
        raise ValueError("UPSTAGE_API_KEY가 설정되어 있지 않습니다.")

    logger.info("LLM 호출 시작: model=solar-pro2 프롬프트길이=%s", len(prompt))
    response = client.chat.completions.create(
        model="solar-pro2",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
    )

    content = response.choices[0].message.content
    logger.info("LLM 응답 수신: 응답길이=%s", len(content or ""))
    return content


def call_query_embedding(texts: list[str]) -> list[list[float]]:
    return call_embedding(texts, model_env_key="UPSTAGE_EMBEDDING_QUERY_MODEL")


def call_passage_embedding(texts: list[str]) -> list[list[float]]:
    return call_embedding(texts, model_env_key="UPSTAGE_EMBEDDING_PASSAGE_MODEL")


def call_embedding(texts: list[str], model_env_key: str) -> list[list[float]]:
    if not texts:
        return []

    if not os.getenv("UPSTAGE_API_KEY"):
        raise ValueError("UPSTAGE_API_KEY가 설정되어 있지 않습니다.")

    model = os.getenv(model_env_key)
    if not model:
        raise ValueError(f"{model_env_key}이 설정되어 있지 않습니다.")

    logger.info("Embedding 호출 시작: model=%s env=%s 입력수=%s", model, model_env_key, len(texts))
    response = client.embeddings.create(
        model=model,
        input=texts,
    )
    embeddings = [item.embedding for item in response.data]
    logger.info("Embedding 응답 수신: embedding_count=%s", len(embeddings))
    return embeddings


def parse_llm_json(raw_response: str) -> dict:
    if not raw_response:
        raise ValueError("LLM 응답이 비어 있습니다.")

    content = raw_response.strip()

    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        logger.exception("LLM JSON 파싱 실패: 응답길이=%s", len(content))
        raise ValueError("LLM 응답을 JSON으로 해석할 수 없습니다.") from e

    if not isinstance(parsed, dict):
        raise ValueError("LLM 응답 JSON은 객체여야 합니다.")

    return parsed
