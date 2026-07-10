import json


def build_trend_extraction_prompt(source_type: str, title: str | None, content: str) -> str:
    return f"""
너는 한국어 소셜 콘텐츠 트렌드 분석 에이전트야.

아래 본문에서 실제로 쓰이는 유행어와 트렌드 표현만 추려서 JSON 객체로 정리해.
반드시 JSON만 반환해. 설명 문장, 코드블록, 마크다운은 절대 쓰지 마.
원문에 없는 사실은 만들지 마.
중복 표현은 제거해.

추출 원칙:
- slang_expressions는 실제 사람들이 쓰는 유행어/신조어만 남겨.
- keywords는 이 글의 핵심 트렌드 주제만 짧게 정리해.
- hook_patterns, writing_patterns, cta_patterns, tone_features는 필요할 때만 남기고, 아니면 빈 배열로 둬.
- 광고 문구, 법적 고지, 플랫폼 안내, 메뉴 문구, 저작권 문구, 일반 요약문은 모두 버려.
- 제목, 본문 길이, 사이트 소개 같은 메타 정보는 사용하지 마.

본문:
{content}

반환 형식:
{{
  "keywords": [],
  "slang_expressions": [],
  "hook_patterns": [],
  "writing_patterns": [],
  "cta_patterns": [],
  "tone_features": []
}}
"""


def build_trend_route_decision_prompt(state_summary: dict) -> str:
    return f"""
너는 트렌드 수집 워크플로우의 라우터 에이전트야.

현재 수집 상태를 보고 다음 작업을 판단해.
반드시 JSON 객체만 반환해. 설명 문장, 마크다운, 코드블록은 절대 쓰지 마.

허용되는 next_action:
- search_more: 부족한 타입의 URL을 더 검색해야 함
- crawl_candidates: 이미 확보한 후보 URL을 크롤링해야 함
- finish: 목표를 충족했거나 제한에 도달해 종료해야 함

허용되는 target_source_type:
- slang
- trend
- both
- none

판단 원칙:
- `slang`과 `trend`는 각각 5개 유효 소스 확보가 목표야.
- 후보 URL이 있고 아직 크롤링할 수 있으면 crawl_candidates를 우선 고려해.
- 한 타입의 유효 소스가 5개 미만이고 검색 시도 제한이 남아 있으면 search_more를 선택해.
- 반복 제한에 도달했거나 더 진행해도 의미가 낮으면 finish를 선택해.
- query_hint에는 다음 검색에 도움이 될 짧은 한국어 검색어를 넣어. 없으면 null로 둬.

현재 상태:
{json.dumps(state_summary, ensure_ascii=False)}

반환 형식:
{{
  "next_action": "search_more",
  "target_source_type": "slang",
  "reason": "판단 이유",
  "query_hint": "다음 검색어 또는 null"
}}
"""
