import anthropic
import datetime
import html
import os
import random
import re
import time
import urllib.parse
import warnings

from pathlib import Path
from ddgs import DDGS
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

warnings.filterwarnings("ignore")

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
BLOGGER_CLIENT_ID = os.environ.get("BLOGGER_CLIENT_ID")
BLOGGER_CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET")
BLOGGER_REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN")
BLOG_ID = os.environ.get("BLOG_ID")

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL") or "claude-sonnet-4-6"
DRAFT_MODE = os.environ.get("DRAFT_MODE", "true").lower() == "true"

CTA_INSERT_RATE = 0.60

CATEGORIES = [
    "Personal Finance & Investing",
    "B2B Software & SaaS Tools",
    "Cybersecurity & Online Privacy",
    "Digital Marketing & E-commerce",
    "Remote Work & Productivity Hacks"
]

FORMATS = [
    "practical step-by-step guide",
    "listicle format with numbered tips",
    "comparison format with pros and cons",
]

CATEGORY_CONFIG = {
    "Personal Finance & Investing": {
        "label": "Personal Finance",
        "secondary_labels": ["Investing", "Money Tips"],
        "image_style": (
            "muted green and cream palette, abstract financial dashboard, "
            "soft chart shapes, coins, calm editorial finance style"
        )
    },
    "B2B Software & SaaS Tools": {
        "label": "SaaS",
        "secondary_labels": ["B2B Software", "Business Tools"],
        "image_style": (
            "soft blue and graphite palette, abstract SaaS dashboard panels, "
            "workflow cards, modern software UI shapes"
        )
    },
    "Cybersecurity & Online Privacy": {
        "label": "Cybersecurity",
        "secondary_labels": ["Online Privacy", "Security Guide"],
        "image_style": (
            "dark navy and violet palette, abstract shield, encrypted network nodes, "
            "secure server blocks, privacy concept"
        )
    },
    "Digital Marketing & E-commerce": {
        "label": "Digital Marketing",
        "secondary_labels": ["Ecommerce", "Marketing Strategy"],
        "image_style": (
            "warm coral and soft yellow palette, abstract analytics dashboard, "
            "ecommerce funnel shapes, product grid concept"
        )
    },
    "Remote Work & Productivity Hacks": {
        "label": "Remote Work",
        "secondary_labels": ["Productivity", "Work From Home"],
        "image_style": (
            "warm beige and sky blue palette, minimal workspace, calendar blocks, "
            "productivity dashboard, remote work setup"
        )
    }
}

CATEGORY_CTAS = {
    "B2B Software & SaaS Tools": """
    <div style="background:#f0f7ff; border-left:4px solid #0066cc; padding:20px; margin-top:40px; border-radius:8px;">
        <h3 style="color:#111827; margin-top:0;">Need Better AI Prompts for Business?</h3>
        <p style="color:#374151;">Use 100 prompts for SaaS research, product positioning, content planning, and business workflows.</p>
        <a href="https://cashgpt00.gumroad.com/l/izbis" style="background:#0066cc; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; display:inline-block;">Get the Prompt Pack</a>
    </div>
    """,
    "Digital Marketing & E-commerce": """
    <div style="background:#f0f7ff; border-left:4px solid #0066cc; padding:20px; margin-top:40px; border-radius:8px;">
        <h3 style="color:#111827; margin-top:0;">Want Faster Marketing Content Ideas?</h3>
        <p style="color:#374151;">Use 100 copy-paste AI prompts for content planning, product descriptions, ads, and email campaigns.</p>
        <a href="https://cashgpt00.gumroad.com/l/izbis" style="background:#0066cc; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; display:inline-block;">Get the Prompt Pack</a>
    </div>
    """,
    "Remote Work & Productivity Hacks": """
    <div style="background:#f9fafb; border-left:4px solid #111827; padding:20px; margin-top:40px; border-radius:8px;">
        <h3 style="color:#111827; margin-top:0;">Save Time with AI Workflows</h3>
        <p style="color:#374151;">Get practical AI prompts for planning, writing, research, and online productivity.</p>
        <a href="https://cashgpt00.gumroad.com/l/izbis" style="background:#111827; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; display:inline-block;">View the Prompt Pack</a>
    </div>
    """
}

