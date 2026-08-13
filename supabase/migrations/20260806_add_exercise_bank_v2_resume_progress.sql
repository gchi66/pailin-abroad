-- Explicit Exercise Bank v2 navigation progress.
--
-- Question mastery remains stored independently in
-- user_exercise_bank_question_state. A set is considered completed only after
-- the learner explicitly advances from its results screen.

alter table public.user_exercise_bank_topic_progress
  add column if not exists active_set_number integer not null default 1,
  add column if not exists active_set_position smallint not null default 1,
  add column if not exists active_view text not null default 'question',
  add column if not exists last_advanced_set_number integer not null default 0;

alter table public.user_exercise_bank_topic_progress
  add constraint user_exercise_bank_topic_progress_active_set_positive
    check (active_set_number > 0) not valid,
  add constraint user_exercise_bank_topic_progress_active_position_range
    check (active_set_position between 1 and 5) not valid,
  add constraint user_exercise_bank_topic_progress_active_view_valid
    check (active_view in ('question', 'results')) not valid,
  add constraint user_exercise_bank_topic_progress_advanced_set_nonnegative
    check (last_advanced_set_number >= 0) not valid;

alter table public.user_exercise_bank_topic_progress
  validate constraint user_exercise_bank_topic_progress_active_set_positive;
alter table public.user_exercise_bank_topic_progress
  validate constraint user_exercise_bank_topic_progress_active_position_range;
alter table public.user_exercise_bank_topic_progress
  validate constraint user_exercise_bank_topic_progress_active_view_valid;
alter table public.user_exercise_bank_topic_progress
  validate constraint user_exercise_bank_topic_progress_advanced_set_nonnegative;

comment on column public.user_exercise_bank_topic_progress.active_set_number is
'The learner''s current unadvanced set. Used to resume the Exercise Bank.';
comment on column public.user_exercise_bank_topic_progress.active_set_position is
'The exact question position to restore within active_set_number.';
comment on column public.user_exercise_bank_topic_progress.active_view is
'Whether reopening should restore the active question or the set results screen.';
comment on column public.user_exercise_bank_topic_progress.last_advanced_set_number is
'Highest sequential set explicitly completed by pressing the advance action.';


