import os
import re
import json
import time
import random
import html
import warnings
import datetime
from pathlib import Path
from typing import List, Tuple, Optional

import requests
import anthropic

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ==========================================
# 0. 설정
# ==========================================
warnings.filterwarnings("ignore")

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "").strip()
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "").strip() or "claude-sonnet-4-6"

BLOGGER_CLIENT_ID = os.environ.get("BLOGGER_CLIENT_ID", "").strip()
BLOGGER_CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET", "").strip()
BLOGGER_REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN", "").strip()
BLOG_ID = os.environ.get("BLOG_ID", "").strip()

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()

DRAFT_MODE = os.environ.get("DRAFT_MODE", "true").strip().lower() in ("1", "true", "yes", "y")
HIGH_RISK_DRAFT_MODE = os.environ.get("HIGH_RISK_DRAFT_MODE", "true").strip().lower() in ("1", "true", "yes", "y")

BACKUP_DIR = Path("draft_backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

CATEGORIES = [
    "Personal Finance & Investing",
    "B2B Software & SaaS Tools",
    "Cybersecurity & Online Privacy",
    "Digital Marketing & E-commerce",
    "Remote Work & Productivity Hacks",
]

FORMATS = [
    "practical step-by-step guide",
    "listicle format with numbered tips",
    "comparison format with pros and cons",
]

CATEGORY_LABELS = {
    "Personal Finance & Investing": ["Personal Finance", "Investing", "Money Tips", "2026 Guide"],
    "B2B Software & SaaS Tools": ["B2B Software", "SaaS Tools", "Business Tech", "2026 Guide"],
    "Cybersecurity & Online Privacy": ["Cybersecurity", "Online Privacy", "Security Guide", "2026 Guide"],
    "Digital Marketing & E-commerce": ["Digital Marketing", "E-commerce", "Growth Tips", "2026 Guide"],
    "Remote Work & Productivity Hacks": ["Remote Work", "Productivity", "Work Smarter", "2026 Guide"],
}

HIGH_RISK_CATEGORIES = {
    "Personal Finance & Investing",
    "Cybersecurity & Online Privacy",
}

CTA_ALLOWED_CATEGORIES = {
    "B2B Software & SaaS Tools",
    "Digital Marketing & E-commerce",
    "Remote Work & Productivity Hacks",
}

BANNED_AI_PHRASES = [
    "in today's fast-paced digital landscape",
    "ever-evolving",
    "delve into",
    "game-changer",
    "it's important to note",
    "in conclusion",
    "to sum up",
    "one-size-fits-all",
    "unlock the power of",
]

GUESS_PRICING_PATTERNS = [
    r"(?:~|approximately|approx\.?|around|roughly|about|typically|usually|estimated(?:\s+at)?|averages?)\s*\$[\d,]+(?:\.\d+)?",
    r"\$[\d,]+(?:\.\d+)?\s*(?:-|–|—|to)\s*\$?[\d,]+(?:\.\d+)?",
]

FINANCE_DISCLAIMER_PATTERNS = [
    r"\bpersonal finance\b",
    r"\bemergency fund\b",
    r"\bsavings account(s)?\b",
    r"\bhigh-yield savings\b",
    r"\binvest(?:ing|ment|ments|or|ors|ed|s)?\b",
    r"\bdividend(s)?\b",
    r"\broth\b",
    r"\bira\b",
    r"\b401k\b",
    r"\b401\(k\)\b",
    r"\betf(s)?\b",
    r"\bstock(s)?\b",
    r"\bportfolio(s)?\b",
    r"\bretirement\b",
    r"\btax(?:es|able|ation)?\b",
    r"\bbrokerage\b",
    r"\bpassive income\b",
]


# ==========================================
# 1. 공용 유틸
# ==========================================
def log(msg: str):
    print(msg, flush=True)


def sanitize_filename(text: str, max_len: int = 80) -> str:
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:max_len].strip()
    return text.replace(" ", "_")


def save_local_html_backup(title: str, content: str) -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = sanitize_filename(title)
    path = BACKUP_DIR / f"{timestamp}_{safe_title}.html"
    path.write_text(content, encoding="utf-8")
    log(f"✅ Local HTML backup saved: {path}")
    return path


