-- Reorder Exercise Bank v2 questions with a best-effort rule that avoids
-- consecutive questions of the same exercise_type.
--
-- This is a MANUAL MAINTENANCE SCRIPT, not a migration. Each execution creates
-- a new random order. Run it only when you intentionally want to reshuffle.
--
-- By default it processes every active topic. To process one topic, replace
-- `null::bigint` below with its numeric topic id, for example `42::bigint`.
--
-- The script also:
--   * excludes examples and inactive questions/exercises/topics;
--   * preserves answer attempts and latest submitted answers;
--   * reconciles saved question-state set positions with the new order;
--   * resets explicit set-completion and resume cursors for affected topics;
--   * increments each affected topic's content_version.

begin;

create temporary table exercise_bank_reorder_config (
  topic_id bigint null
) on commit drop;

insert into exercise_bank_reorder_config (topic_id)
values (null::bigint); -- Change null to a topic id to reorder only that topic.

create temporary table exercise_bank_reorder_topics (
  topic_id bigint primary key
) on commit drop;

insert into exercise_bank_reorder_topics (topic_id)
select distinct t.id
from public.exercise_bank_topics t
cross join exercise_bank_reorder_config config
where t.is_active = true
  and (config.topic_id is null or t.id = config.topic_id)
  and exists (
    select 1
    from public.exercise_bank_exercises e
    join public.exercise_bank_questions q on q.exercise_id = e.id
    where e.topic_id = t.id
      and e.is_active = true
      and q.is_active = true
      and q.is_example = false
  );

do $$
begin
  if not exists (select 1 from exercise_bank_reorder_topics) then
    raise exception 'No active Exercise Bank topics matched the configured scope.';
  end if;
end;
$$;

create temporary table exercise_bank_new_question_order (
  question_id bigint primary key,
  topic_id bigint not null,
  practice_order integer not null,
  exercise_type text not null
) on commit drop;

with recursive
candidates as (
  select
    q.id as question_id,
    e.topic_id,
    e.exercise_type
  from public.exercise_bank_questions q
  join public.exercise_bank_exercises e on e.id = q.exercise_id
  join exercise_bank_reorder_topics scope on scope.topic_id = e.topic_id
  where q.is_active = true
    and q.is_example = false
    and e.is_active = true
),
ordering as (
  select
    topic_id,
    array[]::bigint[] as chosen_question_ids,
    null::text as previous_exercise_type,
    0 as question_count
  from exercise_bank_reorder_topics

  union all

  select
    current_order.topic_id,
    current_order.chosen_question_ids || next_question.question_id,
    next_question.exercise_type,
    current_order.question_count + 1
  from ordering current_order
  join lateral (
    select candidate.question_id, candidate.exercise_type
    from candidates candidate
    where candidate.topic_id = current_order.topic_id
      and not candidate.question_id = any(current_order.chosen_question_ids)
    order by
      case
        when candidate.exercise_type is distinct from current_order.previous_exercise_type
          then 0
        else 1
      end,
      (
        select count(*)
        from candidates remaining
        where remaining.topic_id = current_order.topic_id
          and remaining.exercise_type = candidate.exercise_type
          and not remaining.question_id = any(current_order.chosen_question_ids)
      ) desc,
      random()
    limit 1
  ) next_question on true
),
final_order as (
  select distinct on (topic_id)
    topic_id,
    chosen_question_ids
  from ordering
  order by topic_id, question_count desc
),
numbered as (
  select
    final_order.topic_id,
    ordered_question.question_id,
    ordered_question.practice_order::integer
  from final_order
  cross join lateral unnest(final_order.chosen_question_ids)
    with ordinality as ordered_question(question_id, practice_order)
)
insert into exercise_bank_new_question_order (
  question_id,
  topic_id,
  practice_order,
  exercise_type
)
select
  numbered.question_id,
  numbered.topic_id,
  numbered.practice_order,
  candidates.exercise_type
from numbered
join candidates on candidates.question_id = numbered.question_id;

do $$
declare
  expected_count integer;
  ordered_count integer;
begin
  select count(*) into expected_count
  from public.exercise_bank_questions q
  join public.exercise_bank_exercises e on e.id = q.exercise_id
  join exercise_bank_reorder_topics scope on scope.topic_id = e.topic_id
  where q.is_active = true and q.is_example = false and e.is_active = true;

  select count(*) into ordered_count from exercise_bank_new_question_order;

  if ordered_count <> expected_count then
    raise exception 'Ordering produced % questions; expected %.', ordered_count, expected_count;
  end if;
end;
$$;

update public.exercise_bank_questions question
set practice_order = new_order.practice_order
from exercise_bank_new_question_order new_order
where question.id = new_order.question_id;

-- Reordering changes the published question sequence.
update public.exercise_bank_topics topic
set content_version = topic.content_version + 1
from exercise_bank_reorder_topics scope
where topic.id = scope.topic_id;

-- Move existing state rows temporarily out of the normal set-number range so
-- reassignment cannot hit the unique (user, topic, set, position) constraint.
update public.user_exercise_bank_question_state state
set set_number = state.set_number + 1000000
from exercise_bank_reorder_topics scope
where state.topic_id = scope.topic_id;

update public.user_exercise_bank_question_state state
set
  set_number = ((new_order.practice_order - 1) / 5) + 1,
  set_position = (((new_order.practice_order - 1) % 5) + 1)::smallint,
  assigned_content_version = topic.content_version
from exercise_bank_new_question_order new_order
join public.exercise_bank_topics topic on topic.id = new_order.topic_id
where state.question_id = new_order.question_id;

-- State for questions no longer in the active published pool is not useful for
-- resuming or set assignment. The append-only attempt audit remains preserved.
delete from public.user_exercise_bank_question_state state
using exercise_bank_reorder_topics scope
where state.topic_id = scope.topic_id
  and not exists (
    select 1
    from exercise_bank_new_question_order new_order
    where new_order.question_id = state.question_id
  );

-- A reshuffle invalidates the prior set boundary and exact-position cursor.
-- Answers remain available, but the learner must explicitly advance through
-- the newly ordered sets again.
update public.user_exercise_bank_topic_progress progress
set
  active_set_number = 1,
  active_set_position = 1,
  active_view = 'question',
  last_advanced_set_number = 0,
  first_completed_at = null,
  completed_content_version = null,
  version_completed_at = null
from exercise_bank_reorder_topics scope
where progress.topic_id = scope.topic_id;

-- Verification output. unavoidable_repeat_pairs is zero whenever the available
-- type counts permit perfect alternation.
with ordered as (
  select
    new_order.topic_id,
    new_order.practice_order,
    new_order.exercise_type,
    lag(new_order.exercise_type) over (
      partition by new_order.topic_id
      order by new_order.practice_order
    ) as previous_exercise_type
  from exercise_bank_new_question_order new_order
)
select
  topic.id as topic_id,
  topic.display_title,
  topic.sort_order,
  count(*) as question_count,
  count(*) filter (
    where ordered.exercise_type = ordered.previous_exercise_type
  ) as unavoidable_repeat_pairs,
  string_agg(ordered.exercise_type, ' → ' order by ordered.practice_order) as type_sequence
from ordered
join public.exercise_bank_topics topic on topic.id = ordered.topic_id
group by topic.id, topic.display_title, topic.sort_order
order by topic.sort_order nulls last, topic.id;

commit;
