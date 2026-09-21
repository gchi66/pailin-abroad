create table if not exists public.practice_review_answer_cache (
  exercise_id text not null,
  item_key text not null,
  source_hash text not null,
  review_answer text not null,
  created_at timestamptz not null default now(),
  primary key (exercise_id, item_key)
);

-- The backend service role reads and writes this cache. Learners receive answers
-- only through the authenticated review-answer endpoint.
alter table public.practice_review_answer_cache enable row level security;
