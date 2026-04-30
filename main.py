import anthropic
import requests
import datetime
import os
import random
import re
import warnings
from ddgs import DDGS
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ==========================================
# 0. 쓸데없는 경고 메시지(Warning) 완벽 차단
# ==========================================
warnings.filterwarnings("ignore")

# ==========================================
# 1. 환경 변수 세팅
# ==========================================
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
BLOGGER_CLIENT_ID = os.environ.get("BLOGGER_CLIENT_ID")
BLOGGER_CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET")
BLOGGER_REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN")
BLOG_ID = os.environ.get("BLOG_ID")

CATEGORIES = [
    "Personal Finance & Investing",
    "B2B Software & SaaS Tools",
    "Cybersecurity & Online Privacy",
    "Health, Fitness & Wellness",
    "Digital Marketing & E-commerce",
    "Remote Work & Productivity Hacks",
    "Real Estate & Mortgages"
]

FORMATS = [
    "practical step-by-step guide",
    "listicle format with numbered tips",
    "beginner-friendly explanation",
    "comparison format with pros and cons",
]

# ==========================================
# 2. 기능 함수
# ==========================================
def get_blogger_service():
    creds = Credentials(
        token=None,
        refresh_token=BLOGGER_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=BLOGGER_CLIENT_ID,
        client_secret=BLOGGER_CLIENT_SECRET
    )
    return build('blogger', 'v3', credentials=creds)

def get_recent_posts(service):
    try:
        print("Fetching recent posts to avoid duplication...")
        request = service.posts().list(blogId=BLOG_ID, maxResults=15, status='LIVE')
        response = request.execute()
        items = response.get('items', [])
        recent_titles = [item['title'] for item in items]
        print(f"Successfully fetched {len(recent_titles)} titles.")
        return recent_titles
    except Exception as e:
        print(f"⚠️ Could not fetch recent posts: {e}")
        return []

def get_pexels_image(keyword):
    try:
        response = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": keyword, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": PEXELS_API_KEY}
        )
        data = response.json()
        if "photos" in data and len(data["photos"]) > 0:
            photo = data["photos"][0]
            return photo["src"]["large"], photo["photographer"], photo["url"]
    except Exception as e:
        print(f"⚠️ Image fetch failed: {e}")
    return None, None, None

def get_real_time_context(queries):
    context_data = ""
    try:
        with DDGS() as ddgs:
            for query in queries:
                results = list(ddgs.text(query, max_results=3, timelimit='m'))
                context_data += f"\n--- Search results for '{query}' ---\n"
                for r in results:
                    context_data += f"Title: {r.get('title')}\nSnippet: {r.get('body')}\n\n"
    except Exception as e:
        print(f"⚠️ Web search blocked or failed: {e}. Proceeding with general knowledge.")
        context_data = "No real-time data available. Rely on standard factual knowledge."
    return context_data

