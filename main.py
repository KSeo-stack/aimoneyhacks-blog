import anthropic
import requests
import datetime
import os
import random
from duckduckgo_search import DDGS
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ==========================================
# 1. 환경 변수 세팅 (GitHub Secrets)
# ==========================================
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
BLOGGER_CLIENT_ID = os.environ.get("BLOGGER_CLIENT_ID")
BLOGGER_CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET")
BLOGGER_REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN")
BLOG_ID = os.environ.get("BLOG_ID")

# ==========================================
# 2. 카테고리 및 포맷
# ==========================================
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
# 3. 구글 블로거 연결 및 기능 함수
# ==========================================
def get_blogger_service():
    """Blogger API 서비스 객체를 생성합니다."""
    creds = Credentials(
        token=None,
        refresh_token=BLOGGER_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=BLOGGER_CLIENT_ID,
        client_secret=BLOGGER_CLIENT_SECRET
    )
    return build('blogger', 'v3', credentials=creds)

def get_recent_posts(service):
    """최근 작성된 블로그 글 제목 15개를 가져와서 중복을 방지합니다."""
    try:
        print("Fetching recent posts to avoid duplication...")
        request = service.posts().list(blogId=BLOG_ID, maxResults=15, status='LIVE')
        response = request.execute()
        items = response.get('items', [])
        recent_titles = [item['title'] for item in items]
        print(f"Found {len(recent_titles)} recent posts.")
        return recent_titles
    except Exception as e:
        print(f"Failed to fetch recent posts: {e}")
        return []

def get_pexels_image(keyword):
    """Pexels 이미지 검색"""
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
        print(f"Image fetch failed: {e}")
    return None, None, None

def get_real_time_context(queries):
    """최신 웹 검색 팩트체크"""
    context_data = ""
    ddgs = DDGS()
    for query in queries:
        try:
            results = ddgs.text(query, max_results=3, timelimit='m')
            context_data += f"\n--- Search results for '{query}' ---\n"
            for r in results:
                context_data += f"Title: {r.get('title')}\nSnippet: {r.get('body')}\n\n"
        except Exception as e:
            print(f"Search failed for {query}: {e}")
    return context_data

