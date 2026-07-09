import html
import logging
import re

logger = logging.getLogger(__name__)


TAG_BLOCK_PATTERNS = [
    r"<script\b[^>]*>.*?</script>",
    r"<style\b[^>]*>.*?</style>",
    r"<noscript\b[^>]*>.*?</noscript>",
    r"<svg\b[^>]*>.*?</svg>",
    r"<iframe\b[^>]*>.*?</iframe>",
    r"<footer\b[^>]*>.*?</footer>",
    r"<nav\b[^>]*>.*?</nav>",
    r"<header\b[^>]*>.*?</header>",
    r"<aside\b[^>]*>.*?</aside>",
    r"<form\b[^>]*>.*?</form>",
    r"<button\b[^>]*>.*?</button>",
]

ARTICLE_CONTAINER_PATTERNS = [
    r"<article\b[^>]*>(.*?)</article>",
    r"<main\b[^>]*>(.*?)</main>",
    r"<div\b[^>]*(?:id|class)=[\"'][^\"']*(?:article|content|entry|post|view|story|se-main-container|tt_article_useless_p_margin)[^\"']*[\"'][^>]*>(.*?)</div>",
    r"<section\b[^>]*(?:id|class)=[\"'][^\"']*(?:article|content|entry|post|view|story)[^\"']*[\"'][^>]*>(.*?)</section>",
]

NOISE_PATTERNS = [
    r"\b\d+\s*comments?\b",
    r"\bshare\b",
    r"\blike\b",
    r"\bfollow\b",
    r"\bsubscribe\b",
]


def clean_html_content(raw_html: str) -> str:
    text = raw_html or ""
    raw_length = len(text)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)

    for pattern in TAG_BLOCK_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE | re.DOTALL)

    candidate_html = extract_article_candidate(text)
    cleaned_text = build_cleaned_text(candidate_html)
    if is_poor_cleaned_text(cleaned_text):
        cleaned_text = build_cleaned_text(text)

    logger.info(
        "trend_slang 본문 정제 완료: 원본길이=%s 정제길이=%s",
        raw_length,
        len(cleaned_text),
    )
    return cleaned_text


def extract_article_candidate(raw_html: str) -> str:
    known_segment = extract_known_article_segment(raw_html)
    if known_segment:
        return known_segment

    candidates: list[str] = []

    for pattern in ARTICLE_CONTAINER_PATTERNS:
        matches = re.findall(pattern, raw_html, flags=re.IGNORECASE | re.DOTALL)
        for match in matches:
            if isinstance(match, tuple):
                candidate = " ".join(part for part in match if part)
            else:
                candidate = match
            if candidate:
                candidates.append(candidate)

    if not candidates:
        return raw_html

    best_candidate = max(candidates, key=score_candidate_html)
    return best_candidate if score_candidate_html(best_candidate) >= 200 else raw_html


def extract_known_article_segment(raw_html: str) -> str | None:
    lower_html = raw_html.lower()

    if "se-main-container" in lower_html:
        start = lower_html.find("se-main-container")
        for end_marker in ("post_footer", "wrap_postcomment", "lyr_cont"):
            end = lower_html.find(end_marker, start)
            if end > start:
                return raw_html[start:end]

    if "tt_article_useless_p_margin" in lower_html:
        start = lower_html.find("tt_article_useless_p_margin")
        for end_marker in ("related-articles", "tt_article_bottom", "another_category"):
            end = lower_html.find(end_marker, start)
            if end > start:
                return raw_html[start:end]

    return None


def score_candidate_html(candidate_html: str) -> int:
    plain_text = re.sub(r"<[^>]+>", " ", candidate_html)
    plain_text = html.unescape(plain_text)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()
    if not plain_text:
        return 0

    score = len(plain_text)
    score += plain_text.count(".") * 10
    score += plain_text.count("다") * 2
    score += plain_text.count("\n") * 4
    penalty_keywords = [
        "로그인",
        "회원가입",
        "개인정보처리방침",
        "이용약관",
        "댓글",
        "공유",
        "구독",
        "고객센터",
        "상담하기",
    ]
    for keyword in penalty_keywords:
        if keyword in plain_text:
            score -= 60
    return score


def build_cleaned_text(candidate_html: str) -> str:
    text = re.sub(r"\s+(?:data|aria|t)-[\w-]+=\"[^\"]*\"", " ", candidate_html, flags=re.IGNORECASE)
    text = re.sub(r"\s+(?:data|aria|t)-[\w-]+='[^']*'", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<(br|p|div|li|section|article|h[1-6]|ul|ol|blockquote)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\b(?:data|aria|t)-[\w-]+=\"[^\"]*\"", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:data|aria|t)-[\w-]+='[^']*'", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = [normalize_line(line) for line in text.splitlines()]
    filtered: list[str] = []
    seen: set[str] = set()

    for line in lines:
        if not line or should_drop_line(line):
            continue
        if line in seen:
            continue
        seen.add(line)
        filtered.append(line)

    return "\n".join(filtered[:120])


def is_poor_cleaned_text(text: str) -> bool:
    if len(text) < 200:
        return True
    if len(text.splitlines()) < 3:
        return True
    return False


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def should_drop_line(line: str) -> bool:
    lower = line.lower()
    if len(line) < 25:
        return True
    if len(re.findall(r"[=><]{1,2}", line)) >= 2:
        return True
    if "<" in line or ">" in line:
        return True
    if re.search(r"\b(?:data|aria|t)-[\w-]+=", lower):
        return True
    if line.count('"') >= 4 or line.count("'") >= 4:
        return True
    if "copyright" in lower or "all rights reserved" in lower:
        return True
    if line.startswith("http") or "www." in lower:
        return True
    if re.fullmatch(r"[\w.-]+\.[A-Za-z]{2,}(?:/[^\s]*)?", line):
        return True
    if line.startswith("#") and line.count("#") >= 2:
        return True
    if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", line):
        return True
    if any(re.search(pattern, lower) for pattern in NOISE_PATTERNS):
        return True
    noise_keywords = [
        "로그인",
        "회원가입",
        "이용약관",
        "개인정보처리방침",
        "댓글",
        "공유",
        "구독",
        "광고",
        "메뉴",
        "카테고리",
        "이전 글",
        "다음 글",
        "전체보기",
        "목차",
        "관련 글",
        "추천 글",
        "프로필",
        "채널",
        "알림",
        "쿠키",
        "문의하기",
        "공지사항",
        "브랜드 안내",
        "지금 시작해볼까요",
        "지금 바로 상담하기",
        "고객센터",
        "연락주세요",
        "아이디 변경",
        "이웃을 맺으면",
        "이웃새글",
        "라이프디자인교육연구소",
        "맞춤형 솔루션",
        "지속 가능한 성장",
        "tt_article_useless_p_margin",
        "판매됩니다",
        "책임을 지지 않습니다",
    ]
    if any(keyword in line for keyword in noise_keywords):
        return True
    return False
