-- Exercise Bank v2 learner state.
--
-- Content continues to live in:
--   exercise_bank_topics -> exercise_bank_exercises -> exercise_bank_questions
--
-- This migration adds:
--   1. Stable per-user set assignment and current question mastery state.
--   2. Durable per-user topic completion/version state.
--   3. An append-only answer log for grading audits and future analytics.
--
-- It intentionally does not modify the legacy user_exercise_answers table.

alter table public.exercise_bank_topics
add column if not exists content_version integer not null default 1;

alter table public.exercise_bank_topics
add constraint exercise_bank_topics_content_version_positive
check (content_version > 0) not valid;

alter table public.exercise_bank_topics
validate constraint exercise_bank_topics_content_version_positive;

comment on column public.exercise_bank_topics.content_version is
'Manually incremented when the active published question pool changes. Used to preserve completion while showing newly added questions.';


create table public.user_exercise_bank_question_state (
  id uuid not null default gen_random_uuid(),
  user_id uuid not null,
  topic_id bigint not null,
  question_id bigint not null,
  set_number integer not null,
  set_position smallint not null,
  assigned_content_version integer not null,
  attempt_count integer not null default 0,
  has_answered_correctly boolean not null default false,
  latest_user_answer text null,
  latest_is_correct boolean null,
  latest_ai_score numeric(3, 2) null,
  latest_ai_feedback_en text null,
  latest_ai_feedback_th text null,
  latest_ai_model text null,
  first_correct_at timestamp with time zone null,
  last_attempted_at timestamp with time zone null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint user_exercise_bank_question_state_pkey primary key (id),
  constraint user_exercise_bank_question_state_user_fkey
    foreign key (user_id) references public.users (id) on delete cascade,
  constraint user_exercise_bank_question_state_topic_fkey
    foreign key (topic_id) references public.exercise_bank_topics (id) on delete cascade,
  constraint user_exercise_bank_question_state_question_fkey
    foreign key (question_id) references public.exercise_bank_questions (id) on delete cascade,
  constraint user_exercise_bank_question_state_user_question_key
    unique (user_id, question_id),
  constraint user_exercise_bank_question_state_set_position_key
    unique (user_id, topic_id, set_number, set_position),
  constraint user_exercise_bank_question_state_set_number_positive
    check (set_number > 0),
  constraint user_exercise_bank_question_state_set_position_range
    check (set_position between 1 and 5),
  constraint user_exercise_bank_question_state_assigned_version_positive
    check (assigned_content_version > 0),
  constraint user_exercise_bank_question_state_attempt_count_nonnegative
    check (attempt_count >= 0),
  constraint user_exercise_bank_question_state_ai_score_range
    check (latest_ai_score is null or latest_ai_score between 0 and 1),
  constraint user_exercise_bank_question_state_correct_timestamp
    check (has_answered_correctly = false or first_correct_at is not null)
);

comment on table public.user_exercise_bank_question_state is
'One current-state row per user/question. Also stores the question''s stable assignment into a user-specific set of up to five.';

comment on column public.user_exercise_bank_question_state.assigned_content_version is
'Topic content_version when this question was assigned. Supports the completed checkmark plus N new badge.';

comment on column public.user_exercise_bank_question_state.has_answered_correctly is
'Sticky mastery flag: once true, later incorrect practice attempts must not reset it.';

create index idx_user_exercise_bank_question_state_topic_sets
  on public.user_exercise_bank_question_state
  using btree (user_id, topic_id, set_number, set_position);

create index idx_user_exercise_bank_question_state_review
  on public.user_exercise_bank_question_state
  using btree (user_id, topic_id, has_answered_correctly, last_attempted_at);