def generate_post(recent_titles):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    today = datetime.datetime.now().strftime("%B %d, %Y")
    
    category = random.choice(CATEGORIES)
    fmt = random.choice(FORMATS)
    print(f"Selected Category: {category}")

    # 최근 글 제목 리스트를 문자열로 변환
    recent_titles_str = ", ".join(recent_titles) if recent_titles else "None"

    # [Step 1] 주제 선정 (중복 회피 로직 추가)
    step1_prompt = f"""
    You are an expert SEO strategist. Choose a HIGH-CPC, trending sub-niche topic in the category of "{category}".
    
    CRITICAL RULE: I have recently published posts about the following topics: [{recent_titles_str}]. 
    You MUST pick a completely NEW and DIFFERENT specific topic that does not overlap with those recent posts.

    Then, provide 2 highly effective Google search queries to find the most recent, popular blog posts and factual data about this new topic.
    
    Return EXACTLY in this format, with no other text:
    TOPIC: [your specific topic]
    QUERY1: [first search query]
    QUERY2: [second search query]
    """
    
    msg1 = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{"role": "user", "content": step1_prompt}]
    )
    
    response1 = msg1.content[0].text
    topic = response1.split("TOPIC:")[1].split("QUERY1:")[0].strip()
    query1 = response1.split("QUERY1:")[1].split("QUERY2:")[0].strip()
    query2 = response1.split("QUERY2:")[1].strip()
    
    print(f"Generated Topic: {topic}")
    
    # [Step 2] 실시간 데이터 수집
    real_time_context = get_real_time_context([query1, query2])
    
    # [Step 3] 블로그 작성 (자연스러운 문장 및 팩트 엄수 로직 추가)
    step3_prompt = f"""
    You are an expert SEO blog writer. Today is {today}.
    Write a highly-searched, high-CPC blog post about: "{topic}"
    
    Here is real-time reference data from recent popular blog posts and web search results:
    <reference_data>
    {real_time_context}
    </reference_data>
    
    CRITICAL FACTUALITY REQUIREMENTS:
    1. Base your post heavily on the <reference_data> provided. Mention the real trends and features found in the search snippets.
    2. DO NOT invent fake numbers, prices, or statistics.

    CRITICAL WRITING STYLE (NATIVE ENGLISH):
    1. Write in a highly natural, conversational, and engaging Native English tone.
    2. AVOID robotic, cliché AI phrases completely (e.g., Do NOT use "Delve into", "Tapestry", "Testament", "In conclusion", "It's important to note", "In the ever-evolving landscape").
    3. Use active voice and short, punchy sentences. Write like a top-tier human copywriter.
    
    Requirements:
    - Format: {fmt}
    - Title: Catchy, highly clickable, SEO friendly.
    - Length: Exactly 900-1000 words. DO NOT cut off mid-sentence.
    - Formatting: Clean HTML with h2, h3, p, ul, li. Add emojis to headings.

    Return in this EXACT format with no extra text at all:
    TITLE: [your generated catchy title here]
    KEYWORD: [one or two words for Pexels image search]
    DESCRIPTION: [one sentence compelling meta description]
    CONTENT: [your complete html content here]
    """

    msg2 = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2500,
        messages=[{"role": "user", "content": step3_prompt}]
    )
    
    response2 = msg2.content[0].text
    
    title = response2.split("TITLE:")[1].split("KEYWORD:")[0].strip()
    keyword = response2.split("KEYWORD:")[1].split("DESCRIPTION:")[0].strip()
    description = response2.split("DESCRIPTION:")[1].split("CONTENT:")[0].strip()
    content = response2.split("CONTENT:")[1].strip()

    # 이미지 조합
    img_url, photographer, photo_link = get_pexels_image(keyword)
    if img_url:
        image_html = f'<div style="margin-bottom:24px;"><img src="{img_url}" alt="{title}" style="width:100%;border-radius:8px;"/><p style="font-size:12px;color:#888;">Photo by <a href="{photo_link}" target="_blank">{photographer}</a> on <a href="https://www.pexels.com" target="_blank">Pexels</a></p></div>'
        content = image_html + content

    # 기존 CTA 폼 유지
    cta = '<div style="background:#f0f7ff;border-left:4px solid #0066cc;padding:20px;margin-top:32px;border-radius:8px;"><h3>Want 100 AI Prompts to Make Money Online?</h3><p>Get our complete prompt pack with 100 copy-paste prompts to earn online with AI.</p><a href="https://cashgpt00.gumroad.com/l/izbis" style="background:#0066cc;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:bold;">Get the Prompt Pack</a></div>'
    content = content + cta

    return title, content, description, category

def post_to_blogger(service, title, content, category):
    """Blogger에 글을 발행합니다."""
    try:
        body = {
            "kind": "blogger#post",
            "title": title,
            "content": content,
            "labels": [category.split(" ")[0], "2026 Trends", "Guide"]
        }
        print("Publishing post to Blogger...")
        request = service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False)
        response = request.execute()
        
        print(f"✅ Successfully posted to Blogger!")
        print(f"🔗 URL: {response.get('url')}")
    except Exception as e:
        print(f"❌ Error posting to Blogger: {e}")

if __name__ == "__main__":
    try:
        print("🚀 Starting Automated Blog Post Generation...")
        # 1. Blogger 서비스 연결
        blogger_service = get_blogger_service()
        
        # 2. 최근 글 제목 가져오기 (중복 방지용)
        recent_titles = get_recent_posts(blogger_service)
        
        # 3. 글 작성
        title, content, description, category = generate_post(recent_titles)
        
        # 4. Blogger에 발행
        post_to_blogger(blogger_service, title, content, category)
        
    except Exception as e:
        print(f"❌ Automation failed: {e}")
