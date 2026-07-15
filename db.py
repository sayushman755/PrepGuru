import datetime
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY
from logger_setup import setup_logger

log = setup_logger("db")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in configuration. Please check your .env file.")

_client = create_client(SUPABASE_URL, SUPABASE_KEY)


def insert_entry(fields: dict, raw_text: str, source_url: str | None, embedding: list[float], source_type: str = "captured", ai_supplemented: bool = False) -> dict:
    # Idempotency Check: if exact question or raw text exists, skip insert and return existing
    try:
        q = fields.get("question")
        if q and q.strip():
            existing = _client.table("qa_entries").select("*").eq("question", q.strip()).execute()
            if existing.data:
                return existing.data[0]
    except Exception:
        pass

    row = {
        "raw_text": raw_text,
        "question": fields.get("question"),
        "answer_summary": fields.get("answer_summary"),
        "example": fields.get("example"),
        "topic": fields.get("topic"),
        "level": fields.get("level"),
        "company": fields.get("company"),
        "source_url": source_url,
        "embedding": embedding,
        "source_type": source_type,
        "ai_supplemented": ai_supplemented,
        "technical_answer": fields.get("technical_answer"),
        "concept_diagram": fields.get("concept_diagram"),
        "code_snippet": fields.get("code_snippet"),
        "programming_language": fields.get("programming_language")
    }
    result = _client.table("qa_entries").insert(row).execute()
    return result.data[0]


def check_and_merge_entry(fields: dict, new_raw_text: str, source_url: str | None, embedding: list[float], threshold: float = 0.90) -> dict | None:
    """
    Checks if an entry with vector similarity > threshold exists.
    If yes, merges their raw text and example fields, and updates Supabase.
    """
    try:
        top_matches = semantic_search(embedding, match_count=1)
        if top_matches and top_matches[0].get("similarity", 0) > threshold:
            match = top_matches[0]
            merged_raw = (match.get("raw_text") or "") + "\n\n---\n[Merged Raw Entry]:\n" + new_raw_text
            merged_example = match.get("example") or ""
            new_example = fields.get("example")
            if new_example and new_example not in merged_example:
                merged_example += "\n\n# Alternative Example:\n" + new_example
            
            update_row = {
                "raw_text": merged_raw,
                "example": merged_example,
            }
            if source_url and source_url not in (match.get("source_url") or ""):
                update_row["source_url"] = ((match.get("source_url") or "") + "; " + source_url).strip("; ")
                
            result = _client.table("qa_entries").update(update_row).eq("id", match["id"]).execute()
            return result.data[0]
    except Exception:
        pass
    return None


def fetch_all_grouped_by_level() -> dict:
    """Returns {'basic': [...], 'intermediate': [...], 'advanced': [...]}, each
    list sorted by topic then newest first - used to rebuild the master PDF."""
    result = (
        _client.table("qa_entries")
        .select("question,answer_summary,technical_answer,example,topic,level,company,source_url,created_at")
        .order("topic")
        .order("created_at", desc=True)
        .execute()
    )
    grouped = {"basic": [], "intermediate": [], "advanced": []}
    for row in result.data:
        grouped.setdefault(row["level"], []).append(row)
    return grouped


def semantic_search(query_embedding: list[float], match_count: int = 5) -> list[dict]:
    result = _client.rpc(
        "match_qa_entries",
        {"query_embedding": query_embedding, "match_count": match_count},
    ).execute()
    return result.data


def fetch_all(level: str | None = None, topic: str | None = None) -> list[dict]:
    query = _client.table("qa_entries").select("*").order("created_at", desc=True)
    if level:
        query = query.eq("level", level)
    if topic:
        query = query.eq("topic", topic)
    return query.execute().data


def save_attempt(
    entry_id: str,
    user_answer: str,
    rating: int,
    feedback_right: str,
    feedback_missed: str,
    feedback_tip: str
) -> dict:
    row = {
        "entry_id": entry_id,
        "user_answer": user_answer,
        "rating": rating,
        "feedback_right": feedback_right,
        "feedback_missed": feedback_missed,
        "feedback_tip": feedback_tip
    }
    result = _client.table("qa_attempts").insert(row).execute()
    return result.data[0]


def fetch_attempts_history() -> list[dict]:
    try:
        result = (
            _client.table("qa_attempts")
            .select("id, attempted_at, user_answer, rating, feedback_right, feedback_missed, feedback_tip, entry_id, qa_entries(question, topic)")
            .order("attempted_at", desc=True)
            .execute()
        )
        return result.data
    except Exception:
        # Safe fallback if table doesn't exist yet
        return None


def clear_attempts_history():
    try:
        # Delete all attempts where entry_id is not null (which is all of them)
        _client.table("qa_attempts").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    except Exception:
        pass


