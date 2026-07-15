# Interview Q&A system (PrepGuru)

Capture, store, and intelligently search interview questions & answers. The UI has been revamped with a premium dark‑theme, left‑side navigation, a database health banner, and proactive AI‑generated study cards.

---

## ✨ New features
- **Left‑sidebar navigation** – instantly switch between Code Journal, Knowledge Vault, Spaced Revision, Streaks & Metrics, Market Trends, and Ingest & Backups.
- **Database health banner** – warns if any Supabase tables are missing.
- **Proactive AI Study‑Card Generator** – when a search returns no local match, click the button to let the AI create a new flash‑card.
- **Premium dark theme** – modern gradient buttons, glass‑morphism containers, and high‑contrast text.

---

## 🚀 Live demo
[https://prepguru-bkaqvhx83kwbyjzwkuhnhj.streamlit.app](https://prepguru-bkaqvhx83kwbyjzwkuhnhj.streamlit.app)

---

## 1️⃣ One‑time setup

### Supabase (free tier)
1. Create a project at https://supabase.com.
2. Open the SQL editor, paste and run the contents of `schema.sql`.
3. In **Project Settings → API**, copy the Project URL and the `anon` key.

### Telegram bot (free)
1. Message [@BotFather](https://t.me/BotFather) on Telegram.
2. `/newbot`, follow the prompts, and copy the token.

### Groq (free tier, used for LLM extraction)
1. Create a key at https://console.groq.com.

### Install dependencies
```bash
python -m venv venv
venv\Scripts\activate   # on Unix/macOS: source venv/bin/activate
pip install -r requirements.txt
```

Copy the example environment file and fill in your secrets:
```bash
cp .env.example .env
# Edit .env with TELEGRAM_BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEY
```

---

## 2️⃣ Run the system
Open two terminals:
```bash
# Terminal 1 – Telegram capture bot
python capture_bot.py
```
```bash
# Terminal 2 – Streamlit UI
streamlit run app.py
```

Now you can:
- Message the Telegram bot with any interview Q&A text. The bot extracts structured fields and stores them in Supabase.
- Visit the Streamlit app to ask questions, browse your knowledge base, or download the generated PDF.

---

## 3️⃣ Using the UI
- **Search** – enter a query; if no local match is found, click **🤖 Generate a new AI study card**.
- **Sidebar** – select any section to view / add entries, view analytics, or run market‑trend scans.
- **Backup & Restore** – export your database to a JSON file or import a previous backup.

---

## 📚 Notes
- The PDF (`interview_qa.pdf`) is regenerated from the database on every new entry, guaranteeing a single up‑to‑date file.
- All services run on free tiers: Supabase, Groq, Telegram Bot API, and local embeddings via `sentence‑transformers`.
- You can replace Groq with any OpenAI‑compatible API by updating `config.py` / `.env`.

---

## 🛠️ Development
- Run `pytest` (if tests are added) to ensure core functionality.
- For a containerised deployment, see `Dockerfile` – it builds a lightweight image ready for Render, Railway, Azure, etc.

---

*Generated on 2026‑07‑15*

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
