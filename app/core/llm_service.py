import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("UPSTAGE_API_KEY"),
    base_url="https://api.upstage.ai/v1"
)


def call_llm(prompt: str) -> str:
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

    return response.choices[0].message.content


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
        raise ValueError("LLM 응답을 JSON으로 해석할 수 없습니다.") from e

    if not isinstance(parsed, dict):
        raise ValueError("LLM 응답 JSON은 객체여야 합니다.")

    return parsed