create or replace function public.save_exercise_bank_v2_cursor(
  p_user_id uuid,
  p_topic_id bigint,
  p_set_number integer,
  p_set_position smallint,
  p_view text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_total_questions integer;
  v_total_sets integer;
  v_set_question_count integer;
  v_last_advanced integer := 0;
  v_progress public.user_exercise_bank_topic_progress%rowtype;
begin
  if p_user_id is null then raise exception 'user_id is required'; end if;
  if p_set_number < 1 then raise exception 'set_number must be positive'; end if;
  if p_set_position not between 1 and 5 then raise exception 'invalid set position'; end if;
  if p_view not in ('question', 'results') then raise exception 'invalid view'; end if;

  select count(*)
  into v_total_questions
  from public.exercise_bank_questions q
  join public.exercise_bank_exercises e on e.id = q.exercise_id
  join public.exercise_bank_topics t on t.id = e.topic_id
  where t.id = p_topic_id
    and t.is_active = true
    and e.is_active = true
    and q.is_active = true
    and q.is_example = false
    and q.practice_order is not null;

  if v_total_questions = 0 then raise exception 'active exercise bank topic not found'; end if;
  v_total_sets := ceil(v_total_questions / 5.0)::integer;
  if p_set_number > v_total_sets then raise exception 'set not found'; end if;

  select count(*)
  into v_set_question_count
  from public.exercise_bank_questions q
  join public.exercise_bank_exercises e on e.id = q.exercise_id
  where e.topic_id = p_topic_id
    and e.is_active = true
    and q.is_active = true
    and q.is_example = false
    and q.practice_order between ((p_set_number - 1) * 5 + 1) and (p_set_number * 5);

  if p_set_position > v_set_question_count then raise exception 'question position not found'; end if;

  select p.last_advanced_set_number
  into v_last_advanced
  from public.user_exercise_bank_topic_progress p
  where p.user_id = p_user_id and p.topic_id = p_topic_id;
  v_last_advanced := coalesce(v_last_advanced, 0);
  if p_set_number > v_last_advanced + 1 then
    raise exception 'cannot resume a set before earlier sets are advanced';
  end if;

  insert into public.user_exercise_bank_topic_progress (
    user_id, topic_id, active_set_number, active_set_position, active_view
  ) values (
    p_user_id, p_topic_id, p_set_number, p_set_position, p_view
  )
  on conflict (user_id, topic_id) do update set
    active_set_number = case
      when p_set_number = public.user_exercise_bank_topic_progress.last_advanced_set_number + 1
        then excluded.active_set_number
      else public.user_exercise_bank_topic_progress.active_set_number
    end,
    active_set_position = case
      when p_set_number = public.user_exercise_bank_topic_progress.last_advanced_set_number + 1
        then excluded.active_set_position
      else public.user_exercise_bank_topic_progress.active_set_position
    end,
    active_view = case
      when p_set_number = public.user_exercise_bank_topic_progress.last_advanced_set_number + 1
        then excluded.active_view
      else public.user_exercise_bank_topic_progress.active_view
    end
  returning * into v_progress;

  return jsonb_build_object(
    'topic_id', p_topic_id,
    'active_set_number', v_progress.active_set_number,
    'active_set_position', v_progress.active_set_position,
    'active_view', v_progress.active_view,
    'last_advanced_set_number', v_progress.last_advanced_set_number
  );
end;
$$;


create or replace function public.advance_exercise_bank_v2_set(
  p_user_id uuid,
  p_topic_id bigint,
  p_set_number integer
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_total_questions integer;
  v_total_sets integer;
  v_content_version integer;
  v_last_advanced integer := 0;
  v_now timestamp with time zone := now();
  v_progress public.user_exercise_bank_topic_progress%rowtype;
begin
  if p_user_id is null then raise exception 'user_id is required'; end if;
  if p_set_number < 1 then raise exception 'set_number must be positive'; end if;

  select count(*), max(t.content_version)
  into v_total_questions, v_content_version
  from public.exercise_bank_questions q
  join public.exercise_bank_exercises e on e.id = q.exercise_id
  join public.exercise_bank_topics t on t.id = e.topic_id
  where t.id = p_topic_id
    and t.is_active = true
    and e.is_active = true
    and q.is_active = true
    and q.is_example = false
    and q.practice_order is not null;

  if v_total_questions = 0 then raise exception 'active exercise bank topic not found'; end if;
  v_total_sets := ceil(v_total_questions / 5.0)::integer;
  if p_set_number > v_total_sets then raise exception 'set not found'; end if;

  select p.last_advanced_set_number
  into v_last_advanced
  from public.user_exercise_bank_topic_progress p
  where p.user_id = p_user_id and p.topic_id = p_topic_id;
  v_last_advanced := coalesce(v_last_advanced, 0);
  if p_set_number > v_last_advanced + 1 then
    raise exception 'sets must be advanced sequentially';
  end if;

  insert into public.user_exercise_bank_topic_progress (
    user_id,
    topic_id,
    active_set_number,
    active_set_position,
    active_view,
    last_advanced_set_number,
    first_completed_at,
    completed_content_version,
    version_completed_at
  ) values (
    p_user_id,
    p_topic_id,
    least(p_set_number + 1, v_total_sets),
    1,
    case when p_set_number < v_total_sets then 'question' else 'results' end,
    p_set_number,
    case when p_set_number = v_total_sets then v_now else null end,
    case when p_set_number = v_total_sets then v_content_version else null end,
    case when p_set_number = v_total_sets then v_now else null end
  )
  on conflict (user_id, topic_id) do update set
    last_advanced_set_number = case
      when p_set_number <= public.user_exercise_bank_topic_progress.last_advanced_set_number
        then public.user_exercise_bank_topic_progress.last_advanced_set_number
      when p_set_number = public.user_exercise_bank_topic_progress.last_advanced_set_number + 1
        then p_set_number
      else public.user_exercise_bank_topic_progress.last_advanced_set_number
    end,
    active_set_number = case
      when p_set_number = public.user_exercise_bank_topic_progress.last_advanced_set_number + 1
        then least(p_set_number + 1, v_total_sets)
      else public.user_exercise_bank_topic_progress.active_set_number
    end,
    active_set_position = case
      when p_set_number = public.user_exercise_bank_topic_progress.last_advanced_set_number + 1
        then 1
      else public.user_exercise_bank_topic_progress.active_set_position
    end,
    active_view = case
      when p_set_number = public.user_exercise_bank_topic_progress.last_advanced_set_number + 1
        then case when p_set_number < v_total_sets then 'question' else 'results' end
      else public.user_exercise_bank_topic_progress.active_view
    end,
    first_completed_at = case
      when p_set_number = v_total_sets and v_last_advanced < v_total_sets
        then v_now
      else public.user_exercise_bank_topic_progress.first_completed_at
    end,
    completed_content_version = case
      when p_set_number = v_total_sets
        then greatest(coalesce(public.user_exercise_bank_topic_progress.completed_content_version, 0), v_content_version)
      else public.user_exercise_bank_topic_progress.completed_content_version
    end,
    version_completed_at = case
      when p_set_number = v_total_sets and v_last_advanced < v_total_sets
        then v_now
      else public.user_exercise_bank_topic_progress.version_completed_at
    end
  returning * into v_progress;

  return jsonb_build_object(
    'topic_id', p_topic_id,
    'advanced_set_number', p_set_number,
    'last_advanced_set_number', v_progress.last_advanced_set_number,
    'active_set_number', v_progress.active_set_number,
    'active_set_position', v_progress.active_set_position,
    'active_view', v_progress.active_view,
    'topic_complete', v_progress.last_advanced_set_number >= v_total_sets
  );
end;
$$;

revoke all on function public.save_exercise_bank_v2_cursor(uuid, bigint, integer, smallint, text) from public, anon, authenticated;
grant execute on function public.save_exercise_bank_v2_cursor(uuid, bigint, integer, smallint, text) to service_role;

revoke all on function public.advance_exercise_bank_v2_set(uuid, bigint, integer) from public, anon, authenticated;
grant execute on function public.advance_exercise_bank_v2_set(uuid, bigint, integer) to service_role;