def save_validation_report(title: str, issues: List[str]) -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = sanitize_filename(title)
    path = BACKUP_DIR / f"{timestamp}_{safe_title}_validation_report.json"
    payload = {
        "title": title,
        "issues": issues,
        "created_at": datetime.datetime.now().isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"✅ Validation report saved: {path}")
    return path


def extract_tag(text: str, tag: str) -> str:
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError(f"Missing tag: {tag}")
    return match.group(1).strip()


def word_count(text: str) -> int:
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return len(clean.split())


def with_retry(func, max_attempts=4, base_sleep=2, retriable_statuses=(429, 500, 503)):
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func()

        except HttpError as e:
            status = getattr(e.resp, "status", None)
            last_error = e

            if status not in retriable_statuses or attempt == max_attempts:
                raise

            sleep_s = base_sleep * attempt
            log(f"⚠️ Blogger API temporary error ({status}). Retry {attempt}/{max_attempts} in {sleep_s}s...")
            time.sleep(sleep_s)

        except requests.RequestException as e:
            last_error = e

            if attempt == max_attempts:
                raise

            sleep_s = base_sleep * attempt
            log(f"⚠️ Network error. Retry {attempt}/{max_attempts} in {sleep_s}s...")
            time.sleep(sleep_s)

    if last_error:
        raise last_error


# ==========================================
# 2. Blogger
# ==========================================
def get_blogger_service():
    creds = Credentials(
        token=None,
        refresh_token=BLOGGER_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=BLOGGER_CLIENT_ID,
        client_secret=BLOGGER_CLIENT_SECRET,
    )

    return build("blogger", "v3", credentials=creds)


def get_recent_posts(service, max_results: int = 15) -> List[str]:
    log("Fetching recent Blogger posts...")

    try:
        response = with_retry(
            lambda: service.posts().list(
                blogId=BLOG_ID,
                maxResults=max_results,
                status="LIVE"
            ).execute()
        )

        items = response.get("items", [])
        titles = [item.get("title", "").strip() for item in items if item.get("title")]

        log(f"Fetched {len(titles)} recent titles.")
        return titles

    except Exception as e:
        log(f"⚠️ Could not fetch recent posts: {e}")
        return []


def post_to_blogger(service, title: str, content: str, labels: List[str], is_draft: bool = True):
    body = {
        "title": title,
        "content": content,
        "labels": labels
    }

    log(f"Publishing to Blogger... Draft mode: {is_draft}")
    log(f"Labels: {labels}")

    result = with_retry(
        lambda: service.posts().insert(
            blogId=BLOG_ID,
            body=body,
            isDraft=is_draft
        ).execute(),
        max_attempts=5,
        base_sleep=3
    )

    if is_draft:
        log("✅ Draft saved successfully.")
    else:
        log("✅ Post published successfully.")

    return result


# ==========================================
# 3. 검색 / 참고 데이터
# ==========================================
def get_real_time_context(queries: List[str], max_results: int = 4) -> str:
    context_blocks = []

    try:
        with DDGS() as ddgs:
            for q in queries:
                log(f"Searching: {q}")

                try:
                    results = list(ddgs.text(q, max_results=max_results))
                except Exception as e:
                    log(f"⚠️ Search failed for query '{q}': {e}")
                    results = []

                for r in results:
                    title = r.get("title", "").strip()
                    body = r.get("body", "").strip()
                    href = r.get("href", "").strip()

                    if title or body:
                        context_blocks.append(
                            f"Source Title: {title}\n"
                            f"Snippet: {body}\n"
                            f"URL: {href}\n"
                        )

    except Exception as e:
        log(f"⚠️ Search failed: {e}")

    if not context_blocks:
        return (
            "No fresh reference data retrieved. Use broadly accepted, non-speculative information. "
            "Avoid exact pricing, exact tax numbers, exact performance claims, and unsupported rankings."
        )

    return "\n---\n".join(context_blocks[:12])


# ==========================================
# 4. Pexels 이미지
# ==========================================
def topic_to_image_query(topic: str, category: str) -> str:
    topic_lower = topic.lower()

    if "dividend" in topic_lower:
        return "dividend investing finance"
    if "emergency fund" in topic_lower:
        return "personal finance savings"
    if "crm" in topic_lower:
        return "crm sales dashboard business"
    if "password manager" in topic_lower:
        return "cybersecurity password laptop"
    if "google shopping" in topic_lower:
        return "ecommerce online store marketing"
    if "remote work" in topic_lower or "productivity" in topic_lower:
        return "remote work productivity desk"
    if "sales pipeline" in topic_lower:
        return "sales team business meeting"

    if category == "Personal Finance & Investing":
        return "personal finance investing"
    if category == "B2B Software & SaaS Tools":
        return "saas software business dashboard"
    if category == "Cybersecurity & Online Privacy":
        return "cybersecurity privacy laptop"
    if category == "Digital Marketing & E-commerce":
        return "digital marketing ecommerce"
    if category == "Remote Work & Productivity Hacks":
        return "productivity workspace"

    return topic


