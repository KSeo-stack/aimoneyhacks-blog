import anthropic
import requests
import datetime
import os

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
BLOGGER_CLIENT_ID = os.environ.get("BLOGGER_CLIENT_ID")
BLOGGER_CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET")
BLOGGER_REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN")
BLOG_ID = os.environ.get("BLOG_ID")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

def get_access_token():
    response = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": BLOGGER_CLIENT_ID,
        "client_secret": BLOGGER_CLIENT_SECRET,
        "refresh_token": BLOGGER_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    })
    return response.json()["access_token"]

def get_pexels_image(keyword):
    try:
        response = requests.get(
            "https://api.pexels.com/v1/search",
            params={
                "query": keyword,
                "per_page": 1,
                "orientation": "landscape"
            },
            headers={"Authorization": PEXELS_API_KEY}
        )
        print(f"Pexels status: {response.status_code}")
        data = response.json()
        if "photos" in data and len(data["photos"]) > 0:
            photo = data["photos"][0]
            return photo["src"]["large"], photo["photographer"], photo["url"]
    except Exception as e:
        print(f"Image fetch failed: {e}")
    return None, None, None

def generate_post():
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    today = datetime.datetime.now().strftime("%B %d, %Y")
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""Write a complete blog post for today ({today}) about AI tools or tips to make or save money.

Requirements:
- Title: catchy, specific, SEO friendly (include year 2026)
- Length: exactly 900-1000 words, NO cutting off mid-sentence
- Tone: friendly, conversational, practical
- Only mention REAL existing AI tools: ChatGPT, Claude, Gemini, Jasper, Descript, Canva AI, Midjourney, Notion AI, Copy.ai, Grammarly
- Do NOT invent fake tools, fake statistics, or fake user stories
- Structure: intro, 3 main strategies, bonus tips, strong conclusion
- Every section must be fully completed
- End with a complete call to action paragraph
- Add emojis to headings
- Format: clean HTML with h2, h3, p, ul, li tags

Return in this EXACT format with no extra text:
TITLE: [your title here]
KEYWORD: [one word image search keyword related to the post]
DESCRIPTION: [one sentence meta description]
CONTENT: [your complete html content here]"""
        }]
    )
    response = message.content[0].text
    title = response.split("TITLE:")[1].split("KEYWORD:")[0].strip()
    keyword = response.split("KEYWORD:")[1].split("DESCRIPTION:")[0].strip()
    description = response.split("DESCRIPTION:")[1].split("CONTENT:")[0].strip()
    content = response.split("CONTENT:")[1].strip()

    img_url, photographer, photo_link = get_pexels_image(keyword)
    if img_url:
        image_html = f'''
<div style="margin-bottom: 24px;">
  <img src="{img_url}" alt="{title}" style="width:100%; border-radius:8px;"/>
  <p style="font-size:12px; color:#888;">Photo by <a href="{photo_link}" target="_blank">{photographer}</a> on <a href="https://www.pexels.com" target="_blank">Pexels</a></p>
</div>
'''
        content = image_html + content

    full_content = f'<meta name="description" content="{description}">\n{content}'
    return title, full_content

def post_to_blogger(title, content):
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "title": title,
        "content": content,
        "labels": ["AI Tools", "Make Money", "Side Hustle", "Passive Income", "AI"]
    }
    response = requests.post(
        f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/",
        headers=headers,
        json=data
    )
    return response.json()

if __name__ == "__main__":
    title, content = generate_post()
    result = post_to_blogger(title, content)
    print(f"Posted: {result.get('url', 'Check your blog!')}")
