import anthropic
import requests
import datetime
import os
import json

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
WP_CLIENT_ID = os.environ.get("WP_CLIENT_ID")
WP_CLIENT_SECRET = os.environ.get("WP_CLIENT_SECRET")
WP_SITE = "aimoneyhacksblog.wordpress.com"
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

def get_wp_token():
    response = requests.post(
        "https://public-api.wordpress.com/oauth2/token",
        data={
            "client_id": WP_CLIENT_ID,
            "client_secret": WP_CLIENT_SECRET,
            "grant_type": "client_credentials",
        }
    )
    print(f"Token response: {response.status_code}")
    print(f"Token body: {response.text[:200]}")
    return response.json().get("access_token")

def get_pexels_image(keyword):
    try:
        response = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": keyword, "per_page": 1, "orientation": "landscape"},
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
KEYWORD: [one word image search keyword]
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

    # Add Gumroad CTA at bottom
    cta = '''
<div style="background:#f0f7ff; border-left:4px solid #0066cc; padding:20px; margin-top:32px; border-radius:8px;">
  <h3 style="margin:0 0 8px;">💸 Want 100 AI Prompts to Make Money Online?</h3>
  <p style="margin:0