def get_pexels_image(search_query: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not PEXELS_API_KEY:
        log("⚠️ PEXELS_API_KEY not found. Skipping hero image.")
        return None, None, None

    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": search_query,
        "per_page": 10,
        "orientation": "landscape"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        response.raise_for_status()

        data = response.json()
        photos = data.get("photos", [])

        if not photos:
            log("⚠️ No Pexels image found.")
            return None, None, None

        chosen = photos[0]
        src = chosen.get("src", {})

        image_url = src.get("large2x") or src.get("large") or src.get("original")
        photographer = chosen.get("photographer")
        photo_page = chosen.get("url")

        return image_url, photographer, photo_page

    except Exception as e:
        log(f"⚠️ Pexels fetch failed: {e}")
        return None, None, None


def build_header_image_html(title: str, topic: str, category: str) -> str:
    search_query = topic_to_image_query(topic, category)
    image_url, photographer, photo_page = get_pexels_image(search_query)

    if not image_url:
        return ""

    alt_text = html.escape(title)
    photographer_html = html.escape(photographer or "Unknown")
    photo_page_html = html.escape(photo_page or "https://www.pexels.com/")

    return f"""
    <div style="margin: 0 0 28px 0;">
        <img src="{image_url}" alt="{alt_text}" style="width:100%; border-radius:18px; display:block;" />
        <p style="margin:14px 0 0 0; font-size:15px; line-height:1.6; color:#9ca3af;">
            Photo by <a href="{photo_page_html}" target="_blank" rel="noopener" style="color:#d9f99d; text-decoration:none;">{photographer_html}</a> on
            <a href="https://www.pexels.com/" target="_blank" rel="noopener" style="color:#d9f99d; text-decoration:none;">Pexels</a>
        </p>
    </div>
    """


# ==========================================
# 5. HTML 후처리
# ==========================================
def remove_duplicate_title_from_content(content: str, title: str) -> str:
    if not content or not title:
        return content

    escaped_title = re.escape(title.strip())

    patterns = [
        rf"^\s*<h1[^>]*>\s*{escaped_title}\s*</h1>\s*",
        rf"^\s*<h2[^>]*>\s*{escaped_title}\s*</h2>\s*",
        rf"^\s*<p[^>]*>\s*{escaped_title}\s*</p>\s*",
        rf"^\s*<strong[^>]*>\s*{escaped_title}\s*</strong>\s*",
        rf"^\s*{escaped_title}\s*(<br\s*/?>)?\s*",
    ]

    for pattern in patterns:
        content = re.sub(pattern, "", content, count=1, flags=re.IGNORECASE | re.DOTALL)

    return content.strip()


def remove_wrong_finance_disclaimer(content: str, category: str) -> str:
    if category == "Personal Finance & Investing":
        return content

    disclaimer_div_pattern = re.compile(
        r"<div\b[^>]*>.*?(not financial, tax, or legal advice|educational purposes only).*?</div>",
        re.IGNORECASE | re.DOTALL
    )

    content = disclaimer_div_pattern.sub("", content)

    plain_disclaimer_pattern = re.compile(
        r"Note:\s*This article is for educational purposes only and is not financial, tax, or legal advice\..*?(decisions\.|situation\.)",
        re.IGNORECASE | re.DOTALL
    )

    content = plain_disclaimer_pattern.sub("", content)

    return content.strip()


def merge_inline_style(tag_html: str, extra_style: str) -> str:
    if 'style="' in tag_html:
        return re.sub(
            r'style="([^"]*)"',
            lambda m: 'style="' + m.group(1).rstrip(";") + f'; {extra_style}"',
            tag_html,
            count=1,
            flags=re.IGNORECASE
        )

    return tag_html[:-1] + f' style="{extra_style}">'


def force_text_color_in_block(block_html: str, color: str = "#111827") -> str:
    tags = ["h2", "h3", "h4", "p", "li", "span", "strong", "em", "ul", "ol", "a"]

    pattern = re.compile(
        rf"<({'|'.join(tags)})\b([^>]*)>",
        re.IGNORECASE
    )

    def repl(match):
        tag = match.group(1)
        attrs = match.group(2) or ""
        original = f"<{tag}{attrs}>"

        if tag.lower() == "a":
            style = "color:#1d4ed8 !important;"
        else:
            style = f"color:{color} !important;"

        return merge_inline_style(original, style)

    return pattern.sub(repl, block_html)


def restyle_special_boxes(content: str) -> str:
    quick_pattern = re.compile(
        r"<div\b[^>]*>.*?(Quick Summary|💡\s*Quick Summary).*?</div>",
        re.IGNORECASE | re.DOTALL
    )

    def quick_repl(match):
        block = match.group(0)

        block = re.sub(
            r"<div\b[^>]*>",
            (
                '<div style="background:#eff6ff !important; '
                'border-left:4px solid #3b82f6 !important; '
                'padding:22px !important; '
                'margin:24px 0 !important; '
                'border-radius:16px !important; '
                'color:#111827 !important;">'
            ),
            block,
            count=1,
            flags=re.IGNORECASE
        )

        return force_text_color_in_block(block, "#111827")

    content = quick_pattern.sub(quick_repl, content)

    note_pattern = re.compile(
        r"<div\b[^>]*>.*?(Note:|educational purposes only|not financial, tax, or legal advice).*?</div>",
        re.IGNORECASE | re.DOTALL
    )

    def note_repl(match):
        block = match.group(0)

        block = re.sub(
            r"<div\b[^>]*>",
            (
                '<div style="background:#fff7ed !important; '
                'border-left:4px solid #f97316 !important; '
                'padding:22px !important; '
                'margin:28px 0 !important; '
                'border-radius:16px !important; '
                'color:#111827 !important;">'
            ),
            block,
            count=1,
            flags=re.IGNORECASE
        )

        return force_text_color_in_block(block, "#111827")

    content = note_pattern.sub(note_repl, content)

    return content


def style_tables(content: str) -> str:
    table_pattern = re.compile(r"<table\b.*?</table>", re.IGNORECASE | re.DOTALL)

    def table_repl(match):
        table_html = match.group(0)

        table_html = re.sub(
            r"<table\b[^>]*>",
            (
                '<div style="overflow-x:auto; '
                '-webkit-overflow-scrolling:touch; '
                'margin:24px 0;">'
                '<table style="min-width:720px; '
                'width:100%; '
                'border-collapse:collapse; '
                'table-layout:auto; '
                'background:#ffffff !important; '
                'color:#111827 !important; '
                'border:1px solid #d1d5db; '
                'font-size:16px; '
                'line-height:1.6;">'
            ),
            table_html,
            count=1,
            flags=re.IGNORECASE
        )

        table_html = re.sub(
            r"</table>",
            "</table></div>",
            table_html,
            count=1,
            flags=re.IGNORECASE
        )

        table_html = re.sub(
            r"<th\b([^>]*)>",
            (
                '<th style="background:#e5e7eb !important; '
                'color:#111827 !important; '
                'border:1px solid #cbd5e1 !important; '
                'padding:14px 16px !important; '
                'text-align:left !important; '
                'vertical-align:top !important; '
                'font-weight:700 !important; '
                'min-width:160px !important; '
                'white-space:normal !important; '
                'word-break:keep-all !important; '
                'overflow-wrap:break-word !important;">'
            ),
            table_html,
            flags=re.IGNORECASE
        )

        table_html = re.sub(
            r"<td\b([^>]*)>",
            (
                '<td style="background:#ffffff !important; '
                'color:#111827 !important; '
                'border:1px solid #d1d5db !important; '
                'padding:14px 16px !important; '
                'text-align:left !important; '
                'vertical-align:top !important; '
                'white-space:normal !important; '
                'word-break:normal !important; '
                'overflow-wrap:break-word !important;">'
            ),
            table_html,
            flags=re.IGNORECASE
        )

        table_html = re.sub(
            r"<tr\b([^>]*)>",
            "<tr>",
            table_html,
            flags=re.IGNORECASE
        )

        return table_html

    return table_pattern.sub(table_repl, content)


def post_process_html(content: str, title: str, category: str) -> str:
    content = remove_duplicate_title_from_content(content, title)
    content = remove_wrong_finance_disclaimer(content, category)
    content = restyle_special_boxes(content)
    content = style_tables(content)
    return content


# ==========================================
# 6. CTA / Disclaimer / Labels
# ==========================================
def should_insert_cta(title: str, category: str, content: str) -> bool:
    if category not in CTA_ALLOWED_CATEGORIES:
        return False

    haystack = f"{title} {category} {re.sub(r'<[^>]+>', ' ', content)}".lower()

    related_keywords = [
        "ai",
        "automation",
        "prompt",
        "saas",
        "workflow",
        "content",
        "marketing",
        "productivity",
        "e-commerce",
        "crm",
        "software",
        "tool",
    ]

    return any(k in haystack for k in related_keywords)


def build_cta_html() -> str:
    return """
    <div style="background:#f0f7ff; border-left:4px solid #2563eb; padding:22px; margin-top:40px; border-radius:16px;">
        <h3 style="margin-top:0; margin-bottom:10px; color:#111827;">Need Better AI Prompts for Business?</h3>
        <p style="margin:0 0 16px 0; color:#374151; line-height:1.7;">
            Use 100 prompts for SaaS research, product positioning, content planning, and business workflows.
        </p>
        <a href="https://cashgpt00.gumroad.com/l/izbis"
           style="display:inline-block; background:#2563eb; color:#ffffff; text-decoration:none; padding:12px 18px; border-radius:10px; font-weight:700;">
           Get the Prompt Pack
        </a>
    </div>
    """


def needs_finance_disclaimer(category: str, title: str, content: str) -> bool:
    if category == "Personal Finance & Investing":
        return True

    haystack = f"{title} {re.sub(r'<[^>]+>', ' ', content)}".lower()

    for pattern in FINANCE_DISCLAIMER_PATTERNS:
        if re.search(pattern, haystack, flags=re.IGNORECASE):
            return True

    return False


def build_finance_disclaimer_html() -> str:
    return """
    <div style="background:#fff7ed; border-left:4px solid #f97316; padding:22px; margin-top:32px; border-radius:16px; color:#111827;">
        <p style="margin:0; color:#111827; line-height:1.8;">
            <strong>Note:</strong> This article is for educational purposes only and is not financial, tax, or legal advice.
            Savings account terms, interest rates, tax treatment, account rules, and household situations can vary.
            Consider checking current account terms or speaking with a qualified financial or tax professional before making personal financial decisions.
        </p>
    </div>
    """


def build_labels(category: str, title: str, content: str) -> List[str]:
    base = CATEGORY_LABELS.get(category, ["2026 Guide"])

    text = f"{title} {re.sub(r'<[^>]+>', ' ', content)}".lower()

    extras = []

    keyword_map = {
        "crm": "CRM",
        "sales pipeline": "Sales Automation",
        "dividend": "Dividend Investing",
        "emergency fund": "Emergency Fund",
        "savings": "Savings",
        "password": "Password Managers",
        "google shopping": "Google Ads",
        "remote work": "Remote Work",
        "productivity": "Productivity Tips",
        "cybersecurity": "Cybersecurity",
        "saas": "SaaS Tools",
        "e-commerce": "E-commerce",
    }

    for keyword, label in keyword_map.items():
        if keyword in text and label not in extras and label not in base:
            extras.append(label)

    labels = base + extras
    return labels[:6]


# ==========================================
# 7. 품질 검증
# ==========================================
def validate_content_quality(title: str, content: str) -> List[str]:
    issues = []

    wc = word_count(content)

    if wc < 900:
        issues.append(f"Word count too low: {wc}")

    title_clean = title.strip()

    if len(title_clean) < 35:
        issues.append("Title too short")

    lowered = re.sub(r"<[^>]+>", " ", content).lower()

    for phrase in BANNED_AI_PHRASES:
        if phrase in lowered:
            issues.append(f"Banned AI phrase found: {phrase}")

    for pattern in GUESS_PRICING_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            issues.append(f"Guess-pricing or vague numeric pricing pattern found: {pattern}")

    if "<script" in content.lower():
        issues.append("Unsafe HTML detected")

    if lowered.count("quick summary") == 0:
        issues.append("Missing Quick Summary section")

    if "practical action plan" not in lowered and "action plan" not in lowered:
        issues.append("Missing action plan section")

    return issues


# ==========================================
# 8. AI 글 생성
# ==========================================
def build_topic_prompt(category: str, fmt: str, recent_titles_str: str) -> str:
    return f"""
You are selecting a blog topic for a US-facing blog in 2026.

Category: {category}
Format preference: {fmt}
Avoid topics too similar to these recent titles: {recent_titles_str}

Rules:
1. Choose ONE topic only.
2. Prefer commercially relevant, evergreen, SEO-friendly topics.
3. The topic must be practical and genuinely useful.
4. Avoid clickbait.
5. Avoid exact pricing topics unless pricing can be handled carefully with "pricing varies" language.
6. Return XML only with:
<TOPIC>...</TOPIC>
<QUERY1>...</QUERY1>
<QUERY2>...</QUERY2>
"""


def build_content_prompt(topic: str, category: str, fmt: str, reference_data: str) -> str:
    high_risk = category in HIGH_RISK_CATEGORIES

    extra_rule = ""

    if high_risk:
        extra_rule = """
IMPORTANT RISK RULE:
- Do NOT invent exact prices, yields, returns, tax outcomes, or security claims.
- If exact pricing or numbers are not clearly supported by the reference data, say: "Pricing varies by plan, billing term, and vendor."
- For financial or tax topics, stay educational and general. Do not give personalized advice.
"""

    return f"""
You are writing a polished blog post for a real blog called "AI Money Hacks".

Topic: {topic}
Category: {category}
Preferred format: {fmt}

Reference data:
<REFERENCE_DATA>
{reference_data}
</REFERENCE_DATA>

Writing style rules:
- Write in natural, fluent American English.
- Sound human, clear, and modern. Do NOT sound robotic.
- Slightly warm tone is okay, but do NOT use slang like "lol" or Korean slang.
- Use 1-2 tasteful emojis where appropriate, not too many.
- Get to the core point fast.
- Use short-to-medium paragraphs for readability.
- Add useful bold emphasis with <strong>...</strong> for important points.
- Keep the article around 1000-1400 words.
- No fake urgency.
- No fake statistics.
- No made-up prices.
- No unsupported exact numbers.
- No markdown. Return clean HTML inside CONTENT.
- Do NOT repeat the title inside CONTENT. Blogger already displays the title.

Structure rules:
1. <TITLE> should be SEO-friendly and natural. No excessive hype.
2. Start CONTENT with a visible Quick Summary box:
   - include heading "💡 Quick Summary"
   - 5 to 6 bullet points
3. Then a short intro.
4. Include section "Who This Is Best For"
5. Include 3-6 practical main sections
6. Include either a checklist or a comparison table
7. Include section "Common Mistakes to Avoid"
8. End with "🚀 2026 Practical Action Plan"
9. If relevant, include a comparison table in HTML <table> format.
10. Avoid repeating the exact same sentence structure.

HTML formatting rules:
- Use <h2>, <h3>, <p>, <ul>, <ol>, <li>, <table>, <tr>, <th>, <td>, <strong>.
- Use a div box for Quick Summary.
- Do not include full HTML document wrapper.
- Do not include script tags.

{extra_rule}

Return XML only:
<TITLE>...</TITLE>
<META_DESCRIPTION>...</META_DESCRIPTION>
<CONTENT>...</CONTENT>
"""


def build_revision_prompt(title: str, content: str, issues: List[str], category: str) -> str:
    joined_issues = "\n".join(f"- {i}" for i in issues)

    return f"""
Revise the following blog post so it passes quality checks.

Category: {category}
Current Title: {title}

Issues to fix:
{joined_issues}

Rules:
- Keep the same overall topic.
- Improve clarity and keep the article useful.
- Remove vague or approximate pricing.
- If pricing is uncertain, use generic wording like "Pricing varies by plan, billing term, and vendor."
- Preserve the blog structure.
- Do NOT repeat the title inside CONTENT.
- Keep HTML clean.

Return XML only:
<TITLE>...</TITLE>
<META_DESCRIPTION>...</META_DESCRIPTION>
<CONTENT>...</CONTENT>

Current content:
<CONTENT_BLOCK>
{content}
</CONTENT_BLOCK>
"""


def generate_post(recent_titles: List[str]) -> Tuple[str, str, str, str, bool, List[str]]:
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    category = random.choice(CATEGORIES)
    fmt = random.choice(FORMATS)

    log(f"Selected category: {category}")
    log(f"Selected format: {fmt}")

    recent_titles_str = ", ".join(recent_titles) if recent_titles else "None"

    topic_resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": build_topic_prompt(category, fmt, recent_titles_str)}],
    )

    topic_text = topic_resp.content[0].text

    topic = extract_tag(topic_text, "TOPIC")
    query1 = extract_tag(topic_text, "QUERY1")
    query2 = extract_tag(topic_text, "QUERY2")

    log(f"Generated topic: {topic}")

    reference_data = get_real_time_context([query1, query2])

    content_resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": build_content_prompt(topic, category, fmt, reference_data)}],
    )

    raw = content_resp.content[0].text

    title = extract_tag(raw, "TITLE")
    meta_description = extract_tag(raw, "META_DESCRIPTION")
    content = extract_tag(raw, "CONTENT")

    content = remove_duplicate_title_from_content(content, title)
    content = remove_wrong_finance_disclaimer(content, category)

    issues = validate_content_quality(title, content)
    validation_passed = len(issues) == 0

    if issues:
        log("⚠️ Quality issues found. Trying one revision...")

        for issue in issues:
            log(f"- {issue}")

        revision_resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": build_revision_prompt(title, content, issues, category)}],
        )

        revised = revision_resp.content[0].text

        title = extract_tag(revised, "TITLE")
        meta_description = extract_tag(revised, "META_DESCRIPTION")
        content = extract_tag(revised, "CONTENT")

        content = remove_duplicate_title_from_content(content, title)
        content = remove_wrong_finance_disclaimer(content, category)

        issues = validate_content_quality(title, content)
        validation_passed = len(issues) == 0

        if issues:
            log("❌ Quality issues remain after revision:")

            for issue in issues:
                log(f"- {issue}")

    content = post_process_html(content, title, category)

    header_img = build_header_image_html(title, topic, category)

    disclaimer_html = build_finance_disclaimer_html() if needs_finance_disclaimer(category, title, content) else ""
    cta_html = build_cta_html() if should_insert_cta(title, category, content) else ""

    log(f"Generated title: {title}")
    log(f"Meta description: {meta_description}")
    log(f"Word count: {word_count(content)}")
    log(f"Disclaimer inserted: {'Yes' if disclaimer_html else 'No'}")
    log(f"CTA inserted: {'Yes' if cta_html else 'No'}")
    log(f"Validation passed: {validation_passed}")

    final_content = header_img + content + disclaimer_html + cta_html

    return title, final_content, meta_description, category, validation_passed, issues


