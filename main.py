import anthropic
import requests
import datetime
import os

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
BLOGGER_CLIENT_ID = os.environ.get("BLOGGER_CLIENT_ID")
BLOGGER_CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET")
BLOGGER_REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN")
BLOG_ID = os.environ.get("BLOG_ID")

def get_access_token():
    response = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": BLOGGER_CLIENT_ID,
        "client_secret": BLOGGER_CLIENT_SECRET,
        "refresh_token": BLOGGER_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    })
    return response.json()["access_token"]

def generate_post():
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    today = datetime.datetime.now().strftime("%B %d, %Y")
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""Write a blog post for today ({today}) about AI tools or tips to make or save money.
            
Requirements:
- Title: catchy and SEO friendly
- Length: 800-1000 words
- Tone: friendly, practical, actionable
- Include: 3 specific tips or tools
- End with a call to action
- Format: HTML with proper h2, h3, p tags

Return in this exact format:
TITLE: [your title here]
CONTENT: [your html content here]"""
        }]
    )
    response = message.content[0].text
    title = response.split("TITLE:")[1].split("CONTENT:")[0].strip()
    content = response.split("CONTENT:")[1].strip()
    return title, content

def post_to_blogger(title, content):
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "title": title,
        "content": content
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