def update_last_reviewed(entry_id: str):
    """Updates last_reviewed timestamp and increments review_count."""
    try:
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Fetch current review_count
        entry = _client.table("qa_entries").select("review_count").eq("id", entry_id).execute()
        current_count = 0
        if entry.data:
            current_count = entry.data[0].get("review_count") or 0
        
        _client.table("qa_entries").update({
            "last_reviewed": now_str,
            "review_count": current_count + 1
        }).eq("id", entry_id).execute()
    except Exception:
        pass


def hybrid_search(query_text: str, query_embedding: list[float], match_count: int = 5) -> list[dict]:
    """Combines semantic search with keyword filtering."""
    # 1. Semantic Search
    semantic_results = semantic_search(query_embedding, match_count=match_count)
    
    # 2. Keyword Filter
    keyword_results = []
    try:
        words = [w.strip().lower() for w in query_text.split() if w.strip()]
        if words:
            # Query all records and filter locally
            all_records = _client.table("qa_entries").select("*").execute().data
            for r in all_records:
                text_blob = f"{r.get('question') or ''} {r.get('answer_summary') or ''} {r.get('topic') or ''} {r.get('company') or ''}".lower()
                if all(w in text_blob for w in words):
                    r["similarity"] = 0.85  # Default keyword match score
                    keyword_results.append(r)
    except Exception:
        pass
        
    # Merge
    merged = {}
    for r in semantic_results:
        merged[r["id"]] = r
    for r in keyword_results:
        if r["id"] not in merged:
            merged[r["id"]] = r
        else:
            # Boost score slightly if matched by both
            merged[r["id"]]["similarity"] = min(1.0, merged[r["id"]].get("similarity", 0) + 0.1)
            
    # Sort
    sorted_results = sorted(merged.values(), key=lambda x: x.get("similarity", 0), reverse=True)
    return sorted_results[:match_count]


def add_to_failed_queue(raw_text: str, error_message: str) -> dict:
    try:
        row = {
            "raw_text": raw_text,
            "error_message": error_message
        }
        res = _client.table("qa_failed_queue").insert(row).execute()
        return res.data[0]
    except Exception:
        return {}


def fetch_failed_queue() -> list[dict]:
    try:
        res = _client.table("qa_failed_queue").select("*").order("created_at", desc=True).execute()
        return res.data
    except Exception:
        return []


def delete_from_failed_queue(queue_id: str):
    try:
        _client.table("qa_failed_queue").delete().eq("id", queue_id).execute()
    except Exception:
        pass


def save_market_trend(trending_skills: list, summary: str, sources: list) -> dict:
    try:
        row = {
            "trending_skills": trending_skills,
            "summary": summary,
            "sources": sources
        }
        res = _client.table("qa_market_trends").insert(row).execute()
        return res.data[0]
    except Exception as e:
        log.exception(f"Database insertion failed for qa_market_trends: {e}")
        return {}


