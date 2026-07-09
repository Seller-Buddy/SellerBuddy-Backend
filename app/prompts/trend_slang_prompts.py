def build_trend_extraction_prompt(source_type: str, title: str | None, content: str) -> str:
    source_title = title or ""
    return f"""
너는 한국어 소셜 콘텐츠 트렌드 분석 에이전트야.

아래 본문에서 상품 홍보형 Threads 게시글 작성에 직접 재사용할 수 있는 유행어, 표현, 후킹 방식, CTA 패턴만 추려서 JSON 객체로 정리해.
반드시 JSON만 반환해. 설명 문장, 코드블록, 마크다운은 절대 쓰지 마.
원문에 없는 사실은 만들지 마.
중복 표현은 제거해.

추출 원칙:
- 실제 게시글 문장에 바로 쓸 수 있는 짧은 패턴만 남겨.
- 법적 고지, 플랫폼 안내, 메뉴 문구, 저작권 문구, 영상 설명, 일반 기사 요약은 버려.
- 브랜드 소개문, 서비스 소개문, 문의 유도 영업 문구는 버려.
- 너무 긴 문장, 문맥 의존 문장, 제목 그대로 복사한 문장은 가능하면 제외해.
- 품질이 애매하면 빈 배열로 둬.
- slang_expressions는 실제 사용자들이 쓰는 표현 위주로만 추출해.
- hook_patterns는 첫 문장/첫 훅으로 재사용 가능한 패턴만 추출해.
- writing_patterns는 문체/전개 패턴만 짧게 요약해.
- cta_patterns는 가벼운 참여 유도나 저장/공감 유도 표현만 남겨.
- tone_features는 말투 특성만 남겨.
- avoid_expressions에는 과장, 법적 리스크, 신뢰 저하를 부를 표현만 넣어.
- summary는 "이 자료를 홍보 게시글에 어떻게 참고하면 되는지" 한두 문장으로 요약해.

source_type: {source_type}
source_title: {source_title}

본문:
{content}

반환 형식:
{{
  "keywords": [],
  "slang_expressions": [],
  "hook_patterns": [],
  "writing_patterns": [],
  "cta_patterns": [],
  "tone_features": [],
  "avoid_expressions": [],
  "summary": ""
}}
"""
