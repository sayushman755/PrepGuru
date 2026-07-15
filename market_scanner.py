"""
Scheduled / Manual tech market trend scanning job.
Fetches GitHub trending framework repositories and HackerNews headlines,
synthesizes them using Groq AI, and writes to database.
"""
import urllib.request
import xml.etree.ElementTree as ET
import re
import json
import datetime
from openai import OpenAI
from config import GROQ_API_KEY, GROQ_MODEL
from db import save_market_trend

_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

SCANNER_SYSTEM_PROMPT = """You are a technical market research analyst.
Based on the raw text feed of developer news, framework repositories, and trends, synthesize a market trend report.
Respond with ONLY a JSON object, no preamble, no markdown fences, matching this shape:

{
  "trending_skills": ["Skill1", "Skill2", "Skill3", "Skill4", "Skill5"], -- top 5 trending tools, frameworks, or methodologies
  "summary": "A detailed Markdown summary of the trends, explaining what is booming, why it is in demand, citing sources and dates clearly, and outlining key hiring insights.",
  "sources": ["source1.com", "source2.org"] -- domains you found relevant in the feed
}

Be highly detailed, objective, and analytical. Avoid wordy introductions."""


def run_market_scan() -> dict:
    feeds_text = []
    sources = []
    
    # 1. Fetch HackerNews RSS Feed (Tech News)
    try:
        req = urllib.request.Request(
            "https://news.ycombinator.com/rss",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            headlines = []
            for item in root.findall(".//item"):
                title = item.find("title").text
                headlines.append(title)
            feeds_text.append("=== HackerNews Tech Headlines ===\n" + "\n".join(headlines[:25]))
            sources.append("news.ycombinator.com")
    except Exception as e:
        feeds_text.append(f"Failed to fetch HackerNews headlines: {e}")
        
    # 2. Fetch GitHub Trending HTML (Frameworks & Software Booms)
    try:
        req = urllib.request.Request(
            "https://github.com/trending",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8")
            
            # Simple regex extracts of repository tags and descriptions
            repo_matches = re.findall(r'href="/([^"/]+/[^"/]+)"\s+data-hydro-click', html)
            desc_matches = re.findall(r'<p class="col-9 color-fg-muted my-1 pr-4">\s*(.*?)\s*</p>', html, re.DOTALL)
            
            repos = []
            for r, d in zip(repo_matches[:15], desc_matches[:15]):
                d_clean = re.sub(r'\s+', ' ', d).strip()
                repos.append(f"Repo: {r} - Desc: {d_clean}")
                
            feeds_text.append("=== GitHub Trending Repositories ===\n" + "\n".join(repos))
            sources.append("github.com/trending")
    except Exception as e:
        feeds_text.append(f"Failed to fetch GitHub trending repos: {e}")
        
    combined_feed = "\n\n".join(feeds_text)
    
    # 3. Analyze using Groq LLM (with Gemini fallback)
    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SCANNER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Current Date: {datetime.date.today().strftime('%Y-%m-%d')}\n\nFeed Content:\n{combined_feed}"}
            ],
            temperature=0.2
        )
        content = response.choices[0].message.content.strip()
    except Exception as groq_err:
        try:
            from llm_extract import call_gemini_fallback
            content = call_gemini_fallback(
                f"Current Date: {datetime.date.today().strftime('%Y-%m-%d')}\n\nFeed Content:\n{combined_feed}",
                SCANNER_SYSTEM_PROMPT
            ).strip()
        except Exception as gem_err:
            return {
                "trending_skills": [],
                "summary": f"Failed to synthesize market trends. Groq Error: {groq_err}. Gemini Error: {gem_err}",
                "sources": sources
            }
        
    try:
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(content)
        trending_skills = data.get("trending_skills", [])
        summary = data.get("summary", "")
        sources_list = data.get("sources", sources)
        
        # Save to DB
        save_market_trend(trending_skills, summary, sources_list)
        return data
    except Exception as err:
        return {
            "trending_skills": [],
            "summary": f"Failed to synthesize market trends: {err}",
            "sources": sources
        }


if __name__ == "__main__":
    print("Running market scan...")
    result = run_market_scan()
    print("Trending Skills:", result.get("trending_skills"))
    print("Summary Length:", len(result.get("summary", "")))
