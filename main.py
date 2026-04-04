import anthropic
import requests
import datetime
import os

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
WP_ACCESS_TOKEN = os.environ.get("WP_ACCESS_TOKEN")
WP_SITE = "aimoneyhacksblog.wordpress.com"
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

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
            "content": "Write a complete blog post for today (" + today + ") about AI tools or tips to make or save money.\n\nRequirements:\n- Title: catchy, specific, SEO friendly (include year 2026)\n- Length: exactly 900-1000 words, NO cutting off mid-sentence\n- Tone: friendly, conversational, practical\n- Only mention REAL existing AI tools: ChatGPT, Claude, Gemini, Jasper, Descript, Canva AI, Midjourney, Notion AI, Copy.ai, Grammarly\n- Do NOT invent fake tools, fake statistics, or fake user stories\n- Structure: intro, 3 main strategies, bonus tips, strong conclusion\n- Every section must be fully completed\n- End with a complete call to action paragraph\n- Add emojis to headings\n- Format: clean HTML with h2, h3, p, ul, li tags\n\nReturn in this EXACT format with no extra text:\nTITLE: [your title here]\nKEYWORD: [one word image search keyword]\nDESCRIPTION: [one sentence meta description]\nCONTENT: [your complete html content here]"
        }]
    )
    response = message.content[0].text
    title = response.split("TITLE:")[1].split("KEYWORD:")[0].strip()
    keyword = response.split("KEYWORD:")[1].split("DESCRIPTION:")[0].strip()
    description = response.split("DESCRIPTION:")[1].split("CONTENT:")[0].strip()
    content = response.split("CONTENT:")[1].strip()

    img_url, photographer, photo_link = get_pexels_image(keyword)
    if img_url:
        image_html = '<div style="margin-bottom:24px;"><img src="' + img_url + '" alt="' + title + '" style="width:100%;border-radius:8px;"/><p style="font-size:12px;color:#888;">Photo by <a href="' + photo_link + '" target="_blank">' + photographer + '</a> on <a href="https://www.pexels.com" target="_blank">Pexels</a></p></div>'
        content = image_html + content

    cta = '<div style="background:#f0f7ff;border-left:4px solid #0066cc;padding:20px;margin-top:32px;border-radius:8px;"><h3>Want 100 AI Prompts to Make Money Online?</h3><p>Get our complete prompt pack with 100 copy-paste prompts to earn online with AI.</p><a href="https://cashgpt00.gumroad.com/l/izbis" style="background:#0066cc;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:bold;">Get the Prompt Pack</a></div>'
    content = content + cta
    return title, content, description

def post_to_wordpress(title, content, description):
    headers = {
        "Authorization": "Bearer " + WP_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "title": title,
        "content": content,
        "status": "publish",
        "excerpt": description,
        "tags": ["AI", "make money", "side hustle", "ChatGPT", "passive income"]
    }
    response = requests.post(
        "https://public-api.wordpress.com/rest/v1.1/sites/" + WP_SITE + "/posts/new",
        headers=headers,
        json=data
    )
    print(f"WordPress response: {response.status_code}")
    print(f"Full result: {response.text[:300]}")
    return response.json()

if __name__ == "__main__":
    title, content, description = generate_post()
    result = post_to_wordpress(title, content, description)
    print(f"Posted: {result.get('URL', 'Check your blog!')}")
