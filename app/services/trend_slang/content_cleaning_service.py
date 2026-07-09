import html
import re


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

NOISE_PATTERNS = [
    r"\b\d+\s*comments?\b",
    r"\bshare\b",
    r"\blike\b",
    r"\bfollow\b",
    r"\bsubscribe\b",
]


def clean_html_content(raw_html: str) -> str:
    text = raw_html or ""
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)

    for pattern in TAG_BLOCK_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE | re.DOTALL)

    text = re.sub(r"<(br|p|div|li|section|article|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
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


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def should_drop_line(line: str) -> bool:
    lower = line.lower()
    if len(line) < 25:
        return True
    if "copyright" in lower or "all rights reserved" in lower:
        return True
    if line.startswith("http") or "www." in lower:
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
        "판매됩니다",
        "책임을 지지 않습니다",
    ]
    if any(keyword in line for keyword in noise_keywords):
        return True
    return False