def fetch_latest_market_trends() -> dict | None:
    try:
        res = _client.table("qa_market_trends").select("*").order("scanned_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


def save_topic_summary(topic: str, summary: str) -> dict:
    try:
        row = {
            "topic": topic,
            "summary": summary,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        res = _client.table("qa_topic_summaries").upsert(row).execute()
        return res.data[0]
    except Exception:
        return {}


def fetch_topic_summary(topic: str) -> dict | None:
    try:
        res = _client.table("qa_topic_summaries").select("*").eq("topic", topic).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


def register_chat_id(chat_id: str) -> dict:
    try:
        row = {
            "chat_id": str(chat_id)
        }
        res = _client.table("qa_user_chats").upsert(row).execute()
        return res.data[0]
    except Exception:
        return {}


def fetch_all_chat_ids() -> list:
    try:
        res = _client.table("qa_user_chats").select("chat_id").execute()
        return [r["chat_id"] for r in res.data]
    except Exception:
        return []


def update_entry_confidence(entry_id: str, rating: int):
    try:
        _client.table("qa_entries").update({"confidence_rating": rating}).eq("id", entry_id).execute()
    except Exception:
        pass


def add_pending_statement(title: str, description: str, source_url: str, difficulty: str, target_date: str, programming_language: str, topic: str) -> dict:
    try:
        row = {
            "title": title,
            "description": description,
            "source_url": source_url,
            "difficulty": difficulty,
            "target_date": target_date if target_date else None,
            "programming_language": programming_language,
            "topic": topic,
            "is_solved": False
        }
        res = _client.table("pending_statements").insert(row).execute()
        return res.data[0]
    except Exception:
        return {}


def fetch_pending_statements(is_solved: bool = None) -> list:
    try:
        query = _client.table("pending_statements").select("*")
        if is_solved is not None:
            query = query.eq("is_solved", is_solved)
        res = query.order("created_at", desc=True).execute()
        return res.data
    except Exception:
        return []


def mark_statement_solved(statement_id: str):
    try:
        _client.table("pending_statements").update({"is_solved": True}).eq("id", statement_id).execute()
    except Exception:
        pass


def delete_pending_statement(statement_id: str):
    try:
        _client.table("pending_statements").delete().eq("id", statement_id).execute()
    except Exception:
        pass


def add_knowledge_note(title: str, category: str, tags: list, content: str, code_snippet: str, embedding: list) -> dict:
    try:
        row = {
            "title": title,
            "category": category,
            "tags": tags,
            "content": content,
            "code_snippet": code_snippet,
            "embedding": embedding
        }
        res = _client.table("knowledge_notes").insert(row).execute()
        return res.data[0]
    except Exception:
        return {}


def fetch_knowledge_notes(category: str = None) -> list:
    try:
        query = _client.table("knowledge_notes").select("*")
        if category:
            query = query.eq("category", category)
        res = query.order("created_at", desc=True).execute()
        return res.data
    except Exception:
        return []


def search_knowledge_notes(query_embedding: list, match_count: int = 5) -> list:
    try:
        res = _client.rpc(
            "match_knowledge_notes",
            {"query_embedding": query_embedding, "match_count": match_count}
        ).execute()
        return res.data
    except Exception:
        try:
            all_notes = fetch_knowledge_notes()
            return all_notes[:match_count]
        except Exception:
            return []


def delete_knowledge_note(note_id: str):
    try:
        _client.table("knowledge_notes").delete().eq("id", note_id).execute()
    except Exception:
        pass


def log_daily_activity():
    try:
        today = datetime.date.today().isoformat()
        existing = _client.table("user_activity_log").select("*").eq("activity_date", today).execute()
        if existing.data:
            current_count = existing.data[0].get("solved_count") or 0
            _client.table("user_activity_log").update({"solved_count": current_count + 1}).eq("id", existing.data[0]["id"]).execute()
        else:
            _client.table("user_activity_log").insert({"activity_date": today, "solved_count": 1}).execute()
    except Exception:
        pass


def fetch_activity_logs() -> list:
    try:
        res = _client.table("user_activity_log").select("*").order("activity_date", desc=False).execute()
        return res.data
    except Exception:
        return []


def restore_database_from_backup(backup_list: list) -> tuple:
    """
    Restores database entries from a backup JSON list.
    Skips duplicate questions to prevent collision.
    Returns (restored_count, skipped_count).
    """
    restored = 0
    skipped = 0
    for item in backup_list:
        q = item.get("question")
        if not q:
            continue
        try:
            # Check if question exists
            existing = _client.table("qa_entries").select("id").eq("question", q).execute()
            if existing.data:
                skipped += 1
                continue
            
            row = {
                "raw_text": item.get("raw_text") or f"Question: {q} Answer: {item.get('answer_summary')}",
                "question": q,
                "answer_summary": item.get("answer_summary"),
                "technical_answer": item.get("technical_answer"),
                "concept_diagram": item.get("concept_diagram"),
                "example": item.get("example"),
                "code_snippet": item.get("code_snippet"),
                "programming_language": item.get("programming_language"),
                "topic": item.get("topic", "General"),
                "level": item.get("level", "basic"),
                "company": item.get("company"),
                "source_url": item.get("source_url"),
                "source_type": item.get("source_type") or "captured",
                "ai_supplemented": bool(item.get("ai_supplemented", False)),
                "confidence_rating": item.get("confidence_rating") or 3,
                "review_count": item.get("review_count") or 0
            }
            
            # Recalculate embedding to keep vectors clean and up-to-date
            from embed import embed_text
            row["embedding"] = embed_text(f"{row['question']} {row['answer_summary']}")
            
            _client.table("qa_entries").insert(row).execute()
            restored += 1
        except Exception:
            skipped += 1
    return restored, skipped


def check_db_tables() -> list[str]:
    """Checks which tables are missing from Supabase. Returns list of missing table names."""
    required = [
        "qa_entries",
        "qa_attempts",
        "qa_failed_queue",
        "qa_market_trends",
        "qa_topic_summaries",
        "qa_user_chats",
        "pending_statements",
        "knowledge_notes",
        "user_activity_log"
    ]
    missing = []
    for t in required:
        try:
            _client.table(t).select("count", count="exact").limit(1).execute()
        except Exception as e:
            log.warning(f"Table validation check failed for '{t}': {e}")
            missing.append(t)
    return missing