BANNED_PHRASES = [
    "delve into",
    "tapestry",
    "in today's fast-paced world",
    "game-changer",
    "ever-evolving landscape",
    "unlock the power",
    "revolutionize",
    "paradigm shift",
    "the digital age",
    "cutting-edge solution"
]


def validate_env():
    required_vars = {
        "CLAUDE_API_KEY": CLAUDE_API_KEY,
        "BLOGGER_CLIENT_ID": BLOGGER_CLIENT_ID,
        "BLOGGER_CLIENT_SECRET": BLOGGER_CLIENT_SECRET,
        "BLOGGER_REFRESH_TOKEN": BLOGGER_REFRESH_TOKEN,
        "BLOG_ID": BLOG_ID,
    }

    missing = [key for key, value in required_vars.items() if not value]

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


def execute_google_request_with_retries(request, action_name="Google API request", max_retries=5):
    retryable_status_codes = {429, 500, 502, 503, 504}

    for attempt in range(max_retries):
        try:
            return request.execute()

        except HttpError as e:
            status = getattr(e.resp, "status", None)

            if status in retryable_status_codes and attempt < max_retries - 1:
                delay = (2 ** attempt) + random.uniform(0, 1.5)
                print(
                    f"⚠️ {action_name} failed with HTTP {status}. "
                    f"Retrying in {delay:.1f}s... ({attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
                continue

            raise


def extract_xml(text, tag, fallback=""):
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)

    if match:
        return match.group(1).strip()

    print(f"⚠️ Missing XML tag: {tag}. Using fallback.")
    return fallback


def clean_title(title, fallback):
    title = title.strip() if title else fallback
    title = re.sub(r"\s+", " ", title)
    return title[:120]


def clean_html_content(content, title=""):
    if not content:
        return ""

    content = re.sub(r"<h1.*?>.*?</h1>", "", content, flags=re.DOTALL | re.IGNORECASE)

    if title:
        plain_title = re.escape(title.strip())

        content = re.sub(
            rf"^\s*{plain_title}\s*(<br\s*/?>)?\s*",
            "",
            content,
            flags=re.IGNORECASE
        )

        content = re.sub(
            rf"^\s*<p>\s*{plain_title}\s*</p>\s*",
            "",
            content,
            flags=re.IGNORECASE
        )

        content = re.sub(
            rf"^\s*<strong>\s*{plain_title}\s*</strong>\s*",
            "",
            content,
            flags=re.IGNORECASE
        )

    replacements = {
        "delve into": "look at",
        "Delve into": "Look at",
        "in today's fast-paced world": "in 2026",
        "In today's fast-paced world": "In 2026",
        "ever-evolving landscape": "changing market",
        "Ever-evolving landscape": "Changing market",
        "game-changer": "useful option",
        "Game-changer": "Useful option",
        "tapestry": "mix",
        "Tapestry": "Mix",
        "unlock the power": "use",
        "Unlock the power": "Use",
        "revolutionize": "improve",
        "Revolutionize": "Improve"
    }

    for old, new in replacements.items():
        content = content.replace(old, new)

    return content.strip()


def count_words_from_html(content):
    text = re.sub(r"<.*?>", " ", content)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return len(text.split())


def get_category_labels(category):
    config = CATEGORY_CONFIG.get(category, {})
    main_label = config.get("label", category)
    secondary_labels = config.get("secondary_labels", [])

    labels = [main_label] + secondary_labels[:2] + ["2026 Guide"]

    unique_labels = []
    for label in labels:
        if label and label not in unique_labels:
            unique_labels.append(label)

    return unique_labels[:5]


def get_cta_for_category(category):
    if category not in CATEGORY_CTAS:
        return ""

    if random.random() > CTA_INSERT_RATE:
        return ""

    return CATEGORY_CTAS[category]


