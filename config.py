import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env relative to the config file path and override existing environment variables
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant").strip()
PREPGURU_PASSWORD = os.environ.get("PREPGURU_PASSWORD", "").strip()

# Where the single master PDF is written / regenerated
PDF_PATH = Path(__file__).parent / "interview_qa.pdf"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

LEVELS = ["basic", "intermediate", "advanced"]
