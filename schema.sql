-- Run this once in the Supabase SQL editor (free tier project)

create extension if not exists vector;

create table if not exists qa_entries (
    id uuid primary key default gen_random_uuid(),
    raw_text text not null,
    question text,
    answer_summary text,
    example text,
    topic text,
    level text check (level in ('basic', 'intermediate', 'advanced')),
    company text,
    source_url text,
    created_at timestamptz default now(),
    embedding vector(384)  -- matches all-MiniLM-L6-v2 output size
);

-- Disable Row Level Security (simplest for personal apps using the anonymous key)
alter table qa_entries disable row level security;

-- Or, if you want to keep RLS enabled but allow public anonymous inserts & selects, run this instead:
-- alter table qa_entries enable row level security;
-- create policy "Allow public read access" on qa_entries for select using (true);
-- create policy "Allow public write access" on qa_entries for insert with check (true);

create index if not exists qa_entries_embedding_idx
    on qa_entries using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

-- Semantic search RPC, called from the Streamlit app
create or replace function match_qa_entries(
    query_embedding vector(384),
    match_count int default 5
)
returns table (
    id uuid,
    question text,
    answer_summary text,
    example text,
    topic text,
    level text,
    company text,
    source_url text,
    similarity float
)
language sql stable
as $$
    select
        id, question, answer_summary, example, topic, level, company, source_url,
        1 - (embedding <=> query_embedding) as similarity
    from qa_entries
    order by embedding <=> query_embedding
    limit match_count;
$$;

-- Table to log practice attempts and score history
create table if not exists qa_attempts (
    id uuid primary key default gen_random_uuid(),
    entry_id uuid references qa_entries(id) on delete cascade,
    attempted_at timestamptz default now(),
    user_answer text not null,
    rating int check (rating >= 1 and rating <= 5),
    feedback_right text,
    feedback_missed text,
    feedback_tip text
);

-- Upgrade schema for content provenance, spaced repetition review counts, and source types
alter table qa_entries 
add column if not exists source_type text default 'captured' check (source_type in ('captured', 'ai_generated')),
add column if not exists ai_supplemented boolean default false,
add column if not exists last_reviewed timestamptz,
add column if not exists review_count int default 0;

-- Table to process processing failures / retries (Failed Queue)
create table if not exists qa_failed_queue (
    id uuid primary key default gen_random_uuid(),
    raw_text text not null,
    error_message text,
    created_at timestamptz default now()
);

-- Disable Row Level Security (RLS) on all tables
alter table qa_entries disable row level security;
alter table qa_attempts disable row level security;
alter table qa_failed_queue disable row level security;

-- Alter qa_entries to store separate technical answers, Mermaid diagrams, and self-ratings
alter table qa_entries 
add column if not exists technical_answer text,
add column if not exists concept_diagram text,
add column if not exists confidence_rating int default 3 check (confidence_rating >= 1 and confidence_rating <= 5);

-- Create table for automated market trend research digests
create table if not exists qa_market_trends (
    id uuid primary key default gen_random_uuid(),
    scanned_at timestamptz default now(),
    trending_skills text[] not null,
    summary text not null,
    sources text[] not null
);

-- Create table to store AI-synthesized topic overviews
create table if not exists qa_topic_summaries (
    topic text primary key,
    summary text not null,
    updated_at timestamptz default now()
);

-- Create table to log Telegram chat IDs for digest notifications
create table if not exists qa_user_chats (
    chat_id text primary key,
    registered_at timestamptz default now()
);

-- Disable RLS on new tables
alter table qa_market_trends disable row level security;
alter table qa_topic_summaries disable row level security;
alter table qa_user_chats disable row level security;

-- PrepGuru consolidation columns in qa_entries
alter table qa_entries 
add column if not exists code_snippet text,
add column if not exists programming_language text;

-- Create table for pending problem statements
create table if not exists pending_statements (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz default now(),
    title text not null,
    description text,
    source_url text,
    difficulty text default 'medium',
    target_date date,
    programming_language text,
    topic text,
    is_solved boolean default false
);

-- Create table for knowledge vault notes
create table if not exists knowledge_notes (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz default now(),
    title text not null,
    category text default 'General',
    tags text[],
    content text not null,
    code_snippet text,
    embedding vector(384)
);

-- Create table for user daily activity logs (streaks)
create table if not exists user_activity_log (
    id uuid primary key default gen_random_uuid(),
    activity_date date default current_date unique,
    solved_count int default 1
);

-- Disable RLS on PrepGuru tables
alter table pending_statements disable row level security;
alter table knowledge_notes disable row level security;
alter table user_activity_log disable row level security;

-- Create pgvector similarity matching function for knowledge notebook
create or replace function match_knowledge_notes (
  query_embedding vector(384),
  match_count int
)
returns table (
  id uuid,
  title text,
  category text,
  tags text[],
  content text,
  code_snippet text,
  created_at timestamptz,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    knowledge_notes.id,
    knowledge_notes.title,
    knowledge_notes.category,
    knowledge_notes.tags,
    knowledge_notes.content,
    knowledge_notes.code_snippet,
    knowledge_notes.created_at,
    1 - (knowledge_notes.embedding <=> query_embedding) as similarity
  from knowledge_notes
  order by knowledge_notes.embedding <=> query_embedding
  limit match_count;
end;
$$;
