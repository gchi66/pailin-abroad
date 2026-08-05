-- Transactionally record one Exercise Bank v2 answer and update learner progress.

create or replace function public.record_exercise_bank_v2_attempt(
  p_user_id uuid,
  p_question_id bigint,
  p_user_answer text,
  p_is_correct boolean,
  p_grading_method text,
  p_ai_score numeric default null,
  p_ai_feedback_en text default null,
  p_ai_feedback_th text default null,
  p_ai_model text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_topic_id bigint;
  v_practice_order integer;
  v_content_version integer;
  v_set_number integer;
  v_set_position smallint;
  v_now timestamp with time zone := now();
  v_state public.user_exercise_bank_question_state%rowtype;
  v_topic_complete boolean;
  v_first_completed_at timestamp with time zone;
  v_completed_content_version integer;
begin
  if p_user_id is null then
    raise exception 'user_id is required';
  end if;
  if p_user_answer is null or btrim(p_user_answer) = '' then
    raise exception 'user_answer is required';
  end if;
  if p_grading_method not in ('deterministic', 'ai') then
    raise exception 'invalid grading method';
  end if;
  if p_grading_method = 'deterministic' and (
    p_ai_score is not null
    or p_ai_feedback_en is not null
    or p_ai_feedback_th is not null
    or p_ai_model is not null
  ) then
    raise exception 'deterministic grading cannot include AI fields';
  end if;

  select
    e.topic_id,
    q.practice_order,
    t.content_version
  into
    v_topic_id,
    v_practice_order,
    v_content_version
  from public.exercise_bank_questions q
  join public.exercise_bank_exercises e
    on e.id = q.exercise_id
  join public.exercise_bank_topics t
    on t.id = e.topic_id
  where q.id = p_question_id
    and q.is_active = true
    and q.is_example = false
    and q.practice_order is not null
    and e.is_active = true
    and t.is_active = true;

  if not found then
    raise exception 'active exercise bank question not found';
  end if;

  v_set_number := ((v_practice_order - 1) / 5) + 1;
  v_set_position := (((v_practice_order - 1) % 5) + 1)::smallint;

  insert into public.user_exercise_bank_question_attempts (
    user_id,
    question_id,
    user_answer,
    is_correct,
    grading_method,
    ai_score,
    ai_feedback_en,
    ai_feedback_th,
    ai_model,
    created_at
  ) values (
    p_user_id,
    p_question_id,
    p_user_answer,
    p_is_correct,
    p_grading_method,
    p_ai_score,
    p_ai_feedback_en,
    p_ai_feedback_th,
    p_ai_model,
    v_now
  );

  insert into public.user_exercise_bank_question_state (
    user_id,
    topic_id,
    question_id,
    set_number,
    set_position,
    assigned_content_version,
    attempt_count,
    has_answered_correctly,
    latest_user_answer,
    latest_is_correct,
    latest_ai_score,
    latest_ai_feedback_en,
    latest_ai_feedback_th,
    latest_ai_model,
    first_correct_at,
    last_attempted_at
  ) values (
    p_user_id,
    v_topic_id,
    p_question_id,
    v_set_number,
    v_set_position,
    v_content_version,
    1,
    p_is_correct,
    p_user_answer,
    p_is_correct,
    p_ai_score,
    p_ai_feedback_en,
    p_ai_feedback_th,
    p_ai_model,
    case when p_is_correct then v_now else null end,
    v_now
  )
  on conflict (user_id, question_id) do update set
    attempt_count = public.user_exercise_bank_question_state.attempt_count + 1,
    has_answered_correctly =
      public.user_exercise_bank_question_state.has_answered_correctly
      or excluded.has_answered_correctly,
    latest_user_answer = excluded.latest_user_answer,
    latest_is_correct = excluded.latest_is_correct,
    latest_ai_score = excluded.latest_ai_score,
    latest_ai_feedback_en = excluded.latest_ai_feedback_en,
    latest_ai_feedback_th = excluded.latest_ai_feedback_th,
    latest_ai_model = excluded.latest_ai_model,
    first_correct_at = coalesce(
      public.user_exercise_bank_question_state.first_correct_at,
      excluded.first_correct_at
    ),
    last_attempted_at = excluded.last_attempted_at
  returning * into v_state;

  select not exists (
    select 1
    from public.exercise_bank_questions q
    join public.exercise_bank_exercises e
      on e.id = q.exercise_id
    where e.topic_id = v_topic_id
      and e.is_active = true
      and q.is_active = true
      and q.is_example = false
      and q.practice_order is not null
      and not exists (
        select 1
        from public.user_exercise_bank_question_state s
        where s.user_id = p_user_id
          and s.question_id = q.id
          and s.has_answered_correctly = true
      )
  ) into v_topic_complete;

  if v_topic_complete then
    insert into public.user_exercise_bank_topic_progress (
      user_id,
      topic_id,
      first_completed_at,
      completed_content_version,
      version_completed_at
    ) values (
      p_user_id,
      v_topic_id,
      v_now,
      v_content_version,
      v_now
    )
    on conflict (user_id, topic_id) do update set
      first_completed_at = coalesce(
        public.user_exercise_bank_topic_progress.first_completed_at,
        excluded.first_completed_at
      ),
      completed_content_version = greatest(
        coalesce(public.user_exercise_bank_topic_progress.completed_content_version, 0),
        excluded.completed_content_version
      ),
      version_completed_at = case
        when coalesce(
          public.user_exercise_bank_topic_progress.completed_content_version,
          0
        ) < excluded.completed_content_version
          then excluded.version_completed_at
        else public.user_exercise_bank_topic_progress.version_completed_at
      end;
  end if;

  select
    p.first_completed_at,
    p.completed_content_version
  into
    v_first_completed_at,
    v_completed_content_version
  from public.user_exercise_bank_topic_progress p
  where p.user_id = p_user_id
    and p.topic_id = v_topic_id;

  return jsonb_build_object(
    'topic_id', v_topic_id,
    'question_id', p_question_id,
    'set_number', v_state.set_number,
    'set_position', v_state.set_position,
    'attempt_count', v_state.attempt_count,
    'has_answered_correctly', v_state.has_answered_correctly,
    'topic_complete', v_topic_complete,
    'first_completed_at', v_first_completed_at,
    'completed_content_version', v_completed_content_version
  );
end;
$$;

revoke all on function public.record_exercise_bank_v2_attempt(
  uuid, bigint, text, boolean, text, numeric, text, text, text
) from public;

revoke all on function public.record_exercise_bank_v2_attempt(
  uuid, bigint, text, boolean, text, numeric, text, text, text
) from anon, authenticated;

grant execute on function public.record_exercise_bank_v2_attempt(
  uuid, bigint, text, boolean, text, numeric, text, text, text
) to service_role;

comment on function public.record_exercise_bank_v2_attempt(
  uuid, bigint, text, boolean, text, numeric, text, text, text
) is
'Backend-only transactional write for one Exercise Bank v2 attempt, sticky question mastery, and topic completion.';