def get_disclaimer_for_category(category):
    if category == "Personal Finance & Investing":
        return """
        <div style="background:#fff7ed; border-left:4px solid #f97316; padding:16px; margin-top:32px; border-radius:8px;">
            <p style="margin:0;"><strong>Note:</strong> This article is for educational purposes only and is not financial, tax, or legal advice. Tax rules, account rules, state taxes, and household situations can vary. Check current IRS guidance or speak with a qualified tax professional before making retirement account decisions.</p>
        </div>
        """
    return ""


def validate_title(title):
    issues = []

    if not title or len(title.strip()) < 35:
        issues.append("Title is too short.")

    if title and len(title.strip()) > 120:
        issues.append("Title is too long.")

    overused_patterns = [
        "ultimate guide",
        "complete guide",
        "everything you need",
        "the only guide",
        "game-changing"
    ]

    lowered = title.lower() if title else ""

    for pattern in overused_patterns:
        if pattern in lowered:
            issues.append(f"Title uses an overused SEO phrase: {pattern}")

    return issues


def validate_content_quality(title, content):
    issues = []

    if not content:
        issues.append("Content is empty.")
        return issues

    lowered_all = f"{title} {content}".lower()

    for phrase in BANNED_PHRASES:
        if phrase in lowered_all:
            issues.append(f"Banned or AI-cliché phrase found: {phrase}")

    word_count = count_words_from_html(content)

    if word_count < 700:
        issues.append(f"Content is too short: {word_count} words.")

    if "quick summary" not in lowered_all:
        issues.append("Missing Quick Summary section.")

    has_table = "<table" in lowered_all
    has_checklist = "checklist" in lowered_all

    if not has_table and not has_checklist:
        issues.append("Missing both comparison table and checklist.")

    if "practical action plan" not in lowered_all:
        issues.append("Missing Practical Action Plan section.")

    if "common mistakes" not in lowered_all:
        issues.append("Missing Common Mistakes section.")

    if "cost comparison" in title.lower() or "cost guide" in title.lower():
        if "cost" not in lowered_all and "budget" not in lowered_all:
            issues.append("Title mentions cost, but content does not cover cost or budget factors.")

    if "top " in title.lower() and "solution" in title.lower():
        if "best for" not in lowered_all and "avoid if" not in lowered_all:
            issues.append("Title implies product/solution comparison, but content lacks decision-support language.")

    risky_finance_phrases = [
        "tax-free and penalty-free",
        "completely tax-free",
        "guaranteed",
        "risk-free",
        "will save you"
    ]

    for phrase in risky_finance_phrases:
        if phrase in lowered_all:
            issues.append(f"Risky finance wording found: {phrase}")

    issues.extend(validate_title(title))

    return issues


def get_blogger_service():
    creds = Credentials(
        token=None,
        refresh_token=BLOGGER_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=BLOGGER_CLIENT_ID,
        client_secret=BLOGGER_CLIENT_SECRET
    )

    return build("blogger", "v3", credentials=creds)


def get_recent_posts(service):
    try:
        print("Fetching recent Blogger posts...")

        request = service.posts().list(
            blogId=BLOG_ID,
            maxResults=30,
            status="LIVE"
        )

        response = execute_google_request_with_retries(
            request,
            action_name="Fetch recent Blogger posts"
        )

        items = response.get("items", [])
        titles = [item.get("title", "") for item in items if item.get("title")]

        print(f"Fetched {len(titles)} recent titles.")
        return titles

    except Exception as e:
        print(f"⚠️ Could not fetch recent posts: {e}")
        return []


def post_to_blogger(service, title, content, category, description):
    labels = get_category_labels(category)

    body = {
        "title": title,
        "content": content,
        "labels": labels,
        "customMetaData": description[:300] if description else ""
    }

    print(f"Publishing to Blogger... Draft mode: {DRAFT_MODE}")
    print(f"Labels: {labels}")

    request = service.posts().insert(
        blogId=BLOG_ID,
        body=body,
        isDraft=DRAFT_MODE
    )

    execute_google_request_with_retries(
        request,
        action_name="Publish Blogger post"
    )

    print("✅ Post published successfully." if not DRAFT_MODE else "✅ Draft saved successfully.")