def generate_post(recent_titles):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    today = datetime.datetime.now().strftime("%B %d, %Y")
    
    category = random.choice(CATEGORIES)
    fmt = random.choice(FORMATS)
    print(f"Selected Category: {category}")

    recent_titles_str = ", ".join(recent_titles) if recent_titles else "None"

    # [Step 1] 주제 선정 및 검색어 도출
    step1_prompt = f"""
    You are an expert SEO strategist. Choose a HIGH-CPC, trending sub-niche topic in the category of "{category}".
    
    CRITICAL RULE: Avoid these recent topics: [{recent_titles_str}]. 
    Pick a completely NEW and DIFFERENT specific topic.

    Return EXACTLY in this XML format with NO extra conversational text:
    <TOPIC>specific topic</TOPIC>
    <QUERY1>search query 1</QUERY1>
    <QUERY2>search query 2</QUERY2>
    """
    
    msg1 = client.messages.create(
        model="claude-sonnet-4-20250514",  
        max_tokens=300,
        messages=[{"role": "user", "content": step1_prompt}]
    )
    
    response1 = msg1.content[0].text
    
    # 잠재적 파싱 에러 방어
    try:
        topic = re.search(r"<TOPIC>(.*?)</TOPIC>", response1, re.DOTALL).group(1).strip()
        query1 = re.search(r"<QUERY1>(.*?)</QUERY1>", response1, re.DOTALL).group(1).strip()
        query2 = re.search(r"<QUERY2>(.*?)</QUERY2>", response1, re.DOTALL).group(1).strip()
    except Exception as e:
        print(f"⚠️ Step 1 Parsing Error: {e}. Using fallback topic.")
        topic = f"Latest Trends in {category} for 2026"
        query1 = f"{category} trends 2026"
        query2 = f"Best {category} tips"
        
    print(f"Generated Topic: {topic}")
    
    # [Step 2] 실시간 팩트 수집
    real_time_context = get_real_time_context([query1, query2])
    
    # [Step 3] 최종 글 작성
    step3_prompt = f"""
    You are an expert SEO blog writer. Today is {today}.
    Write a high-CPC blog post about: "{topic}"
    
    Context:
    <reference_data>
    {real_time_context}
    </reference_data>
    
    Requirements:
    1. Base post on <reference_data>. DO NOT invent fake numbers.
    2. Tone: Natural, engaging Native English. No AI clichés (e.g., "Delve into", "Tapestry").
    3. Format: {fmt}. Length: 900-1000 words.
    4. HTML: h2, h3, p, ul, li tags. Emojis in headings.

    Return EXACTLY in this XML format with NO extra conversational text:
    <TITLE>catchy title</TITLE>
    <KEYWORD>pexels search keyword</KEYWORD>
    <DESCRIPTION>meta description</DESCRIPTION>
    <CONTENT>full html content</CONTENT>
    """

    msg2 = client.messages.create(
        model="claude-sonnet-4-20250514",  
        max_tokens=2500,
        messages=[{"role": "user", "content": step3_prompt}]
    )
    
    response2 = msg2.content[0].text
    
    # 잠재적 파싱 에러 방어
    try:
        title = re.search(r"<TITLE>(.*?)</TITLE>", response2, re.DOTALL).group(1).strip()
        keyword = re.search(r"<KEYWORD>(.*?)</KEYWORD>", response2, re.DOTALL).group(1).strip()
        description = re.search(r"<DESCRIPTION>(.*?)</DESCRIPTION>", response2, re.DOTALL).group(1).strip()
        content = re.search(r"<CONTENT>(.*?)</CONTENT>", response2, re.DOTALL).group(1).strip()
    except Exception as e:
        print(f"⚠️ Step 3 Parsing Error: {e}. Rescuing content...")
        title = f"Complete Guide to {topic}"
        keyword = "business"
        description = f"Learn everything you need to know about {topic}."
        content = f"<h2>Introduction to {topic}</h2><p>{response2}</p>"

    # Pexels 이미지 추가
    img_url, photographer, photo_link = get_pexels_image(keyword)
    if img_url:
        image_html = f'<div style="margin-bottom:24px;"><img src="{img_url}" alt="{title}" style="width:100%;border-radius:8px;"/><p style="font-size:12px;color:#888;">Photo by <a href="{photo_link}" target="_blank">{photographer}</a> on <a href="https://www.pexels.com" target="_blank">Pexels</a></p></div>'
        content = image_html + content

    # ==========================================
    # 👇 다크모드 대응: CTA 텍스트 색상을 어두운 색(#111827, #374151)으로 강제 적용했습니다.
    # ==========================================
    cta = '''
    <div style="background:#f0f7ff; border-left:4px solid #0066cc; padding:20px; margin-top:32px; border-radius:8px;">
        <h3 style="color:#111827; margin-top:0; font-weight:bold;">Want 100 AI Prompts to Make Money Online?</h3>
        <p style="color:#374151; margin-bottom:16px;">Get our complete prompt pack with 100 copy-paste prompts to earn online with AI.</p>
        <a href="https://cashgpt00.gumroad.com/l/izbis" style="background:#0066cc; color:white; padding:10px 20px; border-radius:6px; text-decoration:none; font-weight:bold; display:inline-block;">Get the Prompt Pack</a>
    </div>
    '''
    content = content + cta

    return title, content, description, category

def post_to_blogger(service, title, content, category):
    try:
        body = {
            "kind": "blogger#post",
            "title": title,
            "content": content,
            "labels": [category.split(" ")[0], "2026 Trends", "Guide"]
        }
        print("Publishing to Blogger...")
        service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
        print(f"✅ Post published successfully!")
    except Exception as e:
        print(f"❌ Blogger publication failed: {e}")

if __name__ == "__main__":
    try:
        print("🚀 Starting Automated Blog Pipeline...")
        with get_blogger_service() as blogger_service:
            recent_titles = get_recent_posts(blogger_service)
            title, content, description, category = generate_post(recent_titles)
            post_to_blogger(blogger_service, title, content, category)
    except Exception as e:
        print(f"❌ Automation failed: {e}")