# ==========================================
# 9. 메인 실행
# ==========================================
if __name__ == "__main__":
    try:
        log("🚀 Starting Automated Blog Pipeline...")
        log(f"Using Claude model: {CLAUDE_MODEL}")
        log(f"Draft mode from YAML: {DRAFT_MODE}")
        log(f"High-risk draft mode from YAML: {HIGH_RISK_DRAFT_MODE}")

        if not CLAUDE_API_KEY:
            raise ValueError("Missing CLAUDE_API_KEY")

        if not BLOGGER_CLIENT_ID or not BLOGGER_CLIENT_SECRET or not BLOGGER_REFRESH_TOKEN or not BLOG_ID:
            raise ValueError("Missing Blogger credentials or BLOG_ID")

        service = get_blogger_service()
        recent_titles = get_recent_posts(service)

        title, final_content, meta_description, category, validation_passed, issues = generate_post(recent_titles)

        high_risk_draft_mode = HIGH_RISK_DRAFT_MODE and category in HIGH_RISK_CATEGORIES
        final_draft_mode = DRAFT_MODE or high_risk_draft_mode

        log(f"High-risk draft mode applied: {high_risk_draft_mode}")

        if not validation_passed:
            save_local_html_backup(title, final_content)
            save_validation_report(title, issues)
            raise ValueError("Final content failed quality validation. Backup and validation report were saved.")

        save_local_html_backup(title, final_content)

        labels = build_labels(category, title, final_content)

        post_to_blogger(
            service=service,
            title=title,
            content=final_content,
            labels=labels,
            is_draft=final_draft_mode
        )

        log(f"✅ Success: {title}")

    except Exception as e:
        log(f"❌ Automation failed: {e}")
        raise