def save_local_backup(title, content, description, category):
    backup_dir = Path("draft_backups")
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:60]

    file_path = backup_dir / f"{timestamp}_{safe_title}.html"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description or '')}">
</head>
<body>
<h1>{html.escape(title)}</h1>
<p><strong>Category:</strong> {html.escape(category)}</p>
<hr>
{content}
</body>
</html>
"""

    file_path.write_text(html_content, encoding="utf-8")
    print(f"✅ Local backup saved: {file_path}")
    return file_path


def generate_ai_image_url(topic_prompt, category):
    topic_prompt = (topic_prompt or "professional business concept")[:300]

    category_style = CATEGORY_CONFIG.get(category, {}).get(
        "image_style",
        "minimal professional editorial illustration, muted color palette"
    )

    design_style = (
        "minimalist professional digital illustration, matte texture, soft studio lighting, "
        "flat editorial design, no glossy surfaces, no human faces, no generic robots, "
        "no text, no logos, clean composition, modern blog hero image, balanced composition"
    )

    final_prompt = f"{topic_prompt}, {category_style}, {design_style}"
    encoded_prompt = urllib.parse.quote(final_prompt)
    seed = random.randint(1, 99999)

    return (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?seed={seed}&width=1280&height=720&nologo=true"
    )


def get_real_time_context(queries):
    context = ""

    try:
        with DDGS() as ddgs:
            for query in queries:
                print(f"Searching: {query}")

                try:
                    results = list(
                        ddgs.text(
                            query,
                            max_results=4,
                            timelimit="m"
                        )
                    )
                except Exception as e:
                    print(f"⚠️ Search with timelimit failed. Retrying without timelimit: {e}")
                    results = list(
                        ddgs.text(
                            query,
                            max_results=4
                        )
                    )

                context += f"\n--- Search results for: {query} ---\n"

                for result in results:
                    context += f"Title: {result.get('title')}\n"
                    context += f"Snippet: {result.get('body')}\n"
                    context += f"URL: {result.get('href')}\n\n"

    except Exception as e:
        print(f"⚠️ Web search failed: {e}")
        context = ""

    if len(context.strip()) < 300:
        context = (
            "Limited search context was available. Write a conservative evergreen guide. "
            "Do not include specific statistics, prices, breach costs, market sizes, laws, or dates unless clearly supported. "
            "Use general best practices and clearly state that costs vary by company size, tools, and requirements."
        )

    return context


def build_article_prompt(today, topic, category, post_format, context, revision_notes=""):
    revision_block = ""

    if revision_notes:
        revision_block = f"""
REVISION NOTES:
The previous draft had these issues:
{revision_notes}

Fix all of these issues in the new version.
"""

    finance_rules = ""

    if category == "Personal Finance & Investing":
        finance_rules = """
SPECIAL RULES FOR PERSONAL FINANCE AND TAX TOPICS:
- Avoid specific bracket thresholds, contribution limits, tax calculations, or account limits unless directly supported by the reference data.
- If discussing tax brackets, clearly distinguish taxable income from gross income.
- Use cautious wording such as "generally", "may", "can vary", and "depending on your situation".
- Do not say "tax-free and penalty-free" without clarifying whether you mean converted principal, contributions, or earnings.
- Do not present financial, tax, or retirement strategies as advice.
- Recommend checking current IRS guidance or speaking with a qualified tax professional for personal decisions.
"""

    return f"""
You are an expert SEO blog writer and editor.

Today is {today}.
Topic: "{topic}"
Category: "{category}"
Format: "{post_format}"

Use the reference data below. Do not invent facts, prices, statistics, dates, breach costs, tool rankings, tax brackets, contribution limits, or market claims that are not supported by the reference data or stable general knowledge.

