# Interview Q&A system

Capture interview Q&A the moment you see it, and never lose it again.

- **Capture**: forward any LinkedIn post or paste text to your Telegram bot, any time.
- **Auto-structure**: a free LLM call pulls out the question, answer, example, topic, and difficulty level (basic / intermediate / advanced).
- **Store**: everything lands in a free Supabase (Postgres + pgvector) database.
- **Ask**: type a question anytime and get the closest matching answer + example back, via semantic search.
- **Read**: one master PDF (`interview_qa.pdf`), organized into Basic / Intermediate / Advanced sections, rebuilt automatically after every new entry - always current, never duplicated.

## 1. One-time setup

### Supabase (free tier)
1. Create a project at https://supabase.com
2. Open the SQL editor, paste and run the contents of `schema.sql`
3. Go to Project Settings -> API, copy the Project URL and the `anon` key

### Telegram bot (free)
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. `/newbot`, follow the prompts, copy the token it gives you

### Groq (free tier, used only to extract structured fields)
1. Create a key at https://console.groq.com
2. Free tier is generous and plenty for personal note-taking volume

### Install
```bash
python -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# now fill in TELEGRAM_BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEY in .env
```

## 2. Run it

Two separate processes, run them in two terminals:

```bash
# Terminal 1 - listens for your Telegram messages, does the capturing
python capture_bot.py
```

```bash
# Terminal 2 - the search/browse/download web app
streamlit run app.py
```

Now message your Telegram bot with any interview Q&A text - it'll confirm
what it saved, tag its level, and update `interview_qa.pdf` automatically.
Open the Streamlit app any time to ask a question, browse everything, or
download the current PDF.

## Notes
- The PDF is fully regenerated from the database on every new entry - there is
  always exactly one `interview_qa.pdf`, never duplicates.
- Everything here runs on free tiers: Supabase free project, Groq free API,
  Telegram Bot API, and local (free) embeddings via sentence-transformers.
- To swap Groq for another free-tier provider, just change `base_url` and
  `GROQ_MODEL` in `config.py` / `.env` - any OpenAI-compatible API works.
