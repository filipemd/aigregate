import json
import requests
from typing import Optional
from datetime import datetime
import sys

import feedparser
from bs4 import BeautifulSoup

from pydantic import BaseModel
from google import genai
from google.genai import types

AI_MODEL = "gemma-4-31b-it"

class CuratedArticle(BaseModel):
    title: Optional[str]
    urls: list[str]
    technical_significance: Optional[str] = None
    summary: Optional[str] = None

class CuratedNewsFeed(BaseModel):
    best_articles: list[CuratedArticle]

subreddits = {"programming", "hackernews", "technology", "linux"}

def get_news(subreddit):
    url = f"https://www.reddit.com/r/{subreddit}/top/.rss?t=day"
    headers = {'User-Agent': 'Python/RSS-Reader-Bot 1.0'}
    response = requests.get(url, headers=headers, timeout=10)
    feed = feedparser.parse(response.content)
    result = []

    for entry in feed.entries:
        parser = BeautifulSoup(entry.description, "html.parser")
        links = parser.select("a")
        url = None
        for link in links:
                                                # To prevent links to the comments of the post
            if link.text.strip() == "[link]" and (not link["href"].startswith("/")):
                url = link["href"]
                break
        
        if url is not None:
            result.append({"title": entry.title, "url": url})
            
    return result

def get_article_text(url):
    try:
        # Hope this User-Agent helps in something...
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:149.0) Gecko/20100101 Firefox/149.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 3. Find the article tag
        article = soup.find(['article', 'main']) or soup.find('div', class_='content')
        
        if not article:
            return None
            
        # 4. Extract clean text
        return article.get_text(separator='\n', strip=True)[:15000]
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
        return None

if len(sys.argv) <= 1:
    print(f"{sys.argv[0]} output")
    sys.exit(0)

print("Grabbing news from RSS feeds...")

news = []
for subreddit in subreddits:
    news.extend(get_news(subreddit))

# --- 3. Gemini Prompting ---
prompt = (
"""
You are the Lead Curator for a newsletter targeting programmers, software developers, and deep tech enthusiasts. 

Your mission: Filter a raw feed of articles and select the news that resonates with the developer community. We want a well-rounded mix: from deep technical fascinations and "hacker culture" to broader industry shifts, hardware economics, and internet policies that affect how we build and experience the web.

### SELECTION CRITERIA (The "Developer & Ecosystem Test"):
- INCLUDE - Hacker Culture & Deep Tech:** Clever hacks, reverse engineering, bizarre code edge cases, deep architectural dives, complex security vulnerabilities, and significant open-source developments.
- INCLUDE - Macro-Tech & Policy:** Hardware market trends (e.g., RAM or GPU prices rising/falling), significant internet legislation (e.g., age verification laws, encryption battles, AI regulations), and major infrastructure shifts. If it impacts the tech economy, digital rights, or the hardware we run code on, include it—even if the general public also cares about it.
- EXCLUDE - Superficial consumer tech gadgets (e.g., "New iPhone colors", "Top 10 smartwatches"), things way too technical but not that much interesting, celebrity tech gossip, corporate PR fluff, beginner tutorials, and generic SEO listicles. 

### AGGREGATION (The "Event Orbit"):
- Group all related stories into one "Root Event." 
- If one URL is a mainstream news report and another is a technical deep-dive or GitHub repo on the exact same topic, MERGE THEM into the same event.
- Preserve ALL relevant URLs in the list.

### OUTPUT FORMAT (Strict JSON):
- TECHNICAL SIGNIFICANCE: 1 small concise sentence. Explain exactly why a developer or tech enthusiast would find this interesting, impactful, or clever.
- TITLES & SUMMARIES: Set to null.
- URLS: A unique list of all aggregated links associated with the event.

### RAW DATA:
"""
)

for item in news:
    prompt += f"- {item['title']} (URL: {item['url']})\n"

print("Fetching AI curation...")

# --- 4. Call Gemini with Structured Outputs ---
gemini_client = genai.Client()

# First AI call: Selection
selection_response = gemini_client.models.generate_content(
    model=AI_MODEL,
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=CuratedNewsFeed,
        temperature=0.2
    ),
)

# Parse the selection
selected_data = json.loads(selection_response.text)
selected_articles = selected_data.get("best_articles", [])

# SECOND STAGE: Scrape content only for selected articles
final_prompt = """
You are an expert news curator and executive summarizer. Your objective is to analyze the provided scraped content and distill it into a high-signal briefing of the top 7 most relevant and compelling news stories.

### SYNTHESIS & SELECTION RULES:
1. Select for "The Watercooler Factor": Identify up to 7 stories that are not just factually significant, but inherently compelling, surprising, or high-consequence. Prioritize stories that provoke curiosity or have a "did you hear about this?" quality.
2. The "So What?" Filter: Prioritize news with high human impact. While technical milestones are important, favor stories that change how a non-developer perceives the world or their daily life.
3. Balance Novelty & Fact: If a story is purely technical (e.g., a routine version update) but lacks broader implications, skip it in favor of something more unique or thought-provoking.
4. Cohesion: Group multiple URLs covering the same event or similar ones into a single cohesive topic.
5. Output Limit: Provide a maximum of 7 entries. If the source material contains fewer than 7 high-quality, newsworthy items, only output the ones that meet this standard.

### FORMATTING RULES (For each entry):
- Title: Write a new, ultra-concise, and punchy title. Do not copy the original headlines.
- Summary: Write a dense, factual summary. Start with the most impactful or surprising consequence ("the meat"). Focus on why it matters before how it works.
- Tone Constraint: Ruthlessly eliminate all marketing fluff, corporate PR jargon, clickbait, and editorial bias. Keep the text strictly objective yet engaging.

### INPUT ARTICLES:
"""

print("Scraping content from articles...")

successfully_scraped = False

for article in selected_articles:
    for url in article["urls"]:
        content = get_article_text(url)

        if content:
            # Append content to prompt
            final_prompt += f"URL: {url}\nCONTENT:\n{content}\n"
            successfully_scraped = True
    final_prompt += "="*64 + "\n"

print("Writing summaries of the articles...")

# Only proceed if we actually have text to summarize
if successfully_scraped:
    final_response = gemini_client.models.generate_content(
        model=AI_MODEL,
        contents=final_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CuratedNewsFeed,
            temperature=0.2
        ),
    )
    
    # Load final curated list
    final_news = json.loads(final_response.text).get("best_articles", [])
else:
    final_news = []
    print("No articles could be scraped.")

print(f"Writing to {sys.argv[1]}...")
with open(sys.argv[1], "w") as output:
    # Title
    now = datetime.now()
    output.write(f"""+++
title = "{now.strftime("%B %d, %Y")} tech news: {"; ".join(article["title"] for article in final_news)}."
date = {now.date().isoformat()}
draft = false
+++

""")

    for article in final_news:
        output.write(f"## {article["title"]}\n\n")
        output.write(f"{article["summary"]}\n\n")
        for url in article["urls"]:
            output.write(f"- [{url}]({url})\n")
        output.write("\n")