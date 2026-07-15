import streamlit as st
import pandas as pd
import random
import json
import datetime
import re
from db import (
    fetch_all,
    insert_entry,
    check_and_merge_entry,
    semantic_search,
    hybrid_search,
    save_attempt,
    fetch_attempts_history,
    clear_attempts_history,
    update_last_reviewed,
    update_entry_confidence,
    restore_database_from_backup,
    add_pending_statement,
    fetch_pending_statements,
    mark_statement_solved,
    delete_pending_statement,
    add_knowledge_note,
    fetch_knowledge_notes,
    delete_knowledge_note,
    log_daily_activity,
    fetch_activity_logs
)
from llm_extract import (
    extract_fields,
    evaluate_answer,
    generate_fallback_entry,
    summarize_topic_cluster,
    explain_code_snippet
)
from config import PREPGURU_PASSWORD
from pdf_generator import regenerate_pdf
from logger_setup import setup_logger

log = setup_logger("app")

# Page Configuration
st.set_page_config(
    page_title="PrepGuru — Personal Coding Journal & Interview Coach",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Password authentication gate
if PREPGURU_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        
    if not st.session_state.authenticated:
        st.markdown("<div style='max-width:400px; margin:80px auto; padding:30px; background:rgba(30,41,59,0.45); border:1px solid rgba(99,102,241,0.2); border-radius:16px; text-align:center;'>", unsafe_allow_html=True)
        st.markdown("<h2 style='color:#fbbf24; margin-bottom:12px;'>🎓 PrepGuru Gate</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Enter Dashboard Security Password:", type="password")
        if st.button("Unlock Dashboard", use_container_width=True):
            if pwd.strip() == PREPGURU_PASSWORD:
                st.session_state.authenticated = True
                st.success("Access unlocked!")
                st.rerun()
            else:
                st.error("Incorrect password!")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

# Custom Premium CSS overrides
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main {
        background: radial-gradient(circle at 10% 20%, rgba(15, 23, 42, 1) 0%, rgba(9, 15, 29, 1) 90%);
        color: #f8fafc;
    }

    /* Force all form labels to be highly visible and bold */
    label, [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p, .stWidgetLabel, .stWidgetLabel p {
        color: #e2e8f0 !important;
        font-weight: 600 !important;
        font-size: 14.5px !important;
        letter-spacing: 0.02em !important;
    }

    /* Style text input fields and text areas for visibility */
    input, textarea, [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
        color: #ffffff !important;
        background-color: #1e293b !important;
        border: 1px solid rgba(99, 102, 241, 0.4) !important;
        border-radius: 10px !important;
        padding: 8px 12px !important;
    }
    input:focus, textarea:focus {
        border-color: #fbbf24 !important;
        box-shadow: 0 0 0 1px #fbbf24 !important;
    }

    /* Style selectboxes and option dropdowns */
    div[data-baseweb="select"] {
        background-color: #1e293b !important;
        border: 1px solid rgba(99, 102, 241, 0.4) !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="select"] div {
        color: #ffffff !important;
    }
    div[role="listbox"] {
        background-color: #1e293b !important;
        color: #ffffff !important;
    }

    /* Beautiful Premium Tab Styles */
    button[data-baseweb="tab"] {
        background-color: transparent !important;
        color: #94a3b8 !important;
        border: none !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        padding: 10px 16px !important;
        transition: all 0.25s ease !important;
    }
    button[data-baseweb="tab"]:hover {
        color: #ffffff !important;
        background-color: rgba(255, 255, 255, 0.03) !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #fbbf24 !important;
        font-weight: 700 !important;
        border-bottom: 2px solid #fbbf24 !important;
    }

    /* Premium Glassmorphic Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 10px 24px !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4) !important;
        transition: all 0.3s ease !important;
        letter-spacing: 0.03em !important;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%) !important;
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6) !important;
        transform: translateY(-2px) !important;
    }

    /* Premium Download Buttons */
    .stDownloadButton>button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 10px 24px !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 14px rgba(16, 185, 129, 0.4) !important;
        transition: all 0.3s ease !important;
        letter-spacing: 0.03em !important;
    }
    .stDownloadButton>button:hover {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.6) !important;
        transform: translateY(-2px) !important;
    }

    /* Sidebar aesthetics */
    [data-testid="stSidebar"] {
        background-color: #0b0f19 !important;
        border-right: 1px solid rgba(99, 102, 241, 0.15) !important;
    }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
        color: #e2e8f0 !important;
    }

    /* Metrics Flex wrapper for mobile */
    .metrics-container {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        margin-bottom: 24px;
    }
    
    .metric-card {
        flex: 1;
        min-width: 140px;
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);
        backdrop-filter: blur(10px);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-3px);
        border-color: rgba(99, 102, 241, 0.5);
    }
    
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #818cf8;
        margin-top: 4px;
    }
    
    .metric-label {
        font-size: 12px;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Streak Heatmap */
    .heatmap-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        max-width: 320px;
        margin: 10px auto;
    }
    
    .heatmap-cell {
        width: 18px;
        height: 18px;
        border-radius: 4px;
        transition: transform 0.1s ease;
    }
    
    .heatmap-cell:hover {
        transform: scale(1.15);
    }
    
    /* Tags and Badges */
    .badge-topic {
        background: rgba(99, 102, 241, 0.2);
        color: #a5b4fc;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        border: 1px solid rgba(99, 102, 241, 0.3);
    }
    
    .badge-level-basic {
        background: rgba(34, 197, 94, 0.2);
        color: #86efac;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    
    .badge-level-intermediate {
        background: rgba(245, 158, 11, 0.2);
        color: #fde047;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    
    .badge-level-advanced {
        background: rgba(239, 68, 68, 0.2);
        color: #fca5a5;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }

    /* Flashcard Style */
    .flashcard {
        background: rgba(30, 41, 59, 0.55);
        border: 1px solid rgba(251, 191, 36, 0.25);
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 16px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        transition: all 0.25s ease;
    }
    
    .flashcard:hover {
        border-color: rgba(251, 191, 36, 0.5);
        box-shadow: 0 8px 32px rgba(251, 191, 36, 0.15);
    }
    
    /* Code styling */
    pre {
        background: #0f172a !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 8px !important;
    }
    
    /* Expanders styling */
    [data-testid="stExpander"] {
        background: rgba(30, 41, 59, 0.45) !important;
        border: 1px solid rgba(99, 102, 241, 0.25) !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2) !important;
        margin-bottom: 12px !important;
    }
    [data-testid="stExpander"] summary p {
        color: #fbbf24 !important;
        font-weight: 600 !important;
        font-size: 15px !important;
    }
    [data-testid="stExpander"] p, [data-testid="stExpander"] li {
        color: #f1f5f9 !important;
    }
</style>
""", unsafe_allow_html=True)

# Session state initialization
if 'llm_action_count' not in st.session_state:
    st.session_state.llm_action_count = 0

def has_reached_rate_limit() -> bool:
    return st.session_state.llm_action_count >= 20

def increment_llm_action():
    st.session_state.llm_action_count += 1

def render_mermaid(diagram_code: str, chart_id: str):
    clean_code = diagram_code.replace("\n", " ")
    clean_code = re.sub(r'\s+', ' ', clean_code).strip()
    html = f"""
    <div class="mermaid" id="{chart_id}" style="background: rgba(15,23,42,0.6); padding:10px; border-radius:8px; border:1px solid rgba(255,255,255,0.05); margin: 8px 0;">
    {clean_code}
    </div>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
    </script>
    """
    st.components.v1.html(html, height=260, scrolling=True)

# Fetch baseline data
all_entries = fetch_all()
pending_statements = fetch_pending_statements(is_solved=False)
knowledge_notes = fetch_knowledge_notes()
activity_logs = fetch_activity_logs()

# Header Logo Title block
st.markdown("""
<div style="text-align: center; padding: 10px 0 20px 0;">
    <h1 style="font-size: 52px; font-weight: 800; background: linear-gradient(to right, #818cf8, #fbbf24); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0;">PrepGuru</h1>
    <p style="font-size:16px; color:#94a3b8; margin-top:2px;">Consolidated Coding Journal, Spaced Revision, & AI Interview Coach</p>
</div>
""", unsafe_allow_html=True)

# Check database health status
if "missing_tables" not in st.session_state:
    with st.spinner("Checking database schema status..."):
        try:
            from db import check_db_tables
            st.session_state.missing_tables = check_db_tables()
        except Exception:
            st.session_state.missing_tables = []

if st.session_state.missing_tables:
    st.warning(
        f"⚠️ **Supabase Schema Setup Incomplete**: The following database tables are missing in your project: "
        f"`{', '.join(st.session_state.missing_tables)}`. "
        f"Please copy the SQL statements from your `schema.sql` file and execute them in the "
        f"[Supabase SQL Editor](https://supabase.com) to restore full feature capabilities."
    )

# Sidebar Navigation setup
menu_options = [
    "🔍 Unified Search",
    "💻 Code Journal",
    "📓 Knowledge Vault",
    "⚡ Spaced Revision",
    "📈 Streaks & Metrics",
    "📊 Market Trends",
    "📥 Ingest & Backups"
]

if "current_menu" not in st.session_state:
    st.session_state.current_menu = menu_options[0]

def on_menu_change():
    st.session_state.current_menu = st.session_state.sidebar_menu

# PrepGuru Panel Sidebar Navigation
with st.sidebar:
    st.markdown("### 🎓 Navigation")
    menu = st.radio(
        "Go to section:",
        menu_options,
        index=menu_options.index(st.session_state.current_menu) if st.session_state.current_menu in menu_options else 0,
        key="sidebar_menu",
        on_change=on_menu_change
    )
    st.session_state.current_menu = menu

# Section 1: Unified Semantic Search across everything
if st.session_state.current_menu == "🔍 Unified Search":
    st.markdown("<p style='color:#94a3b8;'>Search semantically across all Q&A prep sheets, coding logs, and dev notebook notes.</p>", unsafe_allow_html=True)
    
    search_scope = st.radio("Search Scope", ["All Content", "Interview Q&As Only", "Knowledge Notes Only"], horizontal=True)
    query = st.text_input("What concept, problem, or code snippet are you looking for?", placeholder="e.g. DFS recursion space complexity")
    
    if query:
        if has_reached_rate_limit():
            st.error("⚠️ Session limit reached.")
        else:
            with st.spinner("Executing vector search..."):
                query_emb = []
                try:
                    from embed import embed_text
                    query_emb = embed_text(query)
                except Exception:
                    pass
                
            st.markdown("### 🎯 Search Matches")
            
            # 1. Search Q&As and Code journal
            if search_scope in ("All Content", "Interview Q&As Only"):
                qa_matches = hybrid_search(query, query_emb, match_count=4) if query_emb else []
                if qa_matches:
                    st.markdown("#### 📚 Study Cards & Solved Problems")
                    for match in qa_matches:
                        with st.expander(f"Q: {match.get('question')} (Topic: {match.get('topic')} | Confidence: {match.get('confidence_rating') or 3}/5 ⭐)"):
                            col_c1, col_c2 = st.columns([2, 1])
                            with col_c1:
                                st.markdown(f"**Analogy Explainer:**\n{match.get('answer_summary')}")
                                if match.get("technical_answer"):
                                    st.markdown(f"**Technical Explanation:**\n{match.get('technical_answer')}")
                                if match.get("example"):
                                    st.markdown(f"**Example / Scenario:**\n{match.get('example')}")
                            with col_c2:
                                if match.get("programming_language") or match.get("code_snippet"):
                                    st.markdown(f"**Language: `{match.get('programming_language', 'Generic')}`**")
                                    if match.get("code_snippet"):
                                        st.code(match["code_snippet"], language=str(match.get("programming_language") or "python").lower())
                                if match.get("concept_diagram"):
                                    st.markdown("**Logic Flow:**")
                                    render_mermaid(match["concept_diagram"], f"search_diag_{match['id']}")
            
            # 2. Search Knowledge Notebook
            if search_scope in ("All Content", "Knowledge Notes Only"):
                note_matches = [n for n in knowledge_notes if query.lower() in n['title'].lower() or query.lower() in n['content'].lower()]
                if note_matches:
                    st.markdown("#### 📓 Developer Vault Notes")
                    for note in note_matches[:4]:
                        with st.expander(f"Note: {note['title']} ({note.get('category', 'General')})"):
                            st.markdown(note['content'])
                            if note.get("code_snippet"):
                                st.code(note["code_snippet"], language="python")
                            if note.get("tags"):
                                st.markdown(" ".join([f"`#{t}`" for t in note["tags"]]))            # Proactive AI Search Card Generator
            qa_count = len(qa_matches) if 'qa_matches' in locals() else 0
            note_count = len(note_matches) if 'note_matches' in locals() else 0
            
            if qa_count == 0 and note_count == 0:
                st.info("🔍 No direct matches found in your local repository.")
                if st.button("🤖 Generate a new AI study card on this topic & save it", use_container_width=True):
                    with st.spinner("AI Coach is generating study card..."):
                        try:
                            data = generate_fallback_entry(query)
                            from embed import embed_text
                            emb = embed_text(f"{data['question']} {data['answer_summary']}")
                            from db import insert_entry, log_daily_activity
                            insert_entry(data, f"Generated for topic: {query}", None, emb, source_type="ai_generated", ai_supplemented=True)
                            log_daily_activity()
                            st.success(f"🎉 Successfully generated and saved: {data['question']}")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Failed to generate study card: {ex}")

# Section 2: Code Journal (from CodeVault)
elif st.session_state.current_menu == "💻 Code Journal":
    st.markdown("### 💻 Dev Code Journal & Pending Store")
    
    sub_journal = st.radio("Journal Mode", ["Solved Problems Log", "Planned Problems Planner"], horizontal=True)
    
    if sub_journal == "Solved Problems Log":
        col_j1, col_j2 = st.columns([1, 2])
        
        with col_j1:
            st.markdown("#### ➕ Log a Solved Problem")
            
            prefill_title = st.session_state.get("plan_prefill_title", "")
            prefill_lang = st.session_state.get("plan_prefill_lang", "Python")
            prefill_topic = st.session_state.get("plan_prefill_topic", "DSA")
            prefill_diff = st.session_state.get("plan_prefill_diff", "intermediate").lower()
            
            p_title = st.text_input("Problem Title", value=prefill_title)
            p_lang = st.selectbox("Programming Language", ["Python", "JavaScript", "C++", "Java", "Go", "SQL", "Rust"], index=["Python", "JavaScript", "C++", "Java", "Go", "SQL", "Rust"].index(prefill_lang) if prefill_lang in ["Python", "JavaScript", "C++", "Java", "Go", "SQL", "Rust"] else 0)
            p_topic = st.text_input("Topic Category", value=prefill_topic)
            p_diff = st.selectbox("Complexity Level", ["basic", "intermediate", "advanced"], index=["basic", "intermediate", "advanced"].index(prefill_diff) if prefill_diff in ["basic", "intermediate", "advanced"] else 1)
            p_comp = st.text_input("Company Tag (Optional)", placeholder="e.g. Meta")
            p_desc = st.text_area("Problem Description / Prompt")
            p_code = st.text_area("Your Working Solution Code (Syntax-highlighted)", height=150)
            
            if st.button("💾 Save Code Journal Entry", use_container_width=True):
                if not p_title.strip() or not p_code.strip():
                    st.warning("Title and Solution Code are required!")
                elif has_reached_rate_limit():
                    st.error("⚠️ Session limit reached.")
                else:
                    increment_llm_action()
                    with st.spinner("AI is analyzing code complexities and line-by-line summaries..."):
                        try:
                            analysis = explain_code_snippet(p_code, p_lang)
                            
                            from embed import embed_text
                            emb = embed_text(f"{p_title} {analysis.get('summary', '')}")
                            
                            fields = {
                                "question": p_title,
                                "answer_summary": analysis.get("summary", ""),
                                "technical_answer": f"Line-By-Line Details:\n{analysis.get('line_by_line', '')}\n\nTime Complexity: {analysis.get('time_complexity', '')}\nSpace Complexity: {analysis.get('space_complexity', '')}",
                                "example": f"Interview Pitch:\n{analysis.get('interview_pitch', '')}\n\nProblem details:\n{p_desc}",
                                "code_snippet": p_code,
                                "programming_language": p_lang,
                                "topic": p_topic if p_topic.strip() else "DSA",
                                "level": p_diff,
                                "company": p_comp if p_comp.strip() else None
                            }
                            
                            insert_entry(fields, f"Code title: {p_title} Description: {p_desc} Code:\n{p_code}", None, emb, source_type="captured", ai_supplemented=True)
                            log_daily_activity()
                            
                            if "plan_prefill_id" in st.session_state:
                                mark_statement_solved(st.session_state.plan_prefill_id)
                                del st.session_state["plan_prefill_id"]
                                del st.session_state["plan_prefill_title"]
                            
                            st.success("🎉 Solved Code Journal entry logged! Activity calendar incremented.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to analyze code solution: {e}")
                            
        with col_j2:
            st.markdown("#### 📖 Saved Solution Journals")
            solved_journals = [e for e in all_entries if e.get("code_snippet")]
            
            if not solved_journals:
                st.info("No code solutions logged in your journal yet.")
            else:
                for journal in solved_journals:
                    lvl_class = f"badge-level-{journal.get('level', 'basic')}"
                    with st.expander(f"💻 {journal['question']} ({journal.get('programming_language')}) — {journal.get('topic')}"):
                        st.markdown(f"""
                        <span class="badge-topic">{journal.get('topic')}</span>
                        <span class="{lvl_class}">{journal.get('level', 'basic').upper()}</span>
                        """, unsafe_allow_html=True)
                        
                        st.markdown("##### 📝 Code Solution")
                        st.code(journal["code_snippet"], language=str(journal.get("programming_language") or "python").lower())
                        
                        st.markdown("##### 🔬 AI Summary & Complexities")
                        st.markdown(journal["answer_summary"])
                        if journal.get("technical_answer"):
                            st.markdown(journal["technical_answer"])
                        if journal.get("example"):
                            st.markdown(journal["example"])
                            
                        txt_card = f"Problem: {journal['question']}\nLanguage: {journal.get('programming_language')}\nComplexity: {journal.get('level')}\n\nCode:\n{journal['code_snippet']}\n\nAI Explanation:\n{journal['answer_summary']}\n{journal.get('technical_answer','')}"
                        st.download_button("📥 Download Code Notes (.txt)", txt_card, file_name=f"{journal['question'].lower().replace(' ', '_')}_notes.txt", key=f"dl_solve_{journal['id']}")

    elif sub_journal == "Planned Problems Planner":
        st.markdown("#### 📌 Pending Coding Problem Statements")
        
        col_p1, col_p2 = st.columns([1, 2])
        
        with col_p1:
            st.markdown("##### Add Planned Problem")
            pl_title = st.text_input("Problem Title / Link")
            pl_desc = st.text_area("Prompt / Description Details")
            pl_source = st.text_input("Source Platform (e.g. LeetCode)")
            pl_lang = st.selectbox("Planned Programming Language", ["Python", "JavaScript", "C++", "Java", "Go", "SQL"])
            pl_diff = st.selectbox("Estimated Difficulty", ["basic", "intermediate", "advanced"])
            pl_date = st.date_input("Target Solved Date")
            pl_topic = st.text_input("Topic Category (e.g. Graphs)")
            
            if st.button("➕ Schedule Planned Problem", use_container_width=True):
                if not pl_title.strip():
                    st.warning("Problem Title is required!")
                else:
                    add_pending_statement(
                        pl_title, pl_desc, pl_source, pl_diff, pl_date.isoformat(), pl_lang, pl_topic
                    )
                    st.success("Planned problem scheduled on the board.")
                    st.rerun()
                    
        with col_p2:
            st.markdown("##### Planner Backlog")
            if not pending_statements:
                st.info("No planned problems pending. Good job!")
            else:
                for plan in pending_statements:
                    st.markdown(f"""
                    <div style="background: rgba(30,41,59,0.55); border: 1px solid rgba(251,191,36,0.15); border-radius:12px; padding:16px; margin-bottom:12px;">
                        <div style="font-weight:700; font-size:16px; color:#fbbf24;">📌 {plan['title']} ({plan.get('programming_language')})</div>
                        <div style="font-size:13px; color:#94a3b8; margin: 4px 0;">Target Date: {plan.get('target_date')} | Topic: {plan.get('topic') or 'General'}</div>
                        <p style="font-size:14px; margin-bottom:10px;">{plan.get('description') or ''}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if st.button("✅ Mark as Solved & Log Code", key=f"solve_plan_{plan['id']}", use_container_width=True):
                            st.session_state.plan_prefill_id = plan["id"]
                            st.session_state.plan_prefill_title = plan["title"]
                            st.session_state.plan_prefill_lang = plan.get("programming_language", "Python")
                            st.session_state.plan_prefill_topic = plan.get("topic", "DSA")
                            st.session_state.plan_prefill_diff = plan.get("difficulty", "intermediate")
                            st.info("Redirected! Code journaling form is prefilled on the left side of 'Solved Problems Log'.")
                            st.rerun()
                    with c_btn2:
                        if st.button("🗑️ Delete Plan", key=f"del_plan_{plan['id']}", use_container_width=True):
                            delete_pending_statement(plan["id"])
                            st.success("Plan deleted.")
                            st.rerun()

# Section 3: Knowledge notebook vault
elif st.session_state.current_menu == "📓 Knowledge Vault":
    st.markdown("### 📓 Developer Knowledge Notebook Vault")
    
    col_k1, col_k2 = st.columns([1, 2])
    
    with col_k1:
        st.markdown("#### ➕ Add Knowledge Note")
        kn_title = st.text_input("Note Title")
        kn_cat = st.text_input("Category (e.g. React, FastApi, Docker)")
        kn_tags_raw = st.text_input("Tags (comma separated, e.g. frontend, state)")
        kn_content = st.text_area("Note Content / Learned Skill Details", height=150)
        kn_code = st.text_area("Reusable Code Snippet (Optional)", height=100)
        
        if st.button("💾 Save Knowledge Note", use_container_width=True):
            if not kn_title.strip() or not kn_content.strip():
                st.warning("Title and Content details are required!")
            else:
                from embed import embed_text
                kn_emb = embed_text(f"{kn_title} {kn_content}")
                tags = [t.strip().lower() for t in kn_tags_raw.split(",") if t.strip()]
                add_knowledge_note(
                    kn_title, kn_cat if kn_cat.strip() else "General", tags, kn_content, kn_code, kn_emb
                )
                st.success("Knowledge note cataloged!")
                st.rerun()
                
    with col_k2:
        st.markdown("#### 🔍 Notebook Catalog")
        
        notebook_cats = sorted(list(set([n.get("category", "General") for n in knowledge_notes])))
        selected_n_cat = st.selectbox("Filter Category", ["All Categories"] + notebook_cats)
        
        filtered_notes = knowledge_notes
        if selected_n_cat != "All Categories":
            filtered_notes = [n for n in knowledge_notes if n.get("category") == selected_n_cat]
            
        if not filtered_notes:
            st.info("No notes logged in this category.")
        else:
            for note in filtered_notes:
                with st.expander(f"📓 {note['title']} ({note.get('category', 'General')})"):
                    st.markdown(note['content'])
                    if note.get("code_snippet"):
                        st.code(note["code_snippet"], language="python")
                    if note.get("tags"):
                        st.markdown(" ".join([f"`#{t}`" for t in note["tags"]]))
                    
                    if st.button("🗑️ Delete Note", key=f"del_note_{note['id']}"):
                        delete_knowledge_note(note["id"])
                        st.success("Note deleted.")
                        st.rerun()

# Section 4: Practice & Spaced revisions flashcards
elif st.session_state.current_menu == "⚡ Spaced Revision":
    st.markdown("### ⚡ PrepGuru Spaced Revision & Mock Practice")
    
    practice_mode = st.radio("Practice Style", ["Flashcards Revision Mode", "5-Question Mock Coach"], horizontal=True)
    
    if practice_mode == "Flashcards Revision Mode":
        st.markdown("#### 🎴 Dynamic Study Flashcards")
        
        rev_pool = []
        for e in all_entries:
            rev_pool.append({
                "type": "Code Solution" if e.get("code_snippet") else "Interview Q&A",
                "title": e["question"],
                "content": e["answer_summary"],
                "details": e.get("technical_answer"),
                "code": e.get("code_snippet"),
                "lang": e.get("programming_language"),
                "topic": e.get("topic", "General"),
                "id": e["id"]
            })
        for n in knowledge_notes:
            rev_pool.append({
                "type": "Knowledge Note",
                "title": n["title"],
                "content": n["content"],
                "details": None,
                "code": n.get("code_snippet"),
                "lang": None,
                "topic": n.get("category", "General"),
                "id": n["id"]
            })
            
        if not rev_pool:
            st.info("Ingest some cards or write some notes before starting revisions.")
        else:
            if 'rev_index' not in st.session_state:
                st.session_state.rev_index = 0
                
            idx = st.session_state.rev_index % len(rev_pool)
            card = rev_pool[idx]
            
            st.markdown(f"**Card {idx + 1} of {len(rev_pool)}** | Category: **{card['type']}**")
            
            st.markdown(f"""
            <div class="flashcard">
                <div style="font-size: 13px; color: #fbbf24; text-transform: uppercase; font-weight:700;">{card['topic']}</div>
                <div style="font-size: 22px; font-weight:700; margin-top:8px; color: #f8fafc;">{card['title']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            reveal = st.checkbox("👁️ Reveal Explanation details & code", key=f"rev_reveal_{idx}")
            
            if reveal:
                st.markdown("##### 📝 Content Summary")
                st.markdown(card["content"])
                if card.get("details"):
                    st.markdown("##### 🔬 Technical details")
                    st.markdown(card["details"])
                if card.get("code"):
                    st.markdown("##### 💻 Reference Code Snippet")
                    st.code(card["code"], language=str(card.get("lang") or "python").lower())
                    
            st.divider()
            
            r_col1, r_col2, r_col3 = st.columns(3)
            with r_col1:
                if st.button("⬅️ Previous Card", use_container_width=True):
                    st.session_state.rev_index -= 1
                    st.rerun()
            with r_col2:
                if card["type"] != "Knowledge Note":
                    conf_rating = st.selectbox("Confidence level", [1,2,3,4,5], index=2, key=f"conf_select_{idx}")
                    if st.button("💾 Save Confidence Check", use_container_width=True):
                        update_entry_confidence(card["id"], conf_rating)
                        st.success("Confidence logged.")
            with r_col3:
                if st.button("Next Card ➡️", use_container_width=True):
                    st.session_state.rev_index += 1
                    st.rerun()

    else:
        st.markdown("### 📋 Weight-Based 5-Question Mock Interview")
        
        if 'mock_active' not in st.session_state:
            st.session_state.mock_active = False
            
        if not st.session_state.mock_active:
            if st.button("🏁 Start Mock Session", use_container_width=True):
                shaky_pool = [e for e in all_entries if e.get("confidence_rating", 3) < 3]
                normal_pool = [e for e in all_entries if e.get("confidence_rating", 3) >= 3]
                
                mock_pool = []
                if shaky_pool:
                    mock_pool.extend(random.sample(shaky_pool, min(3, len(shaky_pool))))
                needed = 5 - len(mock_pool)
                if needed > 0 and normal_pool:
                    mock_pool.extend(random.sample(normal_pool, min(needed, len(normal_pool))))
                    
                random.shuffle(mock_pool)
                
                if len(mock_pool) < 1:
                    st.warning("Add some interview cards in the database first!")
                else:
                    st.session_state.mock_list = mock_pool
                    st.session_state.mock_index = 0
                    st.session_state.mock_scores = []
                    st.session_state.mock_active = True
                    st.rerun()
        else:
            mock_list = st.session_state.mock_list
            idx = st.session_state.mock_index
            
            if idx >= len(mock_list):
                st.balloons()
                st.success("🎉 Mock Interview Session Complete!")
                avg_rating = sum(st.session_state.mock_scores) / len(st.session_state.mock_scores) if st.session_state.mock_scores else 0
                st.metric("Mock Average Rating Score", f"{avg_rating:.1f} / 5.0 ⭐")
                
                if st.button("🏁 Clear & Start New Session", use_container_width=True):
                    st.session_state.mock_active = False
                    st.rerun()
            else:
                active_q = mock_list[idx]
                st.markdown(f"**Question {idx + 1} of {len(mock_list)}**")
                
                st.markdown(f"""
                <div style="background: rgba(99,102,241,0.06); border:1px solid rgba(99,102,241,0.25); border-radius:12px; padding:20px; margin-bottom:16px;">
                    <span class="badge-topic">{active_q.get('topic','General')}</span>
                    <span class="badge-level-intermediate">{active_q.get('level','basic').upper()}</span>
                    <div style="font-size:18px; font-weight:700; margin-top:8px; color:#fbbf24;">Q: {active_q['question']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                cand_ans = st.text_area("Your Candidate Answer Attempt:", key=f"cand_mock_ans_{active_q['id']}", height=120)
                
                col_mc1, col_mc2 = st.columns(2)
                with col_mc1:
                    grade_btn = st.button("🎯 Submit & Evaluate Attempt", use_container_width=True)
                with col_mc2:
                    rev_ans = st.button("👁️ Reveal Expected Summary", use_container_width=True)
                    
                if grade_btn:
                    if has_reached_rate_limit():
                        st.error("⚠️ Session limit reached.")
                    elif not cand_ans.strip():
                        st.warning("Please type your answer first!")
                    else:
                        increment_llm_action()
                        with st.spinner("AI Coach is evaluating..."):
                            feedback = evaluate_answer(active_q['question'], active_q['answer_summary'], cand_ans)
                            
                            save_attempt(
                                entry_id=active_q['id'],
                                user_answer=cand_ans,
                                rating=feedback.get('rating', 3),
                                feedback_right=feedback.get('got_right', ''),
                                feedback_missed=feedback.get('missed', ''),
                                feedback_tip=feedback.get('tip', '')
                            )
                            update_last_reviewed(active_q['id'])
                            st.session_state.mock_scores.append(feedback.get('rating', 3))
                            
                            st.markdown("<div style='background: rgba(99,102,241,0.08); border:1px solid rgba(99,102,241,0.2); border-radius:12px; padding:20px; margin-top:16px;'>", unsafe_allow_html=True)
                            st.markdown(f"#### AI Rating: {'⭐' * feedback.get('rating', 3)}")
                            st.markdown(f"**What You Got Right:**\n{feedback.get('got_right')}")
                            st.markdown(f"**What You Missed:**\n{feedback.get('missed')}")
                            st.markdown(f"**Coach Tip:**\n{feedback.get('tip')}")
                            st.markdown("</div>", unsafe_allow_html=True)
                            
                if rev_ans:
                    st.markdown(f"**Reference Expected Summary:**\n{active_q['answer_summary']}")
                    if active_q.get("technical_answer"):
                        st.markdown(f"**Technical Details:**\n{active_q['technical_answer']}")
                        
                st.divider()
                st.markdown("##### 📌 Self-Rating Confidence Check")
                new_conf = st.slider("How well do you know this topic?", 1, 5, int(active_q.get("confidence_rating", 3)), key=f"conf_slider_mock_{active_q['id']}")
                
                if st.button("💾 Save Rating & Next Question", use_container_width=True):
                    update_entry_confidence(active_q['id'], new_conf)
                    st.session_state.mock_index += 1
                    st.rerun()

# Section 5: Analytics and Streaks Calendar
elif st.session_state.current_menu == "📈 Streaks & Metrics":
    st.markdown("### 📈 PrepGuru Performance & Habit Analytics")
    
    total_qas = len([e for e in all_entries if not e.get("code_snippet")])
    total_codes = len([e for e in all_entries if e.get("code_snippet")])
    total_notes = len(knowledge_notes)
    
    streak_days = sorted(list(set([datetime.date.fromisoformat(l['activity_date']) for l in activity_logs])))
    
    today = datetime.date.today()
    current_streak = 0
    longest_streak = 0
    if streak_days:
        yesterday = today - datetime.timedelta(days=1)
        
        temp_streak = 0
        check_day = today
        if yesterday in streak_days and today not in streak_days:
            check_day = yesterday
            
        while check_day in streak_days:
            temp_streak += 1
            check_day -= datetime.timedelta(days=1)
        current_streak = temp_streak
        
        max_str = 0
        curr_str = 0
        prev_d = None
        for d in streak_days:
            if prev_d is None:
                curr_str = 1
            elif (d - prev_d).days == 1:
                curr_str += 1
            else:
                max_str = max(max_str, curr_str)
                curr_str = 1
            prev_d = d
        longest_streak = max(max_str, curr_str)
        
    st.markdown(f"""
    <div class="metrics-container">
        <div class="metric-card">
            <div class="metric-label">Saved Q&As</div>
            <div class="metric-value">{total_qas}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Code Solutions</div>
            <div class="metric-value">{total_codes}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Vault Notes</div>
            <div class="metric-value">{total_notes}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Current Streak</div>
            <div class="metric-value">🔥 {current_streak} days</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Longest Streak</div>
            <div class="metric-value">🏆 {longest_streak} days</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col_a1, col_a2 = st.columns(2)
    
    with col_a1:
        st.markdown("#### 📅 Solve Activity Calendar")
        start_date = today - datetime.timedelta(weeks=10)
        
        activity_map = {l['activity_date']: l['solved_count'] for l in activity_logs}
        
        grid_html = '<div class="heatmap-grid">'
        for d_offset in range(77):
            curr = start_date + datetime.timedelta(days=d_offset)
            curr_str = curr.isoformat()
            count = activity_map.get(curr_str, 0)
            
            if count == 0:
                color = "rgba(255,255,255,0.06)"
            elif count == 1:
                color = "#39d353"
            elif count == 2:
                color = "#26a641"
            else:
                color = "#0e4429"
                
            grid_html += f'<div class="heatmap-cell" style="background: {color};" title="{curr_str}: {count} solves"></div>'
        grid_html += '</div>'
        
        st.markdown(grid_html, unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; font-size:11px; color:#94a3b8;'>Colors represent activity density over the past 11 weeks.</p>", unsafe_allow_html=True)

    with col_a2:
        st.markdown("#### 📊 Complexity Breakdown")
        df_q = pd.DataFrame(all_entries)
        if not df_q.empty:
            diff_counts = df_q.groupby('level').size()
            st.bar_chart(diff_counts)
        else:
            st.info("No data to display breakdown yet.")

# Section 6: Market Trends Scanner
elif st.session_state.current_menu == "📊 Market Trends":
    st.markdown("### 📊 Market trends Analysis crawler")
    st.markdown("Fetches GitHub framework launches and HackerNews feeds, summarizing hiring patterns.")
    
    from db import fetch_latest_market_trends
    from market_scanner import run_market_scan
    
    trends = fetch_latest_market_trends()
    if st.button("🔄 Trigger Market scan crawl", use_container_width=True):
        if has_reached_rate_limit():
            st.error("⚠️ Session limit reached.")
        else:
            increment_llm_action()
            with st.spinner("Analyzing web feeds..."):
                trends = run_market_scan()
                st.success("Trends updated!")
                st.rerun()
                
    if trends:
        st.markdown("#### 🔥 Trending Technical Skills")
        st.markdown(" ".join([f"`{t}`" for t in trends.get("trending_skills", [])]))
        
        st.markdown("##### 📝 Research Summary")
        st.markdown(trends.get("summary"))
        if trends.get("sources"):
            st.caption(f"Sources checked: {', '.join(trends['sources'])}")
    else:
        st.info("No market scans executed yet. Click above to scan.")

# Section 7: Manual ingestion & Backups
elif st.session_state.current_menu == "📥 Ingest & Backups":
    st.markdown("### 📥 Backup Restore, Manual Entry & Failed Captures")
    
    col_in1, col_in2 = st.columns(2)
    
    with col_in1:
        st.markdown("#### 📂 Database Backup Manager")
        
        if all_entries:
            clean_backup = []
            for item in all_entries:
                cleaned = item.copy()
                if "embedding" in cleaned:
                    del cleaned["embedding"]
                clean_backup.append(cleaned)
            json_str = json.dumps(clean_backup, indent=2, default=str)
            st.download_button("📤 Export Database to JSON", json_str, file_name="prepguru_backup.json", mime="application/json", use_container_width=True)
            
        uploaded_backup = st.file_uploader("Upload JSON Backup File to Restore Database", type="json")
        if uploaded_backup:
            try:
                backup_data = json.load(uploaded_backup)
                if st.button("📥 Import Restore Data", use_container_width=True):
                    restored, skipped = restore_database_from_backup(backup_data)
                    st.success(f"Backup Import complete! Restored: {restored} cards. Skipped (duplicates): {skipped} cards.")
                    st.rerun()
            except Exception as backup_err:
                st.error(f"Failed to parse uploaded backup file: {backup_err}")
                
    with col_in2:
        st.markdown("#### ➕ Add Manual Q&A Card")
        man_q = st.text_input("Interview Question")
        man_ans = st.text_area("Answer Analogy Summary")
        man_tech = st.text_area("Technical Details (Optional)")
        man_topic = st.text_input("Topic (e.g. System Design)")
        man_level = st.selectbox("Difficulty Level", ["basic", "intermediate", "advanced"], key="man_level_sel")
        
        if st.button("💾 Save Manual Card", use_container_width=True):
            if not man_q.strip() or not man_ans.strip():
                st.warning("Question and Answer Analogy are required!")
            else:
                from embed import embed_text
                man_emb = embed_text(f"{man_q} {man_ans}")
                
                fields = {
                    "question": man_q,
                    "answer_summary": man_ans,
                    "technical_answer": man_tech,
                    "topic": man_topic if man_topic.strip() else "General",
                    "level": man_level,
                    "ai_supplemented": False
                }
                insert_entry(fields, f"Question: {man_q} Answer: {man_ans}", None, man_emb)
                st.success("Manual card saved!")
                st.rerun()

    # Failed Ingestion Queue
    st.divider()
    st.markdown("#### ❌ Failed Telegram OCR Captures Queue")
    
    from db import fetch_failed_queue, delete_from_failed_queue
    failed_items = fetch_failed_queue()
    
    if not failed_items:
        st.info("Failed queue is currently empty. Everything processed successfully!")
    else:
        for idx, item in enumerate(failed_items):
            with st.expander(f"Failed Ingestion Attempt {idx + 1} ({item.get('created_at')[:16]})"):
                st.error(f"Error Message: {item.get('error_message')}")
                st.markdown("##### Raw Text Extracted:")
                st.code(item.get("raw_text"), language="text")
                
                c_q1, c_q2 = st.columns(2)
                with c_q1:
                    if st.button("🔄 Retry Parse with AI", key=f"retry_fail_{item['id']}", use_container_width=True):
                        if has_reached_rate_limit():
                            st.error("⚠️ Session limit reached.")
                        else:
                            increment_llm_action()
                            with st.spinner("Retrying extraction..."):
                                try:
                                    parsed = extract_fields(item["raw_text"])
                                    from embed import embed_text
                                    emb = embed_text(f"{parsed.get('question')} {parsed.get('answer_summary')}")
                                    insert_entry(parsed, item["raw_text"], None, emb, source_type="captured", ai_supplemented=parsed.get("ai_supplemented", False))
                                    delete_from_failed_queue(item["id"])
                                    st.success("Successfully processed card! Removed from failed queue.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Retry failed again: {e}")
                with c_q2:
                    if st.button("🗑️ Delete from Queue", key=f"del_fail_{item['id']}", use_container_width=True):
                        delete_from_failed_queue(item["id"])
                        st.success("Item removed from queue.")
                        st.rerun()

# Master PDF Regenerator build
if all_entries:
    try:
        regenerate_pdf()
    except Exception:
        pass

# Sidebar controls & Personal Disclaimer
with st.sidebar:
    st.markdown("### 🛠️ PrepGuru Panel")
    
    if st.button("🗑️ Clear Mock history", use_container_width=True):
        clear_attempts_history()
        st.success("Mock history cleared!")
        st.rerun()
        
    st.markdown("---")
    st.markdown("<p style='font-size:11px; text-align:center; color:#64748b;'>PrepGuru © 2026. Made with Google DeepMind Advanced Agentic Coding.</p>", unsafe_allow_html=True)