<REFERENCE_DATA>
{context}
</REFERENCE_DATA>

{revision_block}

{finance_rules}

TARGET READER:
- Write for small business owners, solo operators, lean teams, marketers, founders, and practical decision-makers.
- For personal finance topics, write for general educational readers, not as a financial adviser.
- Do not write like an enterprise consultant unless the topic clearly requires it.
- Explain technical concepts in plain English without dumbing them down.

ARTICLE STRUCTURE:
1. Do NOT repeat the post title as an H1 or plain text. Blogger already displays the title.
2. Start immediately with a helpful "💡 Quick Summary" box using an HTML div with light blue background.
3. The Quick Summary must answer the reader's core question in 4-6 bullet points.
4. After the summary, write a short intro of 2-3 paragraphs.
5. Include one practical section near the top: "Who This Is Best For", "When This Makes Sense", or "What to Do First".
6. Include either a "✅ Checklist" or a "📊 Comparison Table" in the middle.
7. Include a "Common Mistakes to Avoid" section.
8. End with a "🚀 2026 Practical Action Plan".

SEO AND QUALITY RULES:
1. <TITLE> may include at most 1 relevant emoji only if it feels natural.
2. Title should be clear, search-friendly, and not clickbait.
3. Prefer long-tail topics with clear search intent over broad head terms.
4. Avoid using the same title pattern repeatedly.
5. Avoid overusing "Complete Guide", "Ultimate Guide", and "Best Practices".
6. Use varied title formats such as:
   - How to ...
   - [Topic] Checklist
   - [Topic] Cost Guide
   - [Option A] vs [Option B]
   - What Small Businesses Should Know About ...
7. The article must be about 900-1100 words.
8. Use clean HTML only: h2, h3, p, ul, li, table, tr, th, td, div, strong, a.
9. Use natural, engaging native English.
10. Avoid AI clichés like "delve into", "tapestry", "landscape", "in today's fast-paced world", "game-changer".
11. Do not use unsupported statistics.
12. If costs vary, say costs vary instead of inventing numbers.
13. Use concrete decision-support language: best for, avoid if, consider if, implementation steps, budget factors.
14. Do not overuse emojis. Use them mainly in headings.
15. If the title mentions "cost", "pricing", or "comparison", include a cost/budget table without inventing exact prices.
16. If the article discusses products or solutions, prefer tool categories over unsupported vendor rankings.
17. <DESCRIPTION> must be under 160 characters.
18. <IMAGE_PROMPT> must describe a minimalist, matte digital art piece for this topic. No faces. No text. No logos.

Return EXACTLY the XML format below and nothing else.

<TITLE>catchy SEO title</TITLE>
<IMAGE_PROMPT>minimalist matte image prompt</IMAGE_PROMPT>
<DESCRIPTION>meta description under 160 characters</DESCRIPTION>
<CONTENT>full HTML article</CONTENT>
"""


def parse_article_response(response_text, topic):
    title = extract_xml(response_text, "TITLE", f"{topic} in 2026")
    image_prompt = extract_xml(response_text, "IMAGE_PROMPT", topic)
    description = extract_xml(
        response_text,
        "DESCRIPTION",
        f"A practical 2026 guide to {topic}."
    )
    content = extract_xml(response_text, "CONTENT", "")

    if not content:
        raise ValueError("Claude response missing CONTENT tag. Refusing to publish broken post.")

    title = clean_title(title, f"{topic} in 2026")
    content = clean_html_content(content, title)
    description = description[:160]

    return title, image_prompt, description, content


def generate_post(recent_titles):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    today = datetime.datetime.now().strftime("%B %d, %Y")
    category = random.choice(CATEGORIES)
    post_format = random.choice(FORMATS)

    recent_titles_str = ", ".join(recent_titles) if recent_titles else "None"

    print(f"Selected category: {category}")
    print(f"Selected format: {post_format}")

    step1_prompt = f"""
You are an expert SEO strategist for an English blog.

Today is {today}.

