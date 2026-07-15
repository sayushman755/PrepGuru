"""
Turns raw forwarded text into structured fields using Groq, with an active fallback
to the Google Gemini API if Groq fails or hits rate limits.
"""
import json
import time
import datetime
import hashlib
import os
import urllib.request
import urllib.error
from openai import OpenAI
from config import GROQ_API_KEY, GROQ_MODEL
from logger_setup import setup_logger

log = setup_logger("llm_extract")
_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

CACHE_FILE = "groq_cache.json"
DAILY_CAP = 50


# Pure Python Exponential Backoff Retry Decorator
def retry_on_exception(retries=3, backoff_in_seconds=1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries:
                        raise e
                    sleep_time = (backoff_in_seconds * 2 ** attempt)
                    time.sleep(sleep_time)
                    attempt += 1
        return wrapper
    return decorator


def call_gemini_fallback(prompt: str, system_instruction: str) -> str:
    """
    Natively calls Google Gemini 1.5 Flash API as a zero-dependency fallback.
    """
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY is not configured in environment.")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
    headers = {"Content-Type": "application/json"}
    
    body = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "responseMimeType": "application/json" if "JSON" in system_instruction else "text/plain"
        }
    }
    
    req_data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
    
    log.info("Switching to Gemini Fallback API...")
    with urllib.request.urlopen(req, timeout=12) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        try:
            return res_data['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError):
            raise ValueError(f"Unexpected response format from Gemini: {res_data}")


# Local cache operations to control rates and prevent duplicate hits
def _get_cache_hash(text: str) -> str:
    return hashlib.md5(text.strip().encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def _increment_daily_count_and_verify():
    cache = _load_cache()
    today = datetime.date.today().strftime("%Y-%m-%d")
    counts = cache.setdefault("daily_counts", {})
    current = counts.setdefault(today, 0)
    
    if current >= DAILY_CAP:
        raise ValueError(f"Groq API Daily rate limit cap of {DAILY_CAP} calls reached. Try again tomorrow!")
        
    counts[today] = current + 1
    _save_cache(cache)


SYSTEM_PROMPT = """You extract structured interview prep data from raw text.
Respond with ONLY a JSON object, no preamble, no markdown fences, matching this shape:

{
  "question": "the interview question or coding problem description, phrased clearly",
  "answer_summary": "Provide a brief, simplified explanation in easy, conversational language using a real-world analogy. If the input raw text describes a code solution, explain the high-level logic in plain language.",
  "technical_answer": "Provide a granular, formal technical explanation of the solution. If code is present, explain how it works behind the scenes or provide a brief line-by-line explanation of the most important parts.",
  "concept_diagram": "Mermaid.js diagram syntax showing system design flowchart or algorithm logic flow (e.g., recursive calls, loops), else null.",
  "example": "a simple, real-world scenario, code implementation snippet, or concrete design example showing this concept in action.",
  "code_snippet": "the cleaned programming code snippet solving the problem if present in the raw text, else null",
  "programming_language": "the programming language of the code snippet (e.g. Python, JavaScript, C++, Java, Go, SQL) if present, else null",
  "topic": "one short category, e.g. System Design, DSA, Behavioral, SQL, ML, HR",
  "level": "one of: basic, intermediate, advanced - judge from complexity",
  "company": "company name if mentioned, else null",
  "ai_supplemented": true // set to true if the input raw text was thin/generic and you had to generate the analogy or example from your own general knowledge. Set to false if the input raw text already had a detailed analogy or example.
}

If the text doesn't look like interview Q&A content at all, still do your best
to fill the fields from whatever is there."""


@retry_on_exception(retries=3, backoff_in_seconds=2)
def extract_fields(raw_text: str) -> dict:
    # 1. Caching Check
    cache = _load_cache()
    text_hash = _get_cache_hash(raw_text)
    if text_hash in cache:
        return cache[text_hash]

    # 2. Rate Verification
    _increment_daily_count_and_verify()

    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content.strip()
    except Exception as groq_err:
        log.warning(f"Groq Extraction failed: {groq_err}. Trying Gemini Fallback...")
        try:
            content = call_gemini_fallback(raw_text, SYSTEM_PROMPT).strip()
        except Exception as gem_err:
            log.error(f"Gemini Fallback failed: {gem_err}")
            raise ValueError(f"Primary LLM (Groq) failed: {groq_err}. Fallback LLM (Gemini) failed: {gem_err}")

    content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(content)

    level = str(data.get("level") or "").strip().lower()
    if level not in ("basic", "intermediate", "advanced"):
        level = "basic"
    data["level"] = level
    data["ai_supplemented"] = bool(data.get("ai_supplemented", False))

    # Save to Cache
    cache[text_hash] = data
    _save_cache(cache)

    return data


EVAL_SYSTEM_PROMPT = """You are an expert technical interviewer.
Compare the candidate's answer against the reference answer summary for the given question.
Respond with ONLY a JSON object, no preamble, no markdown fences, matching this shape:

{
  "rating": 4,  // an integer from 1 to 5 based on completeness and accuracy of candidate's answer compared to reference answer
  "got_right": "A concise summary of key concepts they correctly identified",
  "missed": "Important details, terminology, or logic from the reference answer they left out",
  "tip": "A quick actionable tip on how to structure or present this answer to impress an interviewer"
}

Be highly direct, constructive, and concise. Avoid wordy introductions."""


@retry_on_exception(retries=3, backoff_in_seconds=2)
def evaluate_answer(question: str, reference_answer: str, candidate_answer: str) -> dict:
    prompt = f"""Question: {question}
Reference Answer Summary: {reference_answer}
Candidate's Attempted Answer: {candidate_answer}"""

    # Rate Verification
    _increment_daily_count_and_verify()

    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": EVAL_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content.strip()
    except Exception as groq_err:
        log.warning(f"Groq Evaluation failed: {groq_err}. Trying Gemini Fallback...")
        try:
            content = call_gemini_fallback(prompt, EVAL_SYSTEM_PROMPT).strip()
        except Exception as gem_err:
            log.error(f"Gemini Evaluation failed: {gem_err}")
            raise ValueError(f"Primary LLM (Groq) failed: {groq_err}. Fallback LLM (Gemini) failed: {gem_err}")

    content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    
    data = json.loads(content)
    try:
        data["rating"] = max(1, min(5, int(data.get("rating", 3))))
    except Exception:
        data["rating"] = 3
    return data


FALLBACK_SYSTEM_PROMPT = """You are an expert technical interviewer.
Based on the query topic, generate a comprehensive, brief interview Q&A study entry.
Respond with ONLY a JSON object, no preamble, no markdown fences, matching this shape:

{
  "question": "A commonly asked technical interview question related to this query",
  "answer_summary": "A brief, simplified explanation in easy, conversational language using a real-world analogy.",
  "technical_answer": "A granular, formal technical explanation of the expected answer containing key industry jargon.",
  "concept_diagram": "If conceptual or architectural, a clean Mermaid.js diagram (e.g. flowchart TD or sequenceDiagram). Do not wrap in markdown syntax. If not conceptual, set to null.",
  "example": "A practical code snippet (python) or system architecture example demonstrating the concept.",
  "topic": "The general category, e.g. System Design, DSA, Behavioral, SQL, ML, HR",
  "level": "one of: basic, intermediate, advanced"
}

Be highly practical, direct, and clear. Avoid wordy introductions."""


@retry_on_exception(retries=3, backoff_in_seconds=2)
def generate_fallback_entry(query_text: str) -> dict:
    # Rate Verification
    _increment_daily_count_and_verify()

    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": FALLBACK_SYSTEM_PROMPT},
                {"role": "user", "content": f"Query Topic: {query_text}"},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content.strip()
    except Exception as groq_err:
        log.warning(f"Groq Fallback Generation failed: {groq_err}. Trying Gemini Fallback...")
        try:
            content = call_gemini_fallback(f"Query Topic: {query_text}", FALLBACK_SYSTEM_PROMPT).strip()
        except Exception as gem_err:
            log.error(f"Gemini Fallback Generation failed: {gem_err}")
            raise ValueError(f"Primary LLM (Groq) failed: {groq_err}. Fallback LLM (Gemini) failed: {gem_err}")

    content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(content)

    level = str(data.get("level") or "").strip().lower()
    if level not in ("basic", "intermediate", "advanced"):
        level = "basic"
    data["level"] = level
    data["ai_supplemented"] = True
    return data


TOPIC_SUMMARIZE_SYSTEM_PROMPT = """You are an expert technical interviewer.
Analyze the following list of interview Q&As saved under this topic.
Synthesize a comprehensive, high-contrast review study sheet.
Return a markdown format document containing:
1. **Recurring Themes**: Key concepts, libraries, or architectures frequently asked.
2. **Interviewer Follow-ups**: Common follow-up questions or scenarios interviewers probe.
3. **Common Pitfalls & Mistakes**: Pitfalls candidates fall into when answering these questions.
4. **Actionable Study Advice**: How to master this topic area.

Be concise, practical, and highly direct."""


@retry_on_exception(retries=3, backoff_in_seconds=2)
def summarize_topic_cluster(topic: str, entries: list) -> str:
    # Rate Verification
    _increment_daily_count_and_verify()

    entries_text = ""
    for idx, e in enumerate(entries, 1):
        entries_text += f"\nEntry {idx}:\nQ: {e.get('question')}\nA: {e.get('answer_summary')}\n"

    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": TOPIC_SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Topic: {topic}\n\nEntries:\n{entries_text}"}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as groq_err:
        log.warning(f"Groq Topic Summarization failed: {groq_err}. Trying Gemini Fallback...")
        try:
            return call_gemini_fallback(f"Topic: {topic}\n\nEntries:\n{entries_text}", TOPIC_SUMMARIZE_SYSTEM_PROMPT).strip()
        except Exception as gem_err:
            log.error(f"Gemini Fallback Topic Summarization failed: {gem_err}")
            raise ValueError(f"Primary LLM (Groq) failed: {groq_err}. Fallback LLM (Gemini) failed: {gem_err}")


CODE_EXPLAIN_SYSTEM_PROMPT = """You are an expert software engineer and technical interviewer.
Analyze the provided code snippet and return a JSON object with this shape (no markdown fences, no preamble):

{
  "summary": "High-level summary of what this code accomplishes and the algorithm/data structure used.",
  "line_by_line": "Detailed line-by-line explanation of how the code works behind the scenes.",
  "time_complexity": "Time complexity notation (e.g. O(n)) and short reason why.",
  "space_complexity": "Space complexity notation (e.g. O(1)) and short reason why.",
  "interview_pitch": "A 1-paragraph explanation on how to explain this solution to an interviewer clearly and confidently."
}"""


@retry_on_exception(retries=3, backoff_in_seconds=2)
def explain_code_snippet(code: str, language: str) -> dict:
    _increment_daily_count_and_verify()
    
    prompt = f"Language: {language}\n\nCode:\n{code}"
    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": CODE_EXPLAIN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        content = response.choices[0].message.content.strip()
    except Exception as groq_err:
        log.warning(f"Groq Code Explanation failed: {groq_err}. Trying Gemini Fallback...")
        try:
            content = call_gemini_fallback(prompt, CODE_EXPLAIN_SYSTEM_PROMPT).strip()
        except Exception as gem_err:
            log.error(f"Gemini Code Explanation failed: {gem_err}")
            raise ValueError(f"Primary LLM (Groq) failed: {groq_err}. Fallback (Gemini) failed: {gem_err}")
            
    content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(content)