create table public.user_exercise_bank_topic_progress (
  id uuid not null default gen_random_uuid(),
  user_id uuid not null,
  topic_id bigint not null,
  first_completed_at timestamp with time zone null,
  completed_content_version integer null,
  version_completed_at timestamp with time zone null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint user_exercise_bank_topic_progress_pkey primary key (id),
  constraint user_exercise_bank_topic_progress_user_fkey
    foreign key (user_id) references public.users (id) on delete cascade,
  constraint user_exercise_bank_topic_progress_topic_fkey
    foreign key (topic_id) references public.exercise_bank_topics (id) on delete cascade,
  constraint user_exercise_bank_topic_progress_user_topic_key
    unique (user_id, topic_id),
  constraint user_exercise_bank_topic_progress_version_positive
    check (completed_content_version is null or completed_content_version > 0),
  constraint user_exercise_bank_topic_progress_completion_consistent
    check (
      (completed_content_version is null and version_completed_at is null)
      or
      (completed_content_version is not null and version_completed_at is not null)
    )
);

comment on table public.user_exercise_bank_topic_progress is
'Durable topic achievement. first_completed_at is never cleared; completed_content_version advances after all questions in a newer version are mastered.';

create index idx_user_exercise_bank_topic_progress_user
  on public.user_exercise_bank_topic_progress
  using btree (user_id, topic_id);


create table public.user_exercise_bank_question_attempts (
  id uuid not null default gen_random_uuid(),
  user_id uuid not null,
  question_id bigint not null,
  user_answer text not null,
  is_correct boolean not null,
  grading_method text not null,
  ai_score numeric(3, 2) null,
  ai_feedback_en text null,
  ai_feedback_th text null,
  ai_model text null,
  created_at timestamp with time zone not null default now(),
  constraint user_exercise_bank_question_attempts_pkey primary key (id),
  constraint user_exercise_bank_question_attempts_user_fkey
    foreign key (user_id) references public.users (id) on delete cascade,
  constraint user_exercise_bank_question_attempts_question_fkey
    foreign key (question_id) references public.exercise_bank_questions (id) on delete cascade,
  constraint user_exercise_bank_question_attempts_grading_method
    check (grading_method in ('deterministic', 'ai')),
  constraint user_exercise_bank_question_attempts_ai_score_range
    check (ai_score is null or ai_score between 0 and 1),
  constraint user_exercise_bank_question_attempts_ai_fields
    check (
      grading_method = 'ai'
      or (
        ai_score is null
        and ai_feedback_en is null
        and ai_feedback_th is null
        and ai_model is null
      )
    )
);

comment on table public.user_exercise_bank_question_attempts is
'Append-only Exercise Bank v2 submission log. Supports AI-grading audits without using or changing the legacy user_exercise_answers table.';

create index idx_user_exercise_bank_question_attempts_user_question
  on public.user_exercise_bank_question_attempts
  using btree (user_id, question_id, created_at desc);

create index idx_user_exercise_bank_question_attempts_created
  on public.user_exercise_bank_question_attempts
  using btree (created_at);


create trigger trg_update_user_exercise_bank_question_state
before update on public.user_exercise_bank_question_state
for each row execute function public.update_timestamp_column();

create trigger trg_update_user_exercise_bank_topic_progress
before update on public.user_exercise_bank_topic_progress
for each row execute function public.update_timestamp_column();


alter table public.user_exercise_bank_question_state enable row level security;
alter table public.user_exercise_bank_topic_progress enable row level security;
alter table public.user_exercise_bank_question_attempts enable row level security;

create policy "Users can read their own exercise bank question state"
on public.user_exercise_bank_question_state
for select
to authenticated
using (auth.uid() = user_id);

create policy "Users can read their own exercise bank topic progress"
on public.user_exercise_bank_topic_progress
for select
to authenticated
using (auth.uid() = user_id);

create policy "Users can read their own exercise bank attempts"
on public.user_exercise_bank_question_attempts
for select
to authenticated
using (auth.uid() = user_id);

-- Mutations are intentionally backend-only. The service-role client bypasses RLS,
-- allowing set assignment and answer/progress updates to happen atomically in the API.
