import anthropic
import requests
import datetime
import os
import random

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
WP_ACCESS_TOKEN = os.environ.get("WP_ACCESS_TOKEN")
WP_SITE = "aimoneyhacksblog.wordpress.com"
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

TOPICS = [
    "how to make money online with AI tools in 2026",
    "best AI side hustles you can start with no experience",
    "how to use ChatGPT to make your first $1000 online",
    "AI tools that pay you to use them in 2026",
    "how to make passive income with AI in 2026",
    "how to sell AI-generated content online",
    "best ways to monetize a blog using AI in 2026",
    "how to make money on Fiverr using AI tools",
    "how to create and sell digital products using AI",
    "how to build a profitable online business with AI",
    "how to save money every month using AI tools",
    "best AI budgeting tools to manage your money in 2026",
    "how to use AI to cut your monthly expenses",
    "AI tools that help you invest smarter in 2026",
    "how to use ChatGPT for personal finance planning",
    "best free AI tools to track and grow your savings",
    "how AI can help you get out of debt faster",
    "how to use AI to find better deals and discounts",
    "ChatGPT vs Claude which is better for making money",
    "best AI writing tools for freelancers in 2026",
    "how to use Canva AI to create income online",
    "best AI tools for content creators in 2026",
    "how to use Notion AI to run a more profitable business",
    "best AI tools for small business owners in 2026",
    "how Grammarly and Copy.ai can boost your freelance income",
    "best AI image tools to make money online in 2026",
    "how to start a freelance writing business using AI",
    "best side hustles using AI that actually make money",
    "how to use AI to land more freelance clients",
    "how to build a side hustle with AI in just one weekend",
    "how to offer AI services on Upwork and Fiverr",
    "how to use Descript to start a podcast editing business",
    "how to use Midjourney to sell art and graphics online",
    "how to use AI to write faster and earn more as a freelancer",
    "how to use AI for social media marketing to grow income",
    "best AI tools for email marketing in 2026",
    "how to use ChatGPT to write better ads and get more sales",
    "how to grow a blog using AI and make money from it",
    "how to use AI for affiliate marketing in 2026",
    "how to use AI to grow your YouTube channel and earn money",
]

FORMATS = [
    "Use a practical step-by-step guide format",
    "Use a listicle format with numbered tips and clear takeaways",
    "Use a beginner-friendly format explaining everything simply",
    "Use a comparison format with clear pros and cons",
    "Use a myth-busting format that challenges common misconceptions",
    "Use a case study style showing hypothetical before and after scenarios",
    "Use a Q&A format answering the most common questions",
]

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
    day_of_year = datetime.datetime.now().timetuple().tm_yday
    topic = TOPICS[day_of_year % len(TOPICS)]
    fmt = FORMATS[day_of_year % len(FORMATS)]
    print(f"Topic: {topic}")
    print(f"Format: {fmt}")
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": "Write a complete blog post for today (" + today + ") about: " + topic + "\n\n" + fmt + "\n\nRequirements:\n- Title: catchy, specific, SEO friendly (include year 2026)\n- Length: exactly 900-1000 words, NO cutting off mid-sentence\n- Tone: friendly, conversational, practical, engaging\n- Only mention REAL existing AI tools: ChatGPT, Claude, Gemini, Jasper, Descript, Canva AI, Midjourney, Notion AI, Copy.ai, Grammarly\n- Do NOT invent fake tools or fake statistics\n- If using case studies or examples, clearly frame them as hypothetical scenarios using phrases like 'imagine someone like...' or 'let us say you are...' rather than presenting them as real people\n- Avoid generic advice - be specific and actionable\n- Every section must be fully completed\n- End with a strong call to action\n- Add emojis to headings\n- Format: clean HTML with h2, h3, p, ul, li tags\n\nReturn in this EXACT format with no extra text:\nTITLE: [your title here]\nKEYWORD: [one word image search keyword]\nDESCRIPTION: [one sentence meta description]\nCONTENT: [your complete html content here]"
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
