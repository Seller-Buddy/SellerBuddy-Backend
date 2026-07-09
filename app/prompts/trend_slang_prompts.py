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