Choose a HIGH-CPC, search-friendly, evergreen topic for the category:
"{category}"

Avoid these recent post titles:
[{recent_titles_str}]

Rules:
- Pick a specific topic, not a broad category.
- The topic must be relevant in 2026.
- Avoid semantic duplicates, not just exact title duplicates.
- Avoid fake trends or unsupported claims.
- Avoid topics that require original hands-on testing unless the article can clearly be written as a general guide.
- Prefer long-tail topics with clear search intent over broad head terms.
- Avoid broad topics that would be difficult for a small blog to rank for.
- Prefer practical, buyer-intent, comparison, checklist, cost-planning, implementation, or decision-support topics.
- For personal finance topics, prefer educational planning topics and avoid topics that require personalized advice.
- Return EXACTLY the XML format below and nothing else.

<TOPIC>specific topic</TOPIC>
<QUERY1>search query 1</QUERY1>
<QUERY2>search query 2</QUERY2>
"""

    msg1 = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": step1_prompt}]
    )

    response1 = msg1.content[0].text

    topic = extract_xml(
        response1,
        "TOPIC",
        f"2026 Trends in {category}"
    )

    query1 = extract_xml(
        response1,
        "QUERY1",
        f"{category} trends 2026"
    )

    query2 = extract_xml(
        response1,
        "QUERY2",
        f"{category} best practices 2026"
    )

    print(f"Generated topic: {topic}")

    context = get_real_time_context([query1, query2])

    article_prompt = build_article_prompt(
        today=today,
        topic=topic,
        category=category,
        post_format=post_format,
        context=context
    )

    msg2 = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": article_prompt}]
    )

    response2 = msg2.content[0].text
    title, image_prompt, description, content = parse_article_response(response2, topic)

    issues = validate_content_quality(title, content)

    if issues:
        print("⚠️ Quality issues found. Trying one revision...")
        for issue in issues:
            print(f"- {issue}")

        revision_notes = "\n".join([f"- {issue}" for issue in issues])

        revise_prompt = build_article_prompt(
            today=today,
            topic=topic,
            category=category,
            post_format=post_format,
            context=context,
            revision_notes=revision_notes
        )

        msg3 = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": revise_prompt}]
        )

        response3 = msg3.content[0].text
        title, image_prompt, description, content = parse_article_response(response3, topic)

        issues = validate_content_quality(title, content)

        if issues:
            print("❌ Quality issues remain after revision:")
            for issue in issues:
                print(f"- {issue}")
            raise ValueError("Final content failed quality validation. Refusing to publish.")

    image_url = generate_ai_image_url(image_prompt, category)
    safe_alt = html.escape(title, quote=True)

    header_image = f"""
    <div style="margin-bottom:30px;">
        <img src="{image_url}" style="width:100%; border-radius:8px;" alt="{safe_alt}"/>
    </div>
    """

    disclaimer = get_disclaimer_for_category(category)
    cta = get_cta_for_category(category)

    final_content = header_image + content + disclaimer + cta

    print(f"Generated title: {title}")
    print(f"Meta description: {description}")
    print(f"Word count: {count_words_from_html(content)}")
    print(f"Disclaimer inserted: {'Yes' if disclaimer else 'No'}")
    print(f"CTA inserted: {'Yes' if cta else 'No'}")

    return title, final_content, description, category


if __name__ == "__main__":
    try:
        print("🚀 Starting Automated Blog Pipeline...")
        print(f"Using Claude model: {CLAUDE_MODEL}")
        print(f"Draft mode: {DRAFT_MODE}")

        validate_env()

        blogger_service = get_blogger_service()
        recent_titles = get_recent_posts(blogger_service)

        title, content, description, category = generate_post(recent_titles)

        save_local_backup(title, content, description, category)

        post_to_blogger(
            service=blogger_service,
            title=title,
            content=content,
            category=category,
            description=description
        )

        print(f"✅ Success: {title}")

    except Exception as e:
        print(f"❌ Automation failed: {e}")
