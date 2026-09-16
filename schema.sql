

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE EXTENSION IF NOT EXISTS "pgsodium";






COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgjwt" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE TYPE "public"."exercise_kind" AS ENUM (
    'fill_blank',
    'sentence_transform',
    'multiple_choice',
    'open'
);


ALTER TYPE "public"."exercise_kind" OWNER TO "postgres";


CREATE TYPE "public"."section_type" AS ENUM (
    'backstory',
    'apply',
    'understand',
    'extra_tip',
    'common_mistake',
    'practice',
    'culture_note',
    'pinned_comment',
    'conversation',
    'prepare'
);


ALTER TYPE "public"."section_type" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."advance_exercise_bank_v2_set"("p_user_id" "uuid", "p_topic_id" bigint, "p_set_number" integer) RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
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


ALTER FUNCTION "public"."advance_exercise_bank_v2_set"("p_user_id" "uuid", "p_topic_id" bigint, "p_set_number" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."consume_auth_signup_rate_limit"("p_key" "text", "p_limit" integer, "p_window_seconds" integer) RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  next_count integer;
begin
  if p_key is null
     or p_key = ''
     or p_limit < 1
     or p_window_seconds < 1 then
    raise exception 'Invalid rate-limit arguments';
  end if;

  insert into public.auth_signup_rate_limits (
    rate_limit_key,
    window_started_at,
    request_count,
    updated_at
  )
  values (p_key, now(), 1, now())
  on conflict (rate_limit_key) do update
  set
    request_count = case
      when auth_signup_rate_limits.window_started_at
        <= now() - make_interval(secs => p_window_seconds)
      then 1
      else auth_signup_rate_limits.request_count + 1
    end,
    window_started_at = case
      when auth_signup_rate_limits.window_started_at
        <= now() - make_interval(secs => p_window_seconds)
      then now()
      else auth_signup_rate_limits.window_started_at
    end,
    updated_at = now()
  returning request_count into next_count;

  return next_count <= p_limit;
end;
$$;


ALTER FUNCTION "public"."consume_auth_signup_rate_limit"("p_key" "text", "p_limit" integer, "p_window_seconds" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_exercise_bank_v2_session"("p_user_id" "uuid", "p_topic_id" bigint, "p_set_number" integer DEFAULT NULL::integer) RETURNS "jsonb"
    LANGUAGE "plpgsql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
declare
  v_topic public.exercise_bank_topics%rowtype;
  v_progress public.user_exercise_bank_topic_progress%rowtype;
  v_total_questions integer;
  v_total_sets integer;
  v_mastered_questions integer;
  v_completed_sets integer;
  v_set_number integer;
  v_sets jsonb;
  v_questions jsonb;
begin
  if p_user_id is null then
    raise exception 'user_id is required';
  end if;

  select *
  into v_topic
  from public.exercise_bank_topics
  where id = p_topic_id
    and is_active = true;

  if not found then
    return null;
  end if;

  select count(*)::integer
  into v_total_questions
  from public.exercise_bank_questions q
  join public.exercise_bank_exercises e
    on e.id = q.exercise_id
  where e.topic_id = p_topic_id
    and e.is_active = true
    and q.is_active = true
    and q.is_example = false
    and q.practice_order is not null
    and q.practice_order > 0;

  v_total_sets :=
    ceil(v_total_questions / 5.0)::integer;

  select *
  into v_progress
  from public.user_exercise_bank_topic_progress
  where user_id = p_user_id
    and topic_id = p_topic_id;

  v_completed_sets := least(
    greatest(
      coalesce(v_progress.last_advanced_set_number, 0),
      0
    ),
    v_total_sets
  );

  v_set_number := coalesce(
    p_set_number,
    least(
      greatest(
        coalesce(
          v_progress.active_set_number,
          v_completed_sets + 1
        ),
        1
      ),
      greatest(v_total_sets, 1)
    )
  );

  if v_total_sets = 0 then
    v_set_number := null;
  end if;

  if v_set_number is not null
     and (
       v_set_number < 1
       or v_set_number > v_total_sets
     )
  then
    raise exception 'set not found';
  end if;

  select count(*)::integer
  into v_mastered_questions
  from public.user_exercise_bank_question_state s
  join public.exercise_bank_questions q
    on q.id = s.question_id
  join public.exercise_bank_exercises e
    on e.id = q.exercise_id
  where s.user_id = p_user_id
    and s.has_answered_correctly = true
    and e.topic_id = p_topic_id
    and e.is_active = true
    and q.is_active = true
    and q.is_example = false
    and q.practice_order is not null
    and q.practice_order > 0;

  select coalesce(
    jsonb_agg(row_data order by set_number),
    '[]'::jsonb
  )
  into v_sets
  from (
    select
      ((q.practice_order - 1) / 5 + 1)::integer
        as set_number,

      jsonb_build_object(
        'set_number',
        ((q.practice_order - 1) / 5 + 1)::integer,

        'question_count',
        count(*)::integer,

        'attempted_questions',
        (
          count(*) filter (
            where coalesce(s.attempt_count, 0) > 0
          )
        )::integer,

        'mastered_questions',
        (
          count(*) filter (
            where s.has_answered_correctly = true
          )
        )::integer,

        'is_complete',
        ((q.practice_order - 1) / 5 + 1)
          <= v_completed_sets
      ) as row_data

    from public.exercise_bank_questions q
    join public.exercise_bank_exercises e
      on e.id = q.exercise_id
    left join public.user_exercise_bank_question_state s
      on s.question_id = q.id
     and s.user_id = p_user_id

    where e.topic_id = p_topic_id
      and e.is_active = true
      and q.is_active = true
      and q.is_example = false
      and q.practice_order is not null
      and q.practice_order > 0

    group by ((q.practice_order - 1) / 5 + 1)
  ) grouped_sets;

  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'id',
        q.id,

        'source_number',
        q.source_number,

        'practice_order',
        q.practice_order,

        'exercise_id',
        e.id,

        'exercise_type',
        e.exercise_type,

        'display_type',
        e.display_type,

        'display_type_th',
        e.display_type_th,

        'prompt',
        e.prompt,

        'prompt_th',
        e.prompt_th,

        'keywords',
        e.keywords,

        'content',
        q.content,

        'content_th',
        q.content_th,

        'state',
        case
          when s.id is null then null
          else jsonb_build_object(
            'attempt_count',
            s.attempt_count,

            'has_answered_correctly',
            s.has_answered_correctly,

            'latest_user_answer',
            s.latest_user_answer,

            'latest_is_correct',
            s.latest_is_correct,

            'latest_ai_score',
            s.latest_ai_score,

            'latest_ai_feedback_en',
            s.latest_ai_feedback_en,

            'latest_ai_feedback_th',
            s.latest_ai_feedback_th,

            'last_attempted_at',
            s.last_attempted_at
          )
        end,

        'examples',
        coalesce(
          (
            select jsonb_agg(
              jsonb_build_object(
                'id',
                ex.id,

                'content',
                ex.content,

                'content_th',
                ex.content_th
              )
              order by ex.sort_order, ex.id
            )
            from public.exercise_bank_questions ex
            where ex.exercise_id = e.id
              and ex.is_active = true
              and ex.is_example = true
          ),
          '[]'::jsonb
        )
      )
      order by q.practice_order
    ),
    '[]'::jsonb
  )
  into v_questions
  from public.exercise_bank_questions q
  join public.exercise_bank_exercises e
    on e.id = q.exercise_id
  left join public.user_exercise_bank_question_state s
    on s.question_id = q.id
   and s.user_id = p_user_id
  where e.topic_id = p_topic_id
    and e.is_active = true
    and q.is_active = true
    and q.is_example = false
    and q.practice_order between
      ((v_set_number - 1) * 5 + 1)
      and (v_set_number * 5);

  return jsonb_build_object(
    'topic',
    jsonb_build_object(
      'id',
      v_topic.id,

      'topic',
      v_topic.topic,

      'topic_th',
      v_topic.topic_th,

      'display_title',
      v_topic.display_title,

      'display_title_th',
      v_topic.display_title_th,

      'category',
      v_topic.category,

      'sub_category',
      v_topic.sub_category,

      'lesson_external_id',
      v_topic.lesson_external_id,

      'sort_order',
      v_topic.sort_order,

      'is_featured',
      v_topic.is_featured,

      'featured_sort_order',
      v_topic.featured_sort_order,

      'content_version',
      v_topic.content_version
    ),

    'progress',
    jsonb_build_object(
      'total_questions',
      v_total_questions,

      'total_sets',
      v_total_sets,

      'mastered_questions',
      v_mastered_questions,

      'completed_sets',
      v_completed_sets,

      'is_completed',
      v_total_sets > 0
      and v_completed_sets >= v_total_sets,

      'is_current_version_completed',
      v_total_sets > 0
      and v_completed_sets >= v_total_sets
      and coalesce(
        v_progress.completed_content_version,
        0
      ) >= v_topic.content_version,

      'has_new_content',
      v_total_sets > 0
      and v_completed_sets >= v_total_sets
      and v_progress.completed_content_version is not null
      and v_progress.completed_content_version
        < v_topic.content_version,

      'active_set_number',
      coalesce(
        v_progress.active_set_number,
        v_completed_sets + 1
      ),

      'active_set_position',
      coalesce(
        v_progress.active_set_position,
        1
      ),

      'active_view',
      case
        when v_progress.active_view in (
          'question',
          'results'
        )
          then v_progress.active_view
        else 'question'
      end,

      'last_advanced_set_number',
      v_completed_sets,

      'first_completed_at',
      v_progress.first_completed_at,

      'completed_content_version',
      v_progress.completed_content_version,

      'version_completed_at',
      v_progress.version_completed_at
    ),

    'sets',
    v_sets,

    'set_number',
    v_set_number,

    'questions',
    v_questions
  );
end;
$$;


ALTER FUNCTION "public"."get_exercise_bank_v2_session"("p_user_id" "uuid", "p_topic_id" bigint, "p_set_number" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_exercise_bank_v2_topic_summaries"("p_user_id" "uuid", "p_category" "text" DEFAULT NULL::"text", "p_featured_only" boolean DEFAULT false) RETURNS "jsonb"
    LANGUAGE "sql" STABLE SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
  with eligible_questions as (
    select e.topic_id, q.id
    from public.exercise_bank_questions q
    join public.exercise_bank_exercises e
      on e.id = q.exercise_id
    where e.is_active = true
      and q.is_active = true
      and q.is_example = false
      and q.practice_order is not null
      and q.practice_order > 0
  ),
  question_totals as (
    select
      topic_id,
      count(*)::integer as total_questions
    from eligible_questions
    group by topic_id
  ),
  mastery as (
    select
      eq.topic_id,
      count(*)::integer as mastered_questions
    from eligible_questions eq
    join public.user_exercise_bank_question_state s
      on s.question_id = eq.id
     and s.user_id = p_user_id
     and s.has_answered_correctly = true
    group by eq.topic_id
  )
  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'id', t.id,
        'topic', t.topic,
        'topic_th', t.topic_th,
        'display_title', t.display_title,
        'display_title_th', t.display_title_th,
        'category', t.category,
        'sub_category', t.sub_category,
        'lesson_external_id', t.lesson_external_id,
        'sort_order', t.sort_order,
        'is_featured', t.is_featured,
        'featured_sort_order', t.featured_sort_order,
        'content_version', t.content_version,
        'progress', jsonb_build_object(
          'total_questions',
          coalesce(qt.total_questions, 0),

          'total_sets',
          ceil(coalesce(qt.total_questions, 0) / 5.0)::integer,

          'mastered_questions',
          coalesce(m.mastered_questions, 0),

          'completed_sets',
          least(
            greatest(coalesce(p.last_advanced_set_number, 0), 0),
            ceil(coalesce(qt.total_questions, 0) / 5.0)::integer
          ),

          'is_completed',
          coalesce(qt.total_questions, 0) > 0
          and coalesce(p.last_advanced_set_number, 0)
            >= ceil(qt.total_questions / 5.0)::integer,

          'is_current_version_completed',
          coalesce(qt.total_questions, 0) > 0
          and coalesce(p.last_advanced_set_number, 0)
            >= ceil(qt.total_questions / 5.0)::integer
          and coalesce(p.completed_content_version, 0)
            >= t.content_version,

          'has_new_content',
          coalesce(qt.total_questions, 0) > 0
          and coalesce(p.last_advanced_set_number, 0)
            >= ceil(qt.total_questions / 5.0)::integer
          and p.completed_content_version is not null
          and p.completed_content_version < t.content_version,

          'active_set_number',
          least(
            greatest(
              coalesce(
                p.active_set_number,
                coalesce(p.last_advanced_set_number, 0) + 1
              ),
              1
            ),
            greatest(
              ceil(coalesce(qt.total_questions, 0) / 5.0)::integer,
              1
            )
          ),

          'active_set_position',
          least(
            greatest(coalesce(p.active_set_position, 1), 1),
            5
          ),

          'active_view',
          case
            when p.active_view in ('question', 'results')
              then p.active_view
            else 'question'
          end,

          'last_advanced_set_number',
          least(
            greatest(coalesce(p.last_advanced_set_number, 0), 0),
            ceil(coalesce(qt.total_questions, 0) / 5.0)::integer
          ),

          'first_completed_at',
          p.first_completed_at,

          'completed_content_version',
          p.completed_content_version,

          'version_completed_at',
          p.version_completed_at
        )
      )
      order by t.sort_order, t.id
    ),
    '[]'::jsonb
  )
  from public.exercise_bank_topics t
  left join question_totals qt
    on qt.topic_id = t.id
  left join mastery m
    on m.topic_id = t.id
  left join public.user_exercise_bank_topic_progress p
    on p.topic_id = t.id
   and p.user_id = p_user_id
  where t.is_active = true
    and (
      p_category is null
      or t.category = p_category
    )
    and (
      not p_featured_only
      or t.is_featured = true
    );
$$;


ALTER FUNCTION "public"."get_exercise_bank_v2_topic_summaries"("p_user_id" "uuid", "p_category" "text", "p_featured_only" boolean) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."handle_new_user"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
  INSERT INTO public.users (
    id,
    email,
    created_at,
    username,
    avatar_image,
    is_active,
    is_verified,
    onboarding_completed
  )
  VALUES (
    NEW.id,
    NEW.email,
    NEW.created_at,
    NEW.email,
    '/images/characters/avatar_1.webp',
    true, -- active from signup
    NEW.email_confirmed_at IS NOT NULL,
    false
  )
  ON CONFLICT (id) DO NOTHING;

  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."handle_new_user"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."is_valid_speaking_coach_focus_items"("items" "jsonb") RETURNS boolean
    LANGUAGE "plpgsql" IMMUTABLE
    AS $$
declare
    item jsonb;
begin
    if items is null or jsonb_typeof(items) <> 'array' then
        return false;
    end if;

    for item in
        select value
        from jsonb_array_elements(items)
    loop
        if jsonb_typeof(item) <> 'object' then
            return false;
        end if;

        if jsonb_typeof(item -> 'priority') is distinct from 'number' then
            return false;
        end if;

        if (item ->> 'priority') not in ('1', '2', '3') then
            return false;
        end if;

        if jsonb_typeof(item -> 'instruction') is distinct from 'string' then
            return false;
        end if;

        if nullif(btrim(item ->> 'instruction'), '') is null then
            return false;
        end if;
    end loop;

    return true;
end;
$$;


ALTER FUNCTION "public"."is_valid_speaking_coach_focus_items"("items" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."pricing_tiers_set_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
begin
  new.updated_at = now();
  return new;
end;
$$;


ALTER FUNCTION "public"."pricing_tiers_set_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."record_exercise_bank_v2_attempt"("p_user_id" "uuid", "p_question_id" bigint, "p_user_answer" "text", "p_is_correct" boolean, "p_grading_method" "text", "p_ai_score" numeric DEFAULT NULL::numeric, "p_ai_feedback_en" "text" DEFAULT NULL::"text", "p_ai_feedback_th" "text" DEFAULT NULL::"text", "p_ai_model" "text" DEFAULT NULL::"text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
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


ALTER FUNCTION "public"."record_exercise_bank_v2_attempt"("p_user_id" "uuid", "p_question_id" bigint, "p_user_answer" "text", "p_is_correct" boolean, "p_grading_method" "text", "p_ai_score" numeric, "p_ai_feedback_en" "text", "p_ai_feedback_th" "text", "p_ai_model" "text") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."record_exercise_bank_v2_attempt"("p_user_id" "uuid", "p_question_id" bigint, "p_user_answer" "text", "p_is_correct" boolean, "p_grading_method" "text", "p_ai_score" numeric, "p_ai_feedback_en" "text", "p_ai_feedback_th" "text", "p_ai_model" "text") IS 'Backend-only transactional write for one Exercise Bank v2 attempt, sticky question mastery, and topic completion.';



CREATE OR REPLACE FUNCTION "public"."save_exercise_bank_v2_cursor"("p_user_id" "uuid", "p_topic_id" bigint, "p_set_number" integer, "p_set_position" smallint, "p_view" "text") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public'
    AS $$
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


ALTER FUNCTION "public"."save_exercise_bank_v2_cursor"("p_user_id" "uuid", "p_topic_id" bigint, "p_set_number" integer, "p_set_position" smallint, "p_view" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."set_exercise_bank_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    SET "search_path" TO 'public'
    AS $$
begin
  new.updated_at = now();
  return new;
end;
$$;


ALTER FUNCTION "public"."set_exercise_bank_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."set_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;


ALTER FUNCTION "public"."set_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."sync_email_verification"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
  -- When email_confirmed_at is set (not null), update users table
  IF NEW.email_confirmed_at IS NOT NULL AND (OLD.email_confirmed_at IS NULL OR OLD.email_confirmed_at IS DISTINCT FROM NEW.email_confirmed_at) THEN
    UPDATE public.users
    SET is_verified = true
    WHERE id = NEW.id;
  END IF;
  
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."sync_email_verification"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_touch_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
begin
  new.updated_at := now();
  return new;
end;
$$;


ALTER FUNCTION "public"."trg_touch_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_timestamp_column"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
begin
  new.updated_at = now();
  return new;
end;
$$;


ALTER FUNCTION "public"."update_timestamp_column"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."audio_snippets" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "lesson_external_id" "text" NOT NULL,
    "section" "text" NOT NULL,
    "seq" smallint NOT NULL,
    "character" "text",
    "storage_path" "text" NOT NULL,
    "audio_key" "text",
    "seq_suffix" numeric DEFAULT 0 NOT NULL,
    "common_mistake_id" "uuid",
    CONSTRAINT "audio_snippets_section_check" CHECK (("section" = ANY (ARRAY['practice'::"text", 'common_mistake'::"text", 'culture_note'::"text", 'understand'::"text", 'extra_tip'::"text", 'apply'::"text", 'prepare'::"text"])))
);


ALTER TABLE "public"."audio_snippets" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."auth_signup_rate_limits" (
    "rate_limit_key" "text" NOT NULL,
    "window_started_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "request_count" integer DEFAULT 1 NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "auth_signup_rate_limits_request_count_check" CHECK (("request_count" > 0))
);


ALTER TABLE "public"."auth_signup_rate_limits" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."comments" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "lesson_id" "uuid" NOT NULL,
    "user_id" "uuid" NOT NULL,
    "body" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "parent_comment_id" "uuid",
    "pinned" boolean DEFAULT false NOT NULL,
    "body_th" "text"
);


ALTER TABLE "public"."comments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."common_mistakes" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "mistake_code" "text" NOT NULL,
    "title" "text" NOT NULL,
    "title_th" "text",
    "slug" "text",
    "lesson_id" "uuid" NOT NULL,
    "lesson_external_id" "text",
    "sort_order" integer DEFAULT 0 NOT NULL,
    "content_jsonb" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "content_jsonb_th" "jsonb",
    "scm" boolean DEFAULT false NOT NULL,
    "is_published" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."common_mistakes" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."comprehension_questions" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "lesson_id" "uuid" NOT NULL,
    "prompt" "text",
    "answer_key" "jsonb",
    "sort_order" integer DEFAULT 0,
    "prompt_th" "text",
    "answer_key_th" "jsonb",
    "options" "jsonb" DEFAULT '[]'::"jsonb",
    "options_th" "jsonb",
    CONSTRAINT "cq_prompt_either_nonempty" CHECK (((COALESCE(NULLIF("btrim"("prompt"), ''::"text"), ''::"text") <> ''::"text") OR (COALESCE(NULLIF("btrim"("prompt_th"), ''::"text"), ''::"text") <> ''::"text")))
);


ALTER TABLE "public"."comprehension_questions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."contact_messages" (
    "id" bigint NOT NULL,
    "email" "text" NOT NULL,
    "ip_address" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "user_agent" "text",
    "subject" "text",
    "message" "text" NOT NULL
);


ALTER TABLE "public"."contact_messages" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."contact_messages_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "public"."contact_messages_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."contact_messages_id_seq" OWNED BY "public"."contact_messages"."id";



CREATE TABLE IF NOT EXISTS "public"."daily_app_open_checkins" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "opened_on" "date" NOT NULL,
    "timezone" "text" DEFAULT 'UTC'::"text" NOT NULL,
    "checked_in_at" timestamp with time zone DEFAULT "timezone"('utc'::"text", "now"()) NOT NULL,
    "created_at" timestamp with time zone DEFAULT "timezone"('utc'::"text", "now"()) NOT NULL
);


ALTER TABLE "public"."daily_app_open_checkins" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."debug_admin_user_lesson_progress_backup_20260630" (
    "id" bigint,
    "user_id" "uuid",
    "lesson_id" "uuid",
    "is_completed" boolean,
    "completed_at" timestamp with time zone,
    "started_at" timestamp with time zone,
    "last_unit_type" "text",
    "last_unit_key" "text",
    "updated_at" timestamp with time zone
);


ALTER TABLE "public"."debug_admin_user_lesson_progress_backup_20260630" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."enum_labels" (
    "enum_value" "text" NOT NULL,
    "lang_code" "text" NOT NULL,
    "label" "text" NOT NULL
);


ALTER TABLE "public"."enum_labels" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."exercise_bank" (
    "id" bigint NOT NULL,
    "category" "text" NOT NULL,
    "section" "text" NOT NULL,
    "exercise_type" "text" NOT NULL,
    "title" "text",
    "title_th" "text",
    "prompt" "text",
    "prompt_th" "text",
    "items" "jsonb" NOT NULL,
    "items_th" "jsonb",
    "is_featured" boolean DEFAULT false,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "section_th" "text",
    "sort_order" integer
);


ALTER TABLE "public"."exercise_bank" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."exercise_bank_exercises" (
    "id" bigint NOT NULL,
    "topic_id" bigint NOT NULL,
    "source_key" "text" NOT NULL,
    "exercise_type" "text" NOT NULL,
    "display_type" "text" NOT NULL,
    "difficulty" "text",
    "prompt" "text" NOT NULL,
    "keywords" "text"[],
    "sort_order" integer NOT NULL,
    "is_active" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "display_type_th" "text",
    "prompt_th" "text"
);


ALTER TABLE "public"."exercise_bank_exercises" OWNER TO "postgres";


ALTER TABLE "public"."exercise_bank_exercises" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."exercise_bank_exercises_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE SEQUENCE IF NOT EXISTS "public"."exercise_bank_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "public"."exercise_bank_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."exercise_bank_id_seq" OWNED BY "public"."exercise_bank"."id";



CREATE TABLE IF NOT EXISTS "public"."exercise_bank_questions" (
    "id" bigint NOT NULL,
    "exercise_id" bigint NOT NULL,
    "source_key" "text" NOT NULL,
    "source_number" "text",
    "is_example" boolean DEFAULT false NOT NULL,
    "sort_order" integer NOT NULL,
    "content" "jsonb" NOT NULL,
    "is_active" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "practice_order" integer,
    "content_th" "jsonb",
    CONSTRAINT "exercise_bank_questions_content_object" CHECK (("jsonb_typeof"("content") = 'object'::"text")),
    CONSTRAINT "exercise_bank_questions_content_th_object" CHECK ((("content_th" IS NULL) OR ("jsonb_typeof"("content_th") = 'object'::"text")))
);


ALTER TABLE "public"."exercise_bank_questions" OWNER TO "postgres";


ALTER TABLE "public"."exercise_bank_questions" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."exercise_bank_questions_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."exercise_bank_topics" (
    "id" bigint NOT NULL,
    "source_key" "text" NOT NULL,
    "source_document_id" "text" NOT NULL,
    "source_tab_id" "text" NOT NULL,
    "source_tab_title" "text" NOT NULL,
    "source_tab_order" integer NOT NULL,
    "topic" "text" NOT NULL,
    "display_title" "text" NOT NULL,
    "category" "text" NOT NULL,
    "sub_category" "text",
    "lesson_external_id" "text" NOT NULL,
    "sort_order" integer DEFAULT 0 NOT NULL,
    "is_active" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "is_featured" boolean DEFAULT false NOT NULL,
    "featured_sort_order" integer,
    "content_version" integer DEFAULT 1 NOT NULL,
    "topic_th" "text",
    "display_title_th" "text",
    CONSTRAINT "exercise_bank_topics_content_version_positive" CHECK (("content_version" > 0))
);


ALTER TABLE "public"."exercise_bank_topics" OWNER TO "postgres";


COMMENT ON COLUMN "public"."exercise_bank_topics"."content_version" IS 'Manually incremented when the active published question pool changes. Used to preserve completion while showing newly added questions.';



ALTER TABLE "public"."exercise_bank_topics" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."exercise_bank_topics_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."featured_sections" (
    "section" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."featured_sections" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."lesson_images" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "lesson_id" "uuid",
    "image_key" "text" NOT NULL,
    "url" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "alt_text_en" "text",
    "alt_text_th" "text"
);


ALTER TABLE "public"."lesson_images" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."lesson_phrases" (
    "lesson_id" "uuid" NOT NULL,
    "phrase_id" "uuid" NOT NULL,
    "sort_order" integer DEFAULT 0,
    "audio_url" "text"
);


ALTER TABLE "public"."lesson_phrases" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."lesson_sections" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "lesson_id" "uuid" NOT NULL,
    "type" "public"."section_type" NOT NULL,
    "content" "text",
    "audio_url" "text",
    "sort_order" integer DEFAULT 0,
    "content_th" "text",
    "content_jsonb" "jsonb",
    "content_jsonb_th" "jsonb",
    "render_mode" "text" DEFAULT 'auto'::"text" NOT NULL,
    CONSTRAINT "lesson_sections_render_mode_check" CHECK (("render_mode" = ANY (ARRAY['auto'::"text", 'bilingual'::"text", 'force_en'::"text", 'force_th'::"text"])))
);


ALTER TABLE "public"."lesson_sections" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."lesson_tags" (
    "lesson_id" "uuid" NOT NULL,
    "tag_id" "uuid" NOT NULL
);


ALTER TABLE "public"."lesson_tags" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."lessons" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "title" "text",
    "title_th" "text",
    "subtitle" "text",
    "subtitle_th" "text",
    "stage" "text",
    "level" smallint,
    "image_url" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "lesson_order" integer,
    "focus" "text",
    "focus_th" "text",
    "backstory" "text",
    "backstory_th" "text",
    "conversation_audio_url" "text",
    "lesson_external_id" "text",
    "conversation_audio_url_no_bg" "text",
    "conversation_audio_url_bg" "text",
    "header_img" "text",
    "app_total_units" integer
);


ALTER TABLE "public"."lessons" OWNER TO "postgres";


COMMENT ON TABLE "public"."lessons" IS 'General Lesson Info';



CREATE TABLE IF NOT EXISTS "public"."phrases" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "phrase" "text" NOT NULL,
    "audio_url" "text",
    "content" "text",
    "variant" smallint DEFAULT 1 NOT NULL,
    "content_th" "text",
    "content_jsonb" "jsonb",
    "content_jsonb_th" "jsonb",
    "phrase_th" "text"
);


ALTER TABLE "public"."phrases" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."phrases_audio_snippets" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "phrase_id" "uuid" NOT NULL,
    "variant" integer DEFAULT 0 NOT NULL,
    "seq" integer DEFAULT 0 NOT NULL,
    "storage_path" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "audio_key" "text"
);


ALTER TABLE "public"."phrases_audio_snippets" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."placement_conversations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "conversation_order" integer NOT NULL,
    "audio_path" "text" NOT NULL,
    "questions" "jsonb" NOT NULL,
    "scoring_rules" "jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "placement_conversations_conversation_order_check" CHECK ((("conversation_order" >= 1) AND ("conversation_order" <= 3))),
    CONSTRAINT "placement_conversations_questions_check" CHECK (("jsonb_typeof"("questions") = 'array'::"text")),
    CONSTRAINT "placement_conversations_scoring_rules_check" CHECK (("jsonb_typeof"("scoring_rules") = 'array'::"text"))
);


ALTER TABLE "public"."placement_conversations" OWNER TO "postgres";


COMMENT ON TABLE "public"."placement_conversations" IS 'Audio references, questions, answer keys, and routing rules for the placement test.';



COMMENT ON COLUMN "public"."placement_conversations"."audio_path" IS 'Object path inside the placement-test-audio Storage bucket.';



CREATE TABLE IF NOT EXISTS "public"."practice_exercises" (
    "id" bigint NOT NULL,
    "lesson_id" "uuid" NOT NULL,
    "kind" "public"."exercise_kind" NOT NULL,
    "prompt_md" "text",
    "options" "jsonb" NOT NULL,
    "answer_key" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "sort_order" integer NOT NULL,
    "items" "jsonb",
    "title" "text",
    "paragraph" "text",
    "title_th" "text",
    "prompt_th" "text",
    "paragraph_th" "text",
    "items_th" "jsonb",
    "prompt_blocks" "jsonb",
    "prompt_blocks_th" "jsonb"
);


ALTER TABLE "public"."practice_exercises" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."practice_exercises_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "public"."practice_exercises_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."practice_exercises_id_seq" OWNED BY "public"."practice_exercises"."id";



ALTER TABLE "public"."practice_exercises" ALTER COLUMN "sort_order" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."practice_exercises_sort_order_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."pricing_tiers" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "region_key" "text" NOT NULL,
    "billing_period" "text" NOT NULL,
    "currency" "text" NOT NULL,
    "amount_total" numeric(10,2) NOT NULL,
    "amount_per_month" numeric(10,2) NOT NULL,
    "stripe_price_id" "text" NOT NULL,
    "active" boolean DEFAULT true NOT NULL,
    "is_promo" boolean DEFAULT false NOT NULL,
    "sort_order" integer DEFAULT 0 NOT NULL,
    "note" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "pricing_tiers_amounts_positive_check" CHECK ((("amount_total" > (0)::numeric) AND ("amount_per_month" > (0)::numeric))),
    CONSTRAINT "pricing_tiers_billing_period_check" CHECK (("billing_period" = ANY (ARRAY['monthly'::"text", '3-month'::"text", '6-month'::"text"]))),
    CONSTRAINT "pricing_tiers_currency_check" CHECK (("currency" = ANY (ARRAY['THB'::"text", 'USD'::"text"]))),
    CONSTRAINT "pricing_tiers_region_key_check" CHECK (("region_key" = ANY (ARRAY['US'::"text", 'INTL'::"text"])))
);


ALTER TABLE "public"."pricing_tiers" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."speaking_coach_practice_sets" (
    "id" bigint NOT NULL,
    "lesson_id" "uuid" NOT NULL,
    "source_key" "text" NOT NULL,
    "source_document_id" "text" NOT NULL,
    "source_tab_id" "text",
    "source_tab_title" "text",
    "source_tab_order" integer,
    "source_paragraph_index" integer,
    "practice_type" "text" NOT NULL,
    "source_practice_type" "text" NOT NULL,
    "focus" "text" NOT NULL,
    "tip_en" "text",
    "tip_th" "text",
    "sort_order" integer NOT NULL,
    "content_hash" "text",
    "is_active" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "speaking_coach_practice_sets_focus_nonempty" CHECK (("btrim"("focus") <> ''::"text")),
    CONSTRAINT "speaking_coach_practice_sets_sort_positive" CHECK (("sort_order" > 0)),
    CONSTRAINT "speaking_coach_practice_sets_type_check" CHECK (("practice_type" = ANY (ARRAY['pronunciation'::"text", 'open'::"text", 'translation'::"text"])))
);


ALTER TABLE "public"."speaking_coach_practice_sets" OWNER TO "postgres";


COMMENT ON TABLE "public"."speaking_coach_practice_sets" IS 'One authored speaking-practice block within an existing lesson. FOCUS is private evaluator configuration and must not be returned directly to the mobile client.';



ALTER TABLE "public"."speaking_coach_practice_sets" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."speaking_coach_practice_sets_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."speaking_coach_questions" (
    "id" bigint NOT NULL,
    "practice_set_id" bigint NOT NULL,
    "source_key" "text" NOT NULL,
    "source_number" "text" NOT NULL,
    "source_paragraph_index" integer,
    "sort_order" integer NOT NULL,
    "prompt_en" "text",
    "prompt_th" "text",
    "target_answers" "text"[] DEFAULT ARRAY[]::"text"[] NOT NULL,
    "examples" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "prompt_audio_key" "text",
    "content_hash" "text",
    "is_active" boolean DEFAULT true NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "focus" "text" NOT NULL,
    "focus_items" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    CONSTRAINT "speaking_coach_questions_examples_array" CHECK (("jsonb_typeof"("examples") = 'array'::"text")),
    CONSTRAINT "speaking_coach_questions_focus_items_valid" CHECK ("public"."is_valid_speaking_coach_focus_items"("focus_items")),
    CONSTRAINT "speaking_coach_questions_number_nonempty" CHECK (("btrim"("source_number") <> ''::"text")),
    CONSTRAINT "speaking_coach_questions_prompt_present" CHECK (((NULLIF("btrim"("prompt_en"), ''::"text") IS NOT NULL) OR (NULLIF("btrim"("prompt_th"), ''::"text") IS NOT NULL))),
    CONSTRAINT "speaking_coach_questions_sort_positive" CHECK (("sort_order" > 0))
);


ALTER TABLE "public"."speaking_coach_questions" OWNER TO "postgres";


COMMENT ON TABLE "public"."speaking_coach_questions" IS 'Normalized speaking prompts. target_answers are private evaluator references and must not be returned directly to the mobile client.';



COMMENT ON COLUMN "public"."speaking_coach_questions"."focus" IS 'Private question-specific evaluator rubric authored in the speaking-coach curriculum.';



COMMENT ON COLUMN "public"."speaking_coach_questions"."focus_items" IS 'Ordered evaluator focus items. Each item contains priority 1-3 and a non-empty instruction. Multiple items may share a priority; array order breaks ties.';



ALTER TABLE "public"."speaking_coach_questions" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."speaking_coach_questions_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."tags" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "name" "text" NOT NULL
);


ALTER TABLE "public"."tags" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."topic_library" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "name" "text" NOT NULL,
    "slug" "text" NOT NULL,
    "idx" integer,
    "tags" "text"[],
    "content_jsonb" "jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "name_th" "text",
    "content_jsonb_th" "jsonb",
    "subtitle" "text",
    "subtitle_th" "text",
    "is_featured" boolean DEFAULT false NOT NULL
);


ALTER TABLE "public"."topic_library" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."transcript_lines" (
    "id" "uuid" DEFAULT "extensions"."uuid_generate_v4"() NOT NULL,
    "lesson_id" "uuid" NOT NULL,
    "sort_order" integer NOT NULL,
    "speaker" "text",
    "line_text" "text" NOT NULL,
    "line_text_th" "text",
    "speaker_th" "text"
);


ALTER TABLE "public"."transcript_lines" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."user_exercise_answers" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid",
    "exercise_bank_id" bigint,
    "practice_exercise_id" bigint,
    "exercise_type" "text" NOT NULL,
    "user_answer" "text" NOT NULL,
    "ai_correct" boolean,
    "ai_score" numeric(3,2),
    "ai_feedback_en" "text",
    "ai_feedback_th" "text",
    "ai_model" "text" DEFAULT 'gpt-4o-mini'::"text",
    "feedback" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "user_exercise_answers_must_link_to_one" CHECK ((((("exercise_bank_id" IS NOT NULL))::integer + (("practice_exercise_id" IS NOT NULL))::integer) = 1))
);


ALTER TABLE "public"."user_exercise_answers" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."user_exercise_bank_question_attempts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "question_id" bigint NOT NULL,
    "user_answer" "text" NOT NULL,
    "is_correct" boolean NOT NULL,
    "grading_method" "text" NOT NULL,
    "ai_score" numeric(3,2),
    "ai_feedback_en" "text",
    "ai_feedback_th" "text",
    "ai_model" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "user_exercise_bank_question_attempts_ai_fields" CHECK ((("grading_method" = 'ai'::"text") OR (("ai_score" IS NULL) AND ("ai_feedback_en" IS NULL) AND ("ai_feedback_th" IS NULL) AND ("ai_model" IS NULL)))),
    CONSTRAINT "user_exercise_bank_question_attempts_ai_score_range" CHECK ((("ai_score" IS NULL) OR (("ai_score" >= (0)::numeric) AND ("ai_score" <= (1)::numeric)))),
    CONSTRAINT "user_exercise_bank_question_attempts_grading_method" CHECK (("grading_method" = ANY (ARRAY['deterministic'::"text", 'ai'::"text"])))
);


ALTER TABLE "public"."user_exercise_bank_question_attempts" OWNER TO "postgres";


COMMENT ON TABLE "public"."user_exercise_bank_question_attempts" IS 'Append-only Exercise Bank v2 submission log. Supports AI-grading audits without using or changing the legacy user_exercise_answers table.';



CREATE TABLE IF NOT EXISTS "public"."user_exercise_bank_question_state" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "topic_id" bigint NOT NULL,
    "question_id" bigint NOT NULL,
    "set_number" integer NOT NULL,
    "set_position" smallint NOT NULL,
    "assigned_content_version" integer NOT NULL,
    "attempt_count" integer DEFAULT 0 NOT NULL,
    "has_answered_correctly" boolean DEFAULT false NOT NULL,
    "latest_user_answer" "text",
    "latest_is_correct" boolean,
    "latest_ai_score" numeric(3,2),
    "latest_ai_feedback_en" "text",
    "latest_ai_feedback_th" "text",
    "latest_ai_model" "text",
    "first_correct_at" timestamp with time zone,
    "last_attempted_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "user_exercise_bank_question_state_ai_score_range" CHECK ((("latest_ai_score" IS NULL) OR (("latest_ai_score" >= (0)::numeric) AND ("latest_ai_score" <= (1)::numeric)))),
    CONSTRAINT "user_exercise_bank_question_state_assigned_version_positive" CHECK (("assigned_content_version" > 0)),
    CONSTRAINT "user_exercise_bank_question_state_attempt_count_nonnegative" CHECK (("attempt_count" >= 0)),
    CONSTRAINT "user_exercise_bank_question_state_correct_timestamp" CHECK ((("has_answered_correctly" = false) OR ("first_correct_at" IS NOT NULL))),
    CONSTRAINT "user_exercise_bank_question_state_set_number_positive" CHECK (("set_number" > 0)),
    CONSTRAINT "user_exercise_bank_question_state_set_position_range" CHECK ((("set_position" >= 1) AND ("set_position" <= 5)))
);


ALTER TABLE "public"."user_exercise_bank_question_state" OWNER TO "postgres";


COMMENT ON TABLE "public"."user_exercise_bank_question_state" IS 'One current-state row per user/question. Also stores the question''s stable assignment into a user-specific set of up to five.';



COMMENT ON COLUMN "public"."user_exercise_bank_question_state"."assigned_content_version" IS 'Topic content_version when this question was assigned. Supports the completed checkmark plus N new badge.';



COMMENT ON COLUMN "public"."user_exercise_bank_question_state"."has_answered_correctly" IS 'Sticky mastery flag: once true, later incorrect practice attempts must not reset it.';



CREATE TABLE IF NOT EXISTS "public"."user_exercise_bank_topic_progress" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "topic_id" bigint NOT NULL,
    "first_completed_at" timestamp with time zone,
    "completed_content_version" integer,
    "version_completed_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "active_set_number" integer DEFAULT 1 NOT NULL,
    "active_set_position" smallint DEFAULT 1 NOT NULL,
    "active_view" "text" DEFAULT 'question'::"text" NOT NULL,
    "last_advanced_set_number" integer DEFAULT 0 NOT NULL,
    CONSTRAINT "user_exercise_bank_topic_progress_active_position_range" CHECK ((("active_set_position" >= 1) AND ("active_set_position" <= 5))),
    CONSTRAINT "user_exercise_bank_topic_progress_active_set_positive" CHECK (("active_set_number" > 0)),
    CONSTRAINT "user_exercise_bank_topic_progress_active_view_valid" CHECK (("active_view" = ANY (ARRAY['question'::"text", 'results'::"text"]))),
    CONSTRAINT "user_exercise_bank_topic_progress_advanced_set_nonnegative" CHECK (("last_advanced_set_number" >= 0)),
    CONSTRAINT "user_exercise_bank_topic_progress_completion_consistent" CHECK (((("completed_content_version" IS NULL) AND ("version_completed_at" IS NULL)) OR (("completed_content_version" IS NOT NULL) AND ("version_completed_at" IS NOT NULL)))),
    CONSTRAINT "user_exercise_bank_topic_progress_version_positive" CHECK ((("completed_content_version" IS NULL) OR ("completed_content_version" > 0)))
);


ALTER TABLE "public"."user_exercise_bank_topic_progress" OWNER TO "postgres";


COMMENT ON TABLE "public"."user_exercise_bank_topic_progress" IS 'Durable topic achievement. first_completed_at is never cleared; completed_content_version advances after all questions in a newer version are mastered.';



COMMENT ON COLUMN "public"."user_exercise_bank_topic_progress"."active_set_number" IS 'The learner''s current unadvanced set. Used to resume the Exercise Bank.';



COMMENT ON COLUMN "public"."user_exercise_bank_topic_progress"."active_set_position" IS 'The exact question position to restore within active_set_number.';



COMMENT ON COLUMN "public"."user_exercise_bank_topic_progress"."active_view" IS 'Whether reopening should restore the active question or the set results screen.';



COMMENT ON COLUMN "public"."user_exercise_bank_topic_progress"."last_advanced_set_number" IS 'Highest sequential set explicitly completed by pressing the advance action.';



CREATE TABLE IF NOT EXISTS "public"."user_lesson_answer_state" (
    "id" bigint NOT NULL,
    "user_id" "uuid" NOT NULL,
    "lesson_id" "uuid" NOT NULL,
    "unit_key" "text" NOT NULL,
    "state_key" "text" DEFAULT 'default'::"text" NOT NULL,
    "answer_payload" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "timezone"('utc'::"text", "now"()) NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "timezone"('utc'::"text", "now"()) NOT NULL
);


ALTER TABLE "public"."user_lesson_answer_state" OWNER TO "postgres";


ALTER TABLE "public"."user_lesson_answer_state" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."user_lesson_answer_state_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."user_lesson_progress" (
    "id" bigint NOT NULL,
    "user_id" "uuid" NOT NULL,
    "lesson_id" "uuid" NOT NULL,
    "is_completed" boolean DEFAULT false NOT NULL,
    "completed_at" timestamp with time zone,
    "started_at" timestamp with time zone,
    "last_unit_type" "text",
    "last_unit_key" "text",
    "updated_at" timestamp with time zone DEFAULT "timezone"('utc'::"text", "now"()) NOT NULL,
    CONSTRAINT "user_lesson_progress_last_unit_type_check" CHECK ((("last_unit_type" IS NULL) OR ("last_unit_type" = ANY (ARRAY['section'::"text", 'exercise'::"text", 'page'::"text", 'card'::"text", 'example_reveal'::"text"]))))
);


ALTER TABLE "public"."user_lesson_progress" OWNER TO "postgres";


ALTER TABLE "public"."user_lesson_progress" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."user_lesson_progress_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."user_lesson_unit_progress" (
    "id" bigint NOT NULL,
    "user_id" "uuid" NOT NULL,
    "lesson_id" "uuid" NOT NULL,
    "unit_type" "text" NOT NULL,
    "unit_key" "text" NOT NULL,
    "section_key" "text",
    "is_completed" boolean DEFAULT false NOT NULL,
    "first_visited_at" timestamp with time zone DEFAULT "timezone"('utc'::"text", "now"()) NOT NULL,
    "last_visited_at" timestamp with time zone DEFAULT "timezone"('utc'::"text", "now"()) NOT NULL,
    "completed_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "timezone"('utc'::"text", "now"()) NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "timezone"('utc'::"text", "now"()) NOT NULL,
    CONSTRAINT "user_lesson_unit_progress_unit_type_check" CHECK (("unit_type" = ANY (ARRAY['section'::"text", 'exercise'::"text", 'page'::"text", 'card'::"text", 'example_reveal'::"text"])))
);


ALTER TABLE "public"."user_lesson_unit_progress" OWNER TO "postgres";


ALTER TABLE "public"."user_lesson_unit_progress" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."user_lesson_unit_progress_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."user_speaking_coach_attempts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "session_id" "uuid" NOT NULL,
    "user_id" "uuid" NOT NULL,
    "question_id" bigint NOT NULL,
    "evaluation_sequence" integer NOT NULL,
    "instructional_attempt_number" smallint NOT NULL,
    "previous_attempt_id" "uuid",
    "processing_status" "text" DEFAULT 'uploaded'::"text" NOT NULL,
    "evaluation_result" "text",
    "transcript" "text",
    "content_result" "jsonb",
    "pronunciation_result" "jsonb",
    "detected_issues" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "displayed_issues" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "corrected_answer" "text",
    "feedback_en" "text",
    "feedback_th" "text",
    "retry_focus" "text"[] DEFAULT ARRAY[]::"text"[] NOT NULL,
    "provider" "text",
    "model_used" "text",
    "prompt_version" "text",
    "evaluator_schema_version" "text",
    "evaluation_context" "jsonb",
    "provider_response_raw" "jsonb",
    "provider_output_text" "text",
    "normalized_evaluation" "jsonb",
    "usage" "jsonb",
    "latency_ms" integer,
    "failure_code" "text",
    "failure_detail" "text",
    "audio_object_path" "text",
    "audio_expires_at" timestamp with time zone,
    "audio_deleted_at" timestamp with time zone,
    "completed_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "completes_question" boolean GENERATED ALWAYS AS ((("processing_status" = 'completed'::"text") AND ("evaluation_result" = ANY (ARRAY['pass'::"text", 'continue_with_correction'::"text"])))) STORED,
    "client_submission_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    CONSTRAINT "user_speaking_coach_attempts_detected_issues_array" CHECK (("jsonb_typeof"("detected_issues") = 'array'::"text")),
    CONSTRAINT "user_speaking_coach_attempts_displayed_issues_array" CHECK (("jsonb_typeof"("displayed_issues") = 'array'::"text")),
    CONSTRAINT "user_speaking_coach_attempts_evaluation_result_check" CHECK ((("evaluation_result" IS NULL) OR ("evaluation_result" = ANY (ARRAY['pass'::"text", 'retry'::"text", 'continue_with_correction'::"text", 'unclear_audio'::"text"])))),
    CONSTRAINT "user_speaking_coach_attempts_instructional_attempt_range" CHECK ((("instructional_attempt_number" >= 1) AND ("instructional_attempt_number" <= 2))),
    CONSTRAINT "user_speaking_coach_attempts_latency_nonnegative" CHECK ((("latency_ms" IS NULL) OR ("latency_ms" >= 0))),
    CONSTRAINT "user_speaking_coach_attempts_normalized_status_matches" CHECK ((("normalized_evaluation" IS NULL) OR (("normalized_evaluation" ->> 'status'::"text") = "evaluation_result"))),
    CONSTRAINT "user_speaking_coach_attempts_previous_not_self" CHECK ((("previous_attempt_id" IS NULL) OR ("previous_attempt_id" <> "id"))),
    CONSTRAINT "user_speaking_coach_attempts_processing_state_consistent" CHECK (((("processing_status" = ANY (ARRAY['uploaded'::"text", 'evaluating'::"text"])) AND ("evaluation_result" IS NULL) AND ("normalized_evaluation" IS NULL) AND ("failure_code" IS NULL) AND ("completed_at" IS NULL)) OR (("processing_status" = 'completed'::"text") AND ("evaluation_result" IS NOT NULL) AND ("normalized_evaluation" IS NOT NULL) AND ("failure_code" IS NULL) AND ("completed_at" IS NOT NULL)) OR (("processing_status" = 'failed'::"text") AND ("evaluation_result" IS NULL) AND ("normalized_evaluation" IS NULL) AND ("failure_code" IS NOT NULL) AND ("completed_at" IS NOT NULL)))),
    CONSTRAINT "user_speaking_coach_attempts_processing_status_check" CHECK (("processing_status" = ANY (ARRAY['uploaded'::"text", 'evaluating'::"text", 'completed'::"text", 'failed'::"text"]))),
    CONSTRAINT "user_speaking_coach_attempts_sequence_positive" CHECK (("evaluation_sequence" > 0))
);


ALTER TABLE "public"."user_speaking_coach_attempts" OWNER TO "postgres";


COMMENT ON TABLE "public"."user_speaking_coach_attempts" IS 'Every submitted recording and its evaluation lifecycle. A question is complete only when completes_question is true.';



COMMENT ON COLUMN "public"."user_speaking_coach_attempts"."evaluation_sequence" IS 'Counts every recording submission, including unclear audio and provider failures.';



COMMENT ON COLUMN "public"."user_speaking_coach_attempts"."instructional_attempt_number" IS 'Counts only instructional attempts. Must remain unchanged after unclear_audio.';



COMMENT ON COLUMN "public"."user_speaking_coach_attempts"."provider_response_raw" IS 'Provider-specific response metadata for backend debugging. Must exclude raw input audio and secrets.';



COMMENT ON COLUMN "public"."user_speaking_coach_attempts"."normalized_evaluation" IS 'Validated provider-independent evaluator result. This is the canonical evaluation payload.';



COMMENT ON COLUMN "public"."user_speaking_coach_attempts"."client_submission_id" IS 'Stable UUID generated by the client for one recording submission. Reused when the same HTTP submission is retried.';



CREATE TABLE IF NOT EXISTS "public"."user_speaking_coach_sessions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "lesson_id" "uuid" NOT NULL,
    "content_hash" "text" NOT NULL,
    "status" "text" DEFAULT 'active'::"text" NOT NULL,
    "current_question_id" bigint,
    "started_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "ended_at" timestamp with time zone,
    "expires_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "user_speaking_coach_sessions_end_state_check" CHECK (((("status" = 'active'::"text") AND ("ended_at" IS NULL)) OR (("status" = ANY (ARRAY['completed'::"text", 'abandoned'::"text"])) AND ("ended_at" IS NOT NULL)))),
    CONSTRAINT "user_speaking_coach_sessions_status_check" CHECK (("status" = ANY (ARRAY['active'::"text", 'completed'::"text", 'abandoned'::"text"])))
);


ALTER TABLE "public"."user_speaking_coach_sessions" OWNER TO "postgres";


COMMENT ON TABLE "public"."user_speaking_coach_sessions" IS 'One learner run through all speaking-coach practice sets in a lesson. current_question_id is a resume hint, not the source of truth for completion.';



CREATE TABLE IF NOT EXISTS "public"."user_speaking_coach_skips" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "session_id" "uuid" NOT NULL,
    "question_id" bigint NOT NULL,
    "skipped_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."user_speaking_coach_skips" OWNER TO "postgres";


COMMENT ON TABLE "public"."user_speaking_coach_skips" IS 'Questions intentionally skipped by a learner. Backend service-role access only.';



CREATE TABLE IF NOT EXISTS "public"."users" (
    "username" character varying(50),
    "email" character varying(100) NOT NULL,
    "password_hash" character varying(255),
    "created_at" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "is_admin" boolean DEFAULT false,
    "avatar_image" character varying(255),
    "is_active" boolean DEFAULT false,
    "is_paid" boolean DEFAULT false,
    "stripe_customer_id" character varying(255),
    "stripe_subscription_id" character varying(255),
    "subscription_status" character varying(50),
    "current_period_end" timestamp with time zone,
    "is_verified" boolean DEFAULT false,
    "cancel_at_period_end" boolean DEFAULT false,
    "cancel_at" timestamp without time zone,
    "onboarding_completed" boolean DEFAULT false NOT NULL,
    "billing_provider" character varying(50),
    "daily_streak" integer DEFAULT 0 NOT NULL,
    "last_checkin_date" "date",
    "daily_streak_timezone" "text",
    "manual_membership" boolean DEFAULT false NOT NULL,
    "membership_source" "text",
    "revenuecat_environment" "text",
    "placement_level" integer,
    "placement_completed_at" timestamp with time zone,
    CONSTRAINT "users_billing_provider_check" CHECK ((("billing_provider" IS NULL) OR (("billing_provider")::"text" = ANY ((ARRAY['stripe'::character varying, 'app_store'::character varying, 'play_store'::character varying])::"text"[])))),
    CONSTRAINT "users_membership_source_check" CHECK (("membership_source" = ANY (ARRAY['manual'::"text", 'stripe'::"text", 'revenuecat'::"text"]))),
    CONSTRAINT "users_placement_level_check" CHECK ((("placement_level" IS NULL) OR ("placement_level" = ANY (ARRAY[1, 2, 5, 9, 13])))),
    CONSTRAINT "users_placement_state_check" CHECK (((("placement_level" IS NULL) AND ("placement_completed_at" IS NULL)) OR (("placement_level" IS NOT NULL) AND ("placement_completed_at" IS NOT NULL)))),
    CONSTRAINT "users_revenuecat_environment_check" CHECK (("revenuecat_environment" = ANY (ARRAY['sandbox'::"text", 'production'::"text", 'unknown'::"text"])))
);


ALTER TABLE "public"."users" OWNER TO "postgres";


COMMENT ON COLUMN "public"."users"."is_admin" IS 'admin column';



COMMENT ON COLUMN "public"."users"."placement_level" IS 'Final level assigned by the placement test.';



COMMENT ON COLUMN "public"."users"."placement_completed_at" IS 'When the user completed the placement test. Null means incomplete.';



ALTER TABLE ONLY "public"."contact_messages" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."contact_messages_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."exercise_bank" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."exercise_bank_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."practice_exercises" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."practice_exercises_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."audio_snippets"
    ADD CONSTRAINT "audio_snippets_lesson_external_id_section_seq_suffix_key" UNIQUE ("lesson_external_id", "section", "seq", "seq_suffix");



ALTER TABLE ONLY "public"."audio_snippets"
    ADD CONSTRAINT "audio_snippets_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."auth_signup_rate_limits"
    ADD CONSTRAINT "auth_signup_rate_limits_pkey" PRIMARY KEY ("rate_limit_key");



ALTER TABLE ONLY "public"."comments"
    ADD CONSTRAINT "comments_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."common_mistakes"
    ADD CONSTRAINT "common_mistakes_mistake_code_key" UNIQUE ("mistake_code");



ALTER TABLE ONLY "public"."common_mistakes"
    ADD CONSTRAINT "common_mistakes_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."common_mistakes"
    ADD CONSTRAINT "common_mistakes_slug_key" UNIQUE ("slug");



ALTER TABLE ONLY "public"."comprehension_questions"
    ADD CONSTRAINT "compq_lesson_sort_unique" UNIQUE ("lesson_id", "sort_order");



ALTER TABLE ONLY "public"."comprehension_questions"
    ADD CONSTRAINT "comprehension_questions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."contact_messages"
    ADD CONSTRAINT "contact_messages_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."daily_app_open_checkins"
    ADD CONSTRAINT "daily_app_open_checkins_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."enum_labels"
    ADD CONSTRAINT "enum_labels_pkey" PRIMARY KEY ("enum_value", "lang_code");



ALTER TABLE ONLY "public"."exercise_bank_exercises"
    ADD CONSTRAINT "exercise_bank_exercises_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."exercise_bank_exercises"
    ADD CONSTRAINT "exercise_bank_exercises_sort_unique" UNIQUE ("topic_id", "sort_order");



ALTER TABLE ONLY "public"."exercise_bank_exercises"
    ADD CONSTRAINT "exercise_bank_exercises_source_key_key" UNIQUE ("source_key");



ALTER TABLE ONLY "public"."exercise_bank"
    ADD CONSTRAINT "exercise_bank_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."exercise_bank_questions"
    ADD CONSTRAINT "exercise_bank_questions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."exercise_bank_questions"
    ADD CONSTRAINT "exercise_bank_questions_sort_unique" UNIQUE ("exercise_id", "sort_order");



ALTER TABLE ONLY "public"."exercise_bank_questions"
    ADD CONSTRAINT "exercise_bank_questions_source_key_key" UNIQUE ("source_key");



ALTER TABLE ONLY "public"."exercise_bank_topics"
    ADD CONSTRAINT "exercise_bank_topics_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."exercise_bank_topics"
    ADD CONSTRAINT "exercise_bank_topics_source_key_key" UNIQUE ("source_key");



ALTER TABLE ONLY "public"."featured_sections"
    ADD CONSTRAINT "featured_sections_pkey" PRIMARY KEY ("section");



ALTER TABLE ONLY "public"."lesson_images"
    ADD CONSTRAINT "lesson_images_image_key_key" UNIQUE ("image_key");



ALTER TABLE ONLY "public"."lesson_images"
    ADD CONSTRAINT "lesson_images_lesson_id_key_key" UNIQUE ("lesson_id", "image_key");



ALTER TABLE ONLY "public"."lesson_images"
    ADD CONSTRAINT "lesson_images_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."lesson_phrases"
    ADD CONSTRAINT "lesson_phrases_pkey" PRIMARY KEY ("lesson_id", "phrase_id");



ALTER TABLE ONLY "public"."lesson_phrases"
    ADD CONSTRAINT "lesson_phrases_unique" UNIQUE ("lesson_id", "phrase_id");



ALTER TABLE ONLY "public"."lesson_sections"
    ADD CONSTRAINT "lesson_sections_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."lesson_tags"
    ADD CONSTRAINT "lesson_tags_lesson_tag_unique" UNIQUE ("lesson_id", "tag_id");



ALTER TABLE ONLY "public"."lesson_tags"
    ADD CONSTRAINT "lesson_tags_pkey" PRIMARY KEY ("lesson_id", "tag_id");



ALTER TABLE ONLY "public"."lessons"
    ADD CONSTRAINT "lessons_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."lessons"
    ADD CONSTRAINT "lessons_stage_level_order_unique" UNIQUE ("stage", "level", "lesson_order");



ALTER TABLE ONLY "public"."phrases_audio_snippets"
    ADD CONSTRAINT "phrases_audio_snippets_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."phrases"
    ADD CONSTRAINT "phrases_phrase_variant_unique" UNIQUE ("phrase", "variant");



ALTER TABLE ONLY "public"."phrases"
    ADD CONSTRAINT "phrases_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."placement_conversations"
    ADD CONSTRAINT "placement_conversations_conversation_order_key" UNIQUE ("conversation_order");



ALTER TABLE ONLY "public"."placement_conversations"
    ADD CONSTRAINT "placement_conversations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."practice_exercises"
    ADD CONSTRAINT "practice_exercises_lesson_kind_sort_order_key" UNIQUE ("lesson_id", "kind", "sort_order");



ALTER TABLE ONLY "public"."practice_exercises"
    ADD CONSTRAINT "practice_exercises_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."pricing_tiers"
    ADD CONSTRAINT "pricing_tiers_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."pricing_tiers"
    ADD CONSTRAINT "pricing_tiers_region_period_unique" UNIQUE ("region_key", "billing_period");



ALTER TABLE ONLY "public"."lesson_sections"
    ADD CONSTRAINT "sections_lesson_type_unique" UNIQUE ("lesson_id", "type");



ALTER TABLE ONLY "public"."speaking_coach_practice_sets"
    ADD CONSTRAINT "speaking_coach_practice_sets_lesson_order_unique" UNIQUE ("lesson_id", "sort_order");



ALTER TABLE ONLY "public"."speaking_coach_practice_sets"
    ADD CONSTRAINT "speaking_coach_practice_sets_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."speaking_coach_practice_sets"
    ADD CONSTRAINT "speaking_coach_practice_sets_source_key_key" UNIQUE ("source_key");



ALTER TABLE ONLY "public"."speaking_coach_questions"
    ADD CONSTRAINT "speaking_coach_questions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."speaking_coach_questions"
    ADD CONSTRAINT "speaking_coach_questions_sort_order_unique" UNIQUE ("practice_set_id", "sort_order");



ALTER TABLE ONLY "public"."speaking_coach_questions"
    ADD CONSTRAINT "speaking_coach_questions_source_key_key" UNIQUE ("source_key");



ALTER TABLE ONLY "public"."speaking_coach_questions"
    ADD CONSTRAINT "speaking_coach_questions_source_number_unique" UNIQUE ("practice_set_id", "source_number");



ALTER TABLE ONLY "public"."tags"
    ADD CONSTRAINT "tags_name_key" UNIQUE ("name");



ALTER TABLE ONLY "public"."tags"
    ADD CONSTRAINT "tags_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."topic_library"
    ADD CONSTRAINT "topic_library_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."topic_library"
    ADD CONSTRAINT "topic_library_slug_key" UNIQUE ("slug");



ALTER TABLE ONLY "public"."transcript_lines"
    ADD CONSTRAINT "transcript_lines_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."transcript_lines"
    ADD CONSTRAINT "transcript_lines_unique" UNIQUE ("lesson_id", "sort_order");



ALTER TABLE ONLY "public"."user_exercise_answers"
    ADD CONSTRAINT "user_exercise_answers_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_exercise_bank_question_attempts"
    ADD CONSTRAINT "user_exercise_bank_question_attempts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_exercise_bank_question_state"
    ADD CONSTRAINT "user_exercise_bank_question_state_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_exercise_bank_question_state"
    ADD CONSTRAINT "user_exercise_bank_question_state_set_position_key" UNIQUE ("user_id", "topic_id", "set_number", "set_position");



ALTER TABLE ONLY "public"."user_exercise_bank_question_state"
    ADD CONSTRAINT "user_exercise_bank_question_state_user_question_key" UNIQUE ("user_id", "question_id");



ALTER TABLE ONLY "public"."user_exercise_bank_topic_progress"
    ADD CONSTRAINT "user_exercise_bank_topic_progress_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_exercise_bank_topic_progress"
    ADD CONSTRAINT "user_exercise_bank_topic_progress_user_topic_key" UNIQUE ("user_id", "topic_id");



ALTER TABLE ONLY "public"."user_lesson_answer_state"
    ADD CONSTRAINT "user_lesson_answer_state_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_lesson_answer_state"
    ADD CONSTRAINT "user_lesson_answer_state_user_lesson_unit_state_key_key" UNIQUE ("user_id", "lesson_id", "unit_key", "state_key");



ALTER TABLE ONLY "public"."user_lesson_progress"
    ADD CONSTRAINT "user_lesson_progress_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_lesson_progress"
    ADD CONSTRAINT "user_lesson_progress_user_id_lesson_id_key" UNIQUE ("user_id", "lesson_id");



ALTER TABLE ONLY "public"."user_lesson_unit_progress"
    ADD CONSTRAINT "user_lesson_unit_progress_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_lesson_unit_progress"
    ADD CONSTRAINT "user_lesson_unit_progress_user_lesson_unit_key_key" UNIQUE ("user_id", "lesson_id", "unit_key");



ALTER TABLE ONLY "public"."user_speaking_coach_attempts"
    ADD CONSTRAINT "user_speaking_coach_attempts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_speaking_coach_attempts"
    ADD CONSTRAINT "user_speaking_coach_attempts_sequence_unique" UNIQUE ("session_id", "question_id", "evaluation_sequence");



ALTER TABLE ONLY "public"."user_speaking_coach_sessions"
    ADD CONSTRAINT "user_speaking_coach_sessions_id_user_unique" UNIQUE ("id", "user_id");



ALTER TABLE ONLY "public"."user_speaking_coach_sessions"
    ADD CONSTRAINT "user_speaking_coach_sessions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_speaking_coach_skips"
    ADD CONSTRAINT "user_speaking_coach_skips_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_speaking_coach_skips"
    ADD CONSTRAINT "user_speaking_coach_skips_session_id_question_id_key" UNIQUE ("session_id", "question_id");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_email_key" UNIQUE ("email");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_username_key" UNIQUE ("username");



CREATE INDEX "audio_snippets_common_mistake_id_idx" ON "public"."audio_snippets" USING "btree" ("common_mistake_id");



CREATE INDEX "comments_lesson_id_pinned_created_at_idx" ON "public"."comments" USING "btree" ("lesson_id", "pinned" DESC, "created_at");



CREATE INDEX "comments_parent_comment_id_idx" ON "public"."comments" USING "btree" ("parent_comment_id");



CREATE INDEX "common_mistakes_content_jsonb_gin_idx" ON "public"."common_mistakes" USING "gin" ("content_jsonb");



CREATE INDEX "common_mistakes_content_jsonb_th_gin_idx" ON "public"."common_mistakes" USING "gin" ("content_jsonb_th");



CREATE INDEX "common_mistakes_lesson_external_id_idx" ON "public"."common_mistakes" USING "btree" ("lesson_external_id");



CREATE INDEX "common_mistakes_lesson_id_idx" ON "public"."common_mistakes" USING "btree" ("lesson_id");



CREATE INDEX "common_mistakes_lesson_sort_idx" ON "public"."common_mistakes" USING "btree" ("lesson_id", "sort_order");



CREATE INDEX "common_mistakes_published_idx" ON "public"."common_mistakes" USING "btree" ("is_published");



CREATE INDEX "common_mistakes_scm_idx" ON "public"."common_mistakes" USING "btree" ("scm");



CREATE INDEX "contact_messages_email_created_at_idx" ON "public"."contact_messages" USING "btree" ("email", "created_at" DESC);



CREATE INDEX "contact_messages_ip_created_at_idx" ON "public"."contact_messages" USING "btree" ("ip_address", "created_at" DESC);



CREATE INDEX "daily_app_open_checkins_user_opened_on_idx" ON "public"."daily_app_open_checkins" USING "btree" ("user_id", "opened_on" DESC);



CREATE UNIQUE INDEX "daily_app_open_checkins_user_opened_on_key" ON "public"."daily_app_open_checkins" USING "btree" ("user_id", "opened_on");



CREATE INDEX "exercise_bank_exercises_topic_difficulty_idx" ON "public"."exercise_bank_exercises" USING "btree" ("topic_id", "difficulty") WHERE ("is_active" = true);



CREATE INDEX "exercise_bank_questions_exercise_example_idx" ON "public"."exercise_bank_questions" USING "btree" ("exercise_id", "is_example") WHERE ("is_active" = true);



CREATE INDEX "exercise_bank_topics_category_order_idx" ON "public"."exercise_bank_topics" USING "btree" ("category", "sort_order") WHERE ("is_active" = true);



CREATE INDEX "idx_audio_snippets_audio_key" ON "public"."audio_snippets" USING "btree" ("audio_key");



CREATE INDEX "idx_comp_q_lesson_order" ON "public"."comprehension_questions" USING "btree" ("lesson_id", "sort_order");



CREATE INDEX "idx_exercise_bank_exercises_active_topic" ON "public"."exercise_bank_exercises" USING "btree" ("topic_id", "id") WHERE ("is_active" = true);



CREATE INDEX "idx_exercise_bank_questions_active_examples" ON "public"."exercise_bank_questions" USING "btree" ("exercise_id", "sort_order", "id") WHERE (("is_active" = true) AND ("is_example" = true));



CREATE INDEX "idx_exercise_bank_questions_active_practice" ON "public"."exercise_bank_questions" USING "btree" ("exercise_id", "practice_order", "id") WHERE (("is_active" = true) AND ("is_example" = false) AND ("practice_order" IS NOT NULL));



CREATE INDEX "idx_lesson_phrases_order" ON "public"."lesson_phrases" USING "btree" ("lesson_id", "sort_order");



CREATE INDEX "idx_phrases_audio_snippets_audio_key" ON "public"."phrases_audio_snippets" USING "btree" ("audio_key");



CREATE INDEX "idx_pricing_tiers_active" ON "public"."pricing_tiers" USING "btree" ("active");



CREATE INDEX "idx_pricing_tiers_region" ON "public"."pricing_tiers" USING "btree" ("region_key");



CREATE INDEX "idx_pricing_tiers_region_period" ON "public"."pricing_tiers" USING "btree" ("region_key", "billing_period");



CREATE INDEX "idx_section_lesson_order" ON "public"."lesson_sections" USING "btree" ("lesson_id", "sort_order");



CREATE INDEX "idx_speaking_coach_practice_sets_lesson" ON "public"."speaking_coach_practice_sets" USING "btree" ("lesson_id", "is_active", "sort_order");



CREATE INDEX "idx_speaking_coach_practice_sets_source_document" ON "public"."speaking_coach_practice_sets" USING "btree" ("source_document_id");



CREATE INDEX "idx_speaking_coach_questions_practice_set" ON "public"."speaking_coach_questions" USING "btree" ("practice_set_id", "is_active", "sort_order");



CREATE INDEX "idx_transcript_lesson_order" ON "public"."transcript_lines" USING "btree" ("lesson_id", "sort_order");



CREATE INDEX "idx_user_exercise_answers_created" ON "public"."user_exercise_answers" USING "btree" ("created_at");



CREATE INDEX "idx_user_exercise_answers_user_bank" ON "public"."user_exercise_answers" USING "btree" ("user_id", "exercise_bank_id");



CREATE INDEX "idx_user_exercise_answers_user_practice" ON "public"."user_exercise_answers" USING "btree" ("user_id", "practice_exercise_id");



CREATE INDEX "idx_user_exercise_bank_question_attempts_created" ON "public"."user_exercise_bank_question_attempts" USING "btree" ("created_at");



CREATE INDEX "idx_user_exercise_bank_question_attempts_user_question" ON "public"."user_exercise_bank_question_attempts" USING "btree" ("user_id", "question_id", "created_at" DESC);



CREATE INDEX "idx_user_exercise_bank_question_state_review" ON "public"."user_exercise_bank_question_state" USING "btree" ("user_id", "topic_id", "has_answered_correctly", "last_attempted_at");



CREATE INDEX "idx_user_exercise_bank_question_state_topic_sets" ON "public"."user_exercise_bank_question_state" USING "btree" ("user_id", "topic_id", "set_number", "set_position");



CREATE INDEX "idx_user_exercise_bank_topic_progress_user" ON "public"."user_exercise_bank_topic_progress" USING "btree" ("user_id", "topic_id");



CREATE INDEX "idx_user_lesson_answer_state_unit_key" ON "public"."user_lesson_answer_state" USING "btree" ("user_id", "lesson_id", "unit_key");



CREATE INDEX "idx_user_lesson_answer_state_user_lesson" ON "public"."user_lesson_answer_state" USING "btree" ("user_id", "lesson_id");



CREATE INDEX "idx_user_lesson_progress_last_unit" ON "public"."user_lesson_progress" USING "btree" ("user_id", "lesson_id", "last_unit_type", "last_unit_key");



CREATE INDEX "idx_user_lesson_progress_lesson_id" ON "public"."user_lesson_progress" USING "btree" ("lesson_id");



CREATE INDEX "idx_user_lesson_progress_user_id" ON "public"."user_lesson_progress" USING "btree" ("user_id");



CREATE INDEX "idx_user_lesson_progress_user_lesson" ON "public"."user_lesson_progress" USING "btree" ("user_id", "lesson_id");



CREATE INDEX "idx_user_lesson_unit_progress_section_key" ON "public"."user_lesson_unit_progress" USING "btree" ("user_id", "lesson_id", "section_key");



CREATE INDEX "idx_user_lesson_unit_progress_user_lesson" ON "public"."user_lesson_unit_progress" USING "btree" ("user_id", "lesson_id");



CREATE INDEX "idx_user_lesson_unit_progress_user_lesson_completed" ON "public"."user_lesson_unit_progress" USING "btree" ("user_id", "lesson_id", "is_completed");



CREATE INDEX "idx_user_speaking_coach_attempts_audio_cleanup" ON "public"."user_speaking_coach_attempts" USING "btree" ("audio_expires_at") WHERE (("audio_object_path" IS NOT NULL) AND ("audio_deleted_at" IS NULL));



CREATE INDEX "idx_user_speaking_coach_attempts_model_analytics" ON "public"."user_speaking_coach_attempts" USING "btree" ("provider", "model_used", "created_at" DESC);



CREATE INDEX "idx_user_speaking_coach_attempts_session_question" ON "public"."user_speaking_coach_attempts" USING "btree" ("session_id", "question_id", "created_at");



CREATE INDEX "idx_user_speaking_coach_attempts_user_history" ON "public"."user_speaking_coach_attempts" USING "btree" ("user_id", "created_at" DESC);



CREATE UNIQUE INDEX "idx_user_speaking_coach_one_active_session" ON "public"."user_speaking_coach_sessions" USING "btree" ("user_id", "lesson_id") WHERE ("status" = 'active'::"text");



CREATE UNIQUE INDEX "idx_user_speaking_coach_one_completion_per_question" ON "public"."user_speaking_coach_attempts" USING "btree" ("session_id", "question_id") WHERE ("completes_question" = true);



CREATE INDEX "idx_user_speaking_coach_sessions_expiration" ON "public"."user_speaking_coach_sessions" USING "btree" ("expires_at") WHERE ("status" = 'active'::"text");



CREATE INDEX "idx_user_speaking_coach_sessions_history" ON "public"."user_speaking_coach_sessions" USING "btree" ("user_id", "lesson_id", "created_at" DESC);



CREATE INDEX "lesson_sections_th_gin" ON "public"."lesson_sections" USING "gin" ("content_jsonb_th");



CREATE UNIQUE INDEX "phrases_audio_snippets_uniq" ON "public"."phrases_audio_snippets" USING "btree" ("phrase_id", "variant", "seq");



CREATE UNIQUE INDEX "phrases_phrase_variant_idx" ON "public"."phrases" USING "btree" ("phrase", "variant");



CREATE UNIQUE INDEX "uq_cq_lesson_sort" ON "public"."comprehension_questions" USING "btree" ("lesson_id", "sort_order");



CREATE UNIQUE INDEX "user_speaking_coach_attempts_one_processing" ON "public"."user_speaking_coach_attempts" USING "btree" ("session_id", "question_id") WHERE ("processing_status" = ANY (ARRAY['uploaded'::"text", 'evaluating'::"text"]));



CREATE UNIQUE INDEX "user_speaking_coach_attempts_submission_unique" ON "public"."user_speaking_coach_attempts" USING "btree" ("session_id", "client_submission_id");



CREATE INDEX "user_speaking_coach_skips_session_id_idx" ON "public"."user_speaking_coach_skips" USING "btree" ("session_id");



CREATE INDEX "user_speaking_coach_skips_user_id_idx" ON "public"."user_speaking_coach_skips" USING "btree" ("user_id");



CREATE OR REPLACE TRIGGER "set_common_mistakes_updated_at" BEFORE UPDATE ON "public"."common_mistakes" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "set_exercise_bank_exercises_updated_at" BEFORE UPDATE ON "public"."exercise_bank_exercises" FOR EACH ROW EXECUTE FUNCTION "public"."set_exercise_bank_updated_at"();



CREATE OR REPLACE TRIGGER "set_exercise_bank_questions_updated_at" BEFORE UPDATE ON "public"."exercise_bank_questions" FOR EACH ROW EXECUTE FUNCTION "public"."set_exercise_bank_updated_at"();



CREATE OR REPLACE TRIGGER "set_exercise_bank_topics_updated_at" BEFORE UPDATE ON "public"."exercise_bank_topics" FOR EACH ROW EXECUTE FUNCTION "public"."set_exercise_bank_updated_at"();



CREATE OR REPLACE TRIGGER "set_user_lesson_answer_state_updated_at" BEFORE UPDATE ON "public"."user_lesson_answer_state" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "set_user_lesson_progress_updated_at" BEFORE UPDATE ON "public"."user_lesson_progress" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "set_user_lesson_unit_progress_updated_at" BEFORE UPDATE ON "public"."user_lesson_unit_progress" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "touch_practice_exercises" BEFORE UPDATE ON "public"."practice_exercises" FOR EACH ROW EXECUTE FUNCTION "public"."trg_touch_updated_at"();



CREATE OR REPLACE TRIGGER "trg_pricing_tiers_updated_at" BEFORE UPDATE ON "public"."pricing_tiers" FOR EACH ROW EXECUTE FUNCTION "public"."pricing_tiers_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_update_speaking_coach_practice_sets" BEFORE UPDATE ON "public"."speaking_coach_practice_sets" FOR EACH ROW EXECUTE FUNCTION "public"."update_timestamp_column"();



CREATE OR REPLACE TRIGGER "trg_update_speaking_coach_questions" BEFORE UPDATE ON "public"."speaking_coach_questions" FOR EACH ROW EXECUTE FUNCTION "public"."update_timestamp_column"();



CREATE OR REPLACE TRIGGER "trg_update_user_exercise_answers" BEFORE UPDATE ON "public"."user_exercise_answers" FOR EACH ROW EXECUTE FUNCTION "public"."update_timestamp_column"();



CREATE OR REPLACE TRIGGER "trg_update_user_exercise_bank_question_state" BEFORE UPDATE ON "public"."user_exercise_bank_question_state" FOR EACH ROW EXECUTE FUNCTION "public"."update_timestamp_column"();



CREATE OR REPLACE TRIGGER "trg_update_user_exercise_bank_topic_progress" BEFORE UPDATE ON "public"."user_exercise_bank_topic_progress" FOR EACH ROW EXECUTE FUNCTION "public"."update_timestamp_column"();



CREATE OR REPLACE TRIGGER "trg_update_user_speaking_coach_attempts" BEFORE UPDATE ON "public"."user_speaking_coach_attempts" FOR EACH ROW EXECUTE FUNCTION "public"."update_timestamp_column"();



CREATE OR REPLACE TRIGGER "trg_update_user_speaking_coach_sessions" BEFORE UPDATE ON "public"."user_speaking_coach_sessions" FOR EACH ROW EXECUTE FUNCTION "public"."update_timestamp_column"();



ALTER TABLE ONLY "public"."audio_snippets"
    ADD CONSTRAINT "audio_snippets_common_mistake_id_fkey" FOREIGN KEY ("common_mistake_id") REFERENCES "public"."common_mistakes"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."comments"
    ADD CONSTRAINT "comments_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."comments"
    ADD CONSTRAINT "comments_parent_comment_id_fkey" FOREIGN KEY ("parent_comment_id") REFERENCES "public"."comments"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."comments"
    ADD CONSTRAINT "comments_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."common_mistakes"
    ADD CONSTRAINT "common_mistakes_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."comprehension_questions"
    ADD CONSTRAINT "comprehension_questions_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."daily_app_open_checkins"
    ADD CONSTRAINT "daily_app_open_checkins_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."exercise_bank_exercises"
    ADD CONSTRAINT "exercise_bank_exercises_topic_id_fkey" FOREIGN KEY ("topic_id") REFERENCES "public"."exercise_bank_topics"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."exercise_bank_questions"
    ADD CONSTRAINT "exercise_bank_questions_exercise_id_fkey" FOREIGN KEY ("exercise_id") REFERENCES "public"."exercise_bank_exercises"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."lesson_images"
    ADD CONSTRAINT "lesson_images_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."lesson_phrases"
    ADD CONSTRAINT "lesson_phrases_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."lesson_phrases"
    ADD CONSTRAINT "lesson_phrases_phrase_id_fkey" FOREIGN KEY ("phrase_id") REFERENCES "public"."phrases"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."lesson_sections"
    ADD CONSTRAINT "lesson_sections_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."lesson_tags"
    ADD CONSTRAINT "lesson_tags_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."lesson_tags"
    ADD CONSTRAINT "lesson_tags_tag_id_fkey" FOREIGN KEY ("tag_id") REFERENCES "public"."tags"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."phrases_audio_snippets"
    ADD CONSTRAINT "phrases_audio_snippets_phrase_id_fkey" FOREIGN KEY ("phrase_id") REFERENCES "public"."phrases"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."practice_exercises"
    ADD CONSTRAINT "practice_exercises_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id");



ALTER TABLE ONLY "public"."speaking_coach_practice_sets"
    ADD CONSTRAINT "speaking_coach_practice_sets_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."speaking_coach_questions"
    ADD CONSTRAINT "speaking_coach_questions_practice_set_id_fkey" FOREIGN KEY ("practice_set_id") REFERENCES "public"."speaking_coach_practice_sets"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."transcript_lines"
    ADD CONSTRAINT "transcript_lines_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_exercise_answers"
    ADD CONSTRAINT "user_exercise_answers_exercise_bank_id_fkey" FOREIGN KEY ("exercise_bank_id") REFERENCES "public"."exercise_bank"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_exercise_answers"
    ADD CONSTRAINT "user_exercise_answers_practice_exercise_id_fkey" FOREIGN KEY ("practice_exercise_id") REFERENCES "public"."practice_exercises"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_exercise_answers"
    ADD CONSTRAINT "user_exercise_answers_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_exercise_bank_question_attempts"
    ADD CONSTRAINT "user_exercise_bank_question_attempts_question_fkey" FOREIGN KEY ("question_id") REFERENCES "public"."exercise_bank_questions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_exercise_bank_question_attempts"
    ADD CONSTRAINT "user_exercise_bank_question_attempts_user_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_exercise_bank_question_state"
    ADD CONSTRAINT "user_exercise_bank_question_state_question_fkey" FOREIGN KEY ("question_id") REFERENCES "public"."exercise_bank_questions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_exercise_bank_question_state"
    ADD CONSTRAINT "user_exercise_bank_question_state_topic_fkey" FOREIGN KEY ("topic_id") REFERENCES "public"."exercise_bank_topics"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_exercise_bank_question_state"
    ADD CONSTRAINT "user_exercise_bank_question_state_user_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_exercise_bank_topic_progress"
    ADD CONSTRAINT "user_exercise_bank_topic_progress_topic_fkey" FOREIGN KEY ("topic_id") REFERENCES "public"."exercise_bank_topics"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_exercise_bank_topic_progress"
    ADD CONSTRAINT "user_exercise_bank_topic_progress_user_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_lesson_answer_state"
    ADD CONSTRAINT "user_lesson_answer_state_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_lesson_answer_state"
    ADD CONSTRAINT "user_lesson_answer_state_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_lesson_progress"
    ADD CONSTRAINT "user_lesson_progress_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_lesson_progress"
    ADD CONSTRAINT "user_lesson_progress_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_lesson_unit_progress"
    ADD CONSTRAINT "user_lesson_unit_progress_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_lesson_unit_progress"
    ADD CONSTRAINT "user_lesson_unit_progress_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_speaking_coach_attempts"
    ADD CONSTRAINT "user_speaking_coach_attempts_previous_attempt_id_fkey" FOREIGN KEY ("previous_attempt_id") REFERENCES "public"."user_speaking_coach_attempts"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."user_speaking_coach_attempts"
    ADD CONSTRAINT "user_speaking_coach_attempts_question_id_fkey" FOREIGN KEY ("question_id") REFERENCES "public"."speaking_coach_questions"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."user_speaking_coach_attempts"
    ADD CONSTRAINT "user_speaking_coach_attempts_session_user_fkey" FOREIGN KEY ("session_id", "user_id") REFERENCES "public"."user_speaking_coach_sessions"("id", "user_id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_speaking_coach_attempts"
    ADD CONSTRAINT "user_speaking_coach_attempts_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_speaking_coach_sessions"
    ADD CONSTRAINT "user_speaking_coach_sessions_current_question_id_fkey" FOREIGN KEY ("current_question_id") REFERENCES "public"."speaking_coach_questions"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."user_speaking_coach_sessions"
    ADD CONSTRAINT "user_speaking_coach_sessions_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "public"."lessons"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_speaking_coach_sessions"
    ADD CONSTRAINT "user_speaking_coach_sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_speaking_coach_skips"
    ADD CONSTRAINT "user_speaking_coach_skips_question_id_fkey" FOREIGN KEY ("question_id") REFERENCES "public"."speaking_coach_questions"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."user_speaking_coach_skips"
    ADD CONSTRAINT "user_speaking_coach_skips_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."user_speaking_coach_sessions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_speaking_coach_skips"
    ADD CONSTRAINT "user_speaking_coach_skips_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE CASCADE;



CREATE POLICY "Active exercise bank exercises are readable" ON "public"."exercise_bank_exercises" FOR SELECT TO "authenticated", "anon" USING ((("is_active" = true) AND (EXISTS ( SELECT 1
   FROM "public"."exercise_bank_topics" "topic"
  WHERE (("topic"."id" = "exercise_bank_exercises"."topic_id") AND ("topic"."is_active" = true))))));



CREATE POLICY "Active exercise bank questions are readable" ON "public"."exercise_bank_questions" FOR SELECT TO "authenticated", "anon" USING ((("is_active" = true) AND (EXISTS ( SELECT 1
   FROM ("public"."exercise_bank_exercises" "exercise"
     JOIN "public"."exercise_bank_topics" "topic" ON (("topic"."id" = "exercise"."topic_id")))
  WHERE (("exercise"."id" = "exercise_bank_questions"."exercise_id") AND ("exercise"."is_active" = true) AND ("topic"."is_active" = true))))));



CREATE POLICY "Active exercise bank topics are readable" ON "public"."exercise_bank_topics" FOR SELECT TO "authenticated", "anon" USING (("is_active" = true));



CREATE POLICY "Admins can manage all comments" ON "public"."comments" TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."users"
  WHERE (("users"."id" = "auth"."uid"()) AND ("users"."is_admin" = true))))) WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."users"
  WHERE (("users"."id" = "auth"."uid"()) AND ("users"."is_admin" = true)))));



CREATE POLICY "Admins can manage all exercise answers" ON "public"."user_exercise_answers" TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."users"
  WHERE (("users"."id" = "auth"."uid"()) AND ("users"."is_admin" = true))))) WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."users"
  WHERE (("users"."id" = "auth"."uid"()) AND ("users"."is_admin" = true)))));



CREATE POLICY "Admins can view all exercise answers" ON "public"."user_exercise_answers" FOR SELECT TO "authenticated" USING ((EXISTS ( SELECT 1
   FROM "public"."users"
  WHERE (("users"."id" = "auth"."uid"()) AND ("users"."is_admin" = true)))));



CREATE POLICY "Allow reading public user info" ON "public"."users" FOR SELECT TO "authenticated", "anon" USING (true);



CREATE POLICY "Allow user to create a record" ON "public"."users" FOR INSERT TO "authenticated" WITH CHECK (("id" = "auth"."uid"()));



CREATE POLICY "Allow user to update their own record" ON "public"."users" FOR UPDATE TO "authenticated" USING (("auth"."uid"() = "id")) WITH CHECK (("auth"."uid"() = "id"));



CREATE POLICY "Enable delete for users based on user_id" ON "public"."users" FOR DELETE TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "id"));



CREATE POLICY "Enable insert for authenticated users only" ON "public"."users" FOR INSERT TO "authenticated" WITH CHECK (true);



CREATE POLICY "Enable read access for user's own record" ON "public"."users" FOR SELECT TO "authenticated" USING (("auth"."uid"() = "id"));



CREATE POLICY "Placement conversations are publicly readable" ON "public"."placement_conversations" FOR SELECT TO "authenticated", "anon" USING (true);



CREATE POLICY "Public can read lessons" ON "public"."lessons" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."comprehension_questions" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."enum_labels" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."exercise_bank" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."lesson_images" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."lesson_phrases" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."lesson_sections" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."lesson_tags" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."phrases" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."phrases_audio_snippets" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."practice_exercises" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."tags" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."topic_library" FOR SELECT USING (true);



CREATE POLICY "Public read access" ON "public"."transcript_lines" FOR SELECT USING (true);



CREATE POLICY "Public read access for audio snippets" ON "public"."audio_snippets" FOR SELECT USING (true);



CREATE POLICY "Public read access for comments" ON "public"."comments" FOR SELECT USING (true);



CREATE POLICY "Users can create own exercise answers" ON "public"."user_exercise_answers" FOR INSERT TO "authenticated" WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can create root comments; admins can reply" ON "public"."comments" FOR INSERT TO "authenticated" WITH CHECK ((("auth"."uid"() = "user_id") AND (("parent_comment_id" IS NULL) OR (EXISTS ( SELECT 1
   FROM "public"."users"
  WHERE (("users"."id" = "auth"."uid"()) AND ("users"."is_admin" = true)))))));



CREATE POLICY "Users can delete own comments" ON "public"."comments" FOR DELETE TO "authenticated" USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can delete own exercise answers" ON "public"."user_exercise_answers" FOR DELETE TO "authenticated" USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can delete own progress" ON "public"."user_lesson_progress" FOR DELETE TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Users can insert own progress" ON "public"."user_lesson_progress" FOR INSERT TO "authenticated" WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Users can read their own exercise bank attempts" ON "public"."user_exercise_bank_question_attempts" FOR SELECT TO "authenticated" USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can read their own exercise bank question state" ON "public"."user_exercise_bank_question_state" FOR SELECT TO "authenticated" USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can read their own exercise bank topic progress" ON "public"."user_exercise_bank_topic_progress" FOR SELECT TO "authenticated" USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can select own progress" ON "public"."user_lesson_progress" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Users can update own comments" ON "public"."comments" FOR UPDATE TO "authenticated" USING (("auth"."uid"() = "user_id")) WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can update own exercise answers" ON "public"."user_exercise_answers" FOR UPDATE TO "authenticated" USING (("auth"."uid"() = "user_id")) WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can update own is_verified" ON "public"."users" FOR UPDATE USING (("auth"."uid"() = "id")) WITH CHECK (("auth"."uid"() = "id"));



CREATE POLICY "Users can update own progress" ON "public"."user_lesson_progress" FOR UPDATE TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "user_id")) WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Users can view own exercise answers" ON "public"."user_exercise_answers" FOR SELECT TO "authenticated" USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users manage own lesson answer state" ON "public"."user_lesson_answer_state" TO "authenticated" USING (("auth"."uid"() = "user_id")) WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "Users manage own lesson progress" ON "public"."user_lesson_progress" TO "authenticated" USING (("auth"."uid"() = "user_id")) WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "Users manage own lesson unit progress" ON "public"."user_lesson_unit_progress" TO "authenticated" USING (("auth"."uid"() = "user_id")) WITH CHECK (("auth"."uid"() = "user_id"));



ALTER TABLE "public"."audio_snippets" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "audio_snippets_select_common_mistake_audio" ON "public"."audio_snippets" FOR SELECT TO "authenticated", "anon" USING ((("common_mistake_id" IS NOT NULL) AND (EXISTS ( SELECT 1
   FROM "public"."common_mistakes" "cm"
  WHERE (("cm"."id" = "audio_snippets"."common_mistake_id") AND ("cm"."is_published" = true))))));



ALTER TABLE "public"."auth_signup_rate_limits" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."comments" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."common_mistakes" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "common_mistakes_select_published" ON "public"."common_mistakes" FOR SELECT TO "authenticated", "anon" USING (("is_published" = true));



ALTER TABLE "public"."comprehension_questions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."daily_app_open_checkins" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."enum_labels" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."exercise_bank" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."exercise_bank_exercises" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."exercise_bank_questions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."exercise_bank_topics" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."lesson_images" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."lesson_phrases" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."lesson_sections" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."lesson_tags" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."lessons" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."phrases" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."phrases_audio_snippets" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."placement_conversations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."practice_exercises" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."pricing_tiers" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "pricing_tiers_select_active" ON "public"."pricing_tiers" FOR SELECT USING (("active" = true));



ALTER TABLE "public"."speaking_coach_practice_sets" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."speaking_coach_questions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."tags" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."topic_library" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."transcript_lines" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_exercise_answers" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_exercise_bank_question_attempts" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_exercise_bank_question_state" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_exercise_bank_topic_progress" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_lesson_answer_state" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_lesson_progress" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_lesson_unit_progress" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_speaking_coach_attempts" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_speaking_coach_sessions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_speaking_coach_skips" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."users" ENABLE ROW LEVEL SECURITY;




ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";

















































































































































































REVOKE ALL ON FUNCTION "public"."advance_exercise_bank_v2_set"("p_user_id" "uuid", "p_topic_id" bigint, "p_set_number" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."advance_exercise_bank_v2_set"("p_user_id" "uuid", "p_topic_id" bigint, "p_set_number" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."consume_auth_signup_rate_limit"("p_key" "text", "p_limit" integer, "p_window_seconds" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."consume_auth_signup_rate_limit"("p_key" "text", "p_limit" integer, "p_window_seconds" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."get_exercise_bank_v2_session"("p_user_id" "uuid", "p_topic_id" bigint, "p_set_number" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."get_exercise_bank_v2_session"("p_user_id" "uuid", "p_topic_id" bigint, "p_set_number" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."get_exercise_bank_v2_topic_summaries"("p_user_id" "uuid", "p_category" "text", "p_featured_only" boolean) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."get_exercise_bank_v2_topic_summaries"("p_user_id" "uuid", "p_category" "text", "p_featured_only" boolean) TO "service_role";



GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "anon";
GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "service_role";



GRANT ALL ON FUNCTION "public"."is_valid_speaking_coach_focus_items"("items" "jsonb") TO "anon";
GRANT ALL ON FUNCTION "public"."is_valid_speaking_coach_focus_items"("items" "jsonb") TO "authenticated";
GRANT ALL ON FUNCTION "public"."is_valid_speaking_coach_focus_items"("items" "jsonb") TO "service_role";



GRANT ALL ON FUNCTION "public"."pricing_tiers_set_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."pricing_tiers_set_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."pricing_tiers_set_updated_at"() TO "service_role";



REVOKE ALL ON FUNCTION "public"."record_exercise_bank_v2_attempt"("p_user_id" "uuid", "p_question_id" bigint, "p_user_answer" "text", "p_is_correct" boolean, "p_grading_method" "text", "p_ai_score" numeric, "p_ai_feedback_en" "text", "p_ai_feedback_th" "text", "p_ai_model" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."record_exercise_bank_v2_attempt"("p_user_id" "uuid", "p_question_id" bigint, "p_user_answer" "text", "p_is_correct" boolean, "p_grading_method" "text", "p_ai_score" numeric, "p_ai_feedback_en" "text", "p_ai_feedback_th" "text", "p_ai_model" "text") TO "service_role";



REVOKE ALL ON FUNCTION "public"."save_exercise_bank_v2_cursor"("p_user_id" "uuid", "p_topic_id" bigint, "p_set_number" integer, "p_set_position" smallint, "p_view" "text") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."save_exercise_bank_v2_cursor"("p_user_id" "uuid", "p_topic_id" bigint, "p_set_number" integer, "p_set_position" smallint, "p_view" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."set_exercise_bank_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."set_exercise_bank_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."set_exercise_bank_updated_at"() TO "service_role";



GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "service_role";



GRANT ALL ON FUNCTION "public"."sync_email_verification"() TO "anon";
GRANT ALL ON FUNCTION "public"."sync_email_verification"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."sync_email_verification"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_touch_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_touch_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_touch_updated_at"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_timestamp_column"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_timestamp_column"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_timestamp_column"() TO "service_role";



























GRANT ALL ON TABLE "public"."audio_snippets" TO "anon";
GRANT ALL ON TABLE "public"."audio_snippets" TO "authenticated";
GRANT ALL ON TABLE "public"."audio_snippets" TO "service_role";



GRANT ALL ON TABLE "public"."auth_signup_rate_limits" TO "service_role";



GRANT ALL ON TABLE "public"."comments" TO "anon";
GRANT ALL ON TABLE "public"."comments" TO "authenticated";
GRANT ALL ON TABLE "public"."comments" TO "service_role";



GRANT ALL ON TABLE "public"."common_mistakes" TO "anon";
GRANT ALL ON TABLE "public"."common_mistakes" TO "authenticated";
GRANT ALL ON TABLE "public"."common_mistakes" TO "service_role";



GRANT ALL ON TABLE "public"."comprehension_questions" TO "anon";
GRANT ALL ON TABLE "public"."comprehension_questions" TO "authenticated";
GRANT ALL ON TABLE "public"."comprehension_questions" TO "service_role";



GRANT ALL ON TABLE "public"."contact_messages" TO "anon";
GRANT ALL ON TABLE "public"."contact_messages" TO "authenticated";
GRANT ALL ON TABLE "public"."contact_messages" TO "service_role";



GRANT ALL ON SEQUENCE "public"."contact_messages_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."contact_messages_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."contact_messages_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."daily_app_open_checkins" TO "anon";
GRANT ALL ON TABLE "public"."daily_app_open_checkins" TO "authenticated";
GRANT ALL ON TABLE "public"."daily_app_open_checkins" TO "service_role";



GRANT ALL ON TABLE "public"."debug_admin_user_lesson_progress_backup_20260630" TO "anon";
GRANT ALL ON TABLE "public"."debug_admin_user_lesson_progress_backup_20260630" TO "authenticated";
GRANT ALL ON TABLE "public"."debug_admin_user_lesson_progress_backup_20260630" TO "service_role";



GRANT ALL ON TABLE "public"."enum_labels" TO "anon";
GRANT ALL ON TABLE "public"."enum_labels" TO "authenticated";
GRANT ALL ON TABLE "public"."enum_labels" TO "service_role";



GRANT ALL ON TABLE "public"."exercise_bank" TO "anon";
GRANT ALL ON TABLE "public"."exercise_bank" TO "authenticated";
GRANT ALL ON TABLE "public"."exercise_bank" TO "service_role";



GRANT ALL ON TABLE "public"."exercise_bank_exercises" TO "anon";
GRANT ALL ON TABLE "public"."exercise_bank_exercises" TO "authenticated";
GRANT ALL ON TABLE "public"."exercise_bank_exercises" TO "service_role";



GRANT ALL ON SEQUENCE "public"."exercise_bank_exercises_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."exercise_bank_exercises_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."exercise_bank_exercises_id_seq" TO "service_role";



GRANT ALL ON SEQUENCE "public"."exercise_bank_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."exercise_bank_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."exercise_bank_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."exercise_bank_questions" TO "anon";
GRANT ALL ON TABLE "public"."exercise_bank_questions" TO "authenticated";
GRANT ALL ON TABLE "public"."exercise_bank_questions" TO "service_role";



GRANT ALL ON SEQUENCE "public"."exercise_bank_questions_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."exercise_bank_questions_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."exercise_bank_questions_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."exercise_bank_topics" TO "anon";
GRANT ALL ON TABLE "public"."exercise_bank_topics" TO "authenticated";
GRANT ALL ON TABLE "public"."exercise_bank_topics" TO "service_role";



GRANT ALL ON SEQUENCE "public"."exercise_bank_topics_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."exercise_bank_topics_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."exercise_bank_topics_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."featured_sections" TO "anon";
GRANT ALL ON TABLE "public"."featured_sections" TO "authenticated";
GRANT ALL ON TABLE "public"."featured_sections" TO "service_role";



GRANT ALL ON TABLE "public"."lesson_images" TO "anon";
GRANT ALL ON TABLE "public"."lesson_images" TO "authenticated";
GRANT ALL ON TABLE "public"."lesson_images" TO "service_role";



GRANT ALL ON TABLE "public"."lesson_phrases" TO "anon";
GRANT ALL ON TABLE "public"."lesson_phrases" TO "authenticated";
GRANT ALL ON TABLE "public"."lesson_phrases" TO "service_role";



GRANT ALL ON TABLE "public"."lesson_sections" TO "anon";
GRANT ALL ON TABLE "public"."lesson_sections" TO "authenticated";
GRANT ALL ON TABLE "public"."lesson_sections" TO "service_role";



GRANT ALL ON TABLE "public"."lesson_tags" TO "anon";
GRANT ALL ON TABLE "public"."lesson_tags" TO "authenticated";
GRANT ALL ON TABLE "public"."lesson_tags" TO "service_role";



GRANT ALL ON TABLE "public"."lessons" TO "anon";
GRANT ALL ON TABLE "public"."lessons" TO "authenticated";
GRANT ALL ON TABLE "public"."lessons" TO "service_role";



GRANT ALL ON TABLE "public"."phrases" TO "anon";
GRANT ALL ON TABLE "public"."phrases" TO "authenticated";
GRANT ALL ON TABLE "public"."phrases" TO "service_role";



GRANT ALL ON TABLE "public"."phrases_audio_snippets" TO "anon";
GRANT ALL ON TABLE "public"."phrases_audio_snippets" TO "authenticated";
GRANT ALL ON TABLE "public"."phrases_audio_snippets" TO "service_role";



GRANT ALL ON TABLE "public"."placement_conversations" TO "anon";
GRANT ALL ON TABLE "public"."placement_conversations" TO "authenticated";
GRANT ALL ON TABLE "public"."placement_conversations" TO "service_role";



GRANT ALL ON TABLE "public"."practice_exercises" TO "anon";
GRANT ALL ON TABLE "public"."practice_exercises" TO "authenticated";
GRANT ALL ON TABLE "public"."practice_exercises" TO "service_role";



GRANT ALL ON SEQUENCE "public"."practice_exercises_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."practice_exercises_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."practice_exercises_id_seq" TO "service_role";



GRANT ALL ON SEQUENCE "public"."practice_exercises_sort_order_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."practice_exercises_sort_order_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."practice_exercises_sort_order_seq" TO "service_role";



GRANT ALL ON TABLE "public"."pricing_tiers" TO "anon";
GRANT ALL ON TABLE "public"."pricing_tiers" TO "authenticated";
GRANT ALL ON TABLE "public"."pricing_tiers" TO "service_role";



GRANT ALL ON TABLE "public"."speaking_coach_practice_sets" TO "anon";
GRANT ALL ON TABLE "public"."speaking_coach_practice_sets" TO "authenticated";
GRANT ALL ON TABLE "public"."speaking_coach_practice_sets" TO "service_role";



GRANT ALL ON SEQUENCE "public"."speaking_coach_practice_sets_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."speaking_coach_practice_sets_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."speaking_coach_practice_sets_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."speaking_coach_questions" TO "anon";
GRANT ALL ON TABLE "public"."speaking_coach_questions" TO "authenticated";
GRANT ALL ON TABLE "public"."speaking_coach_questions" TO "service_role";



GRANT ALL ON SEQUENCE "public"."speaking_coach_questions_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."speaking_coach_questions_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."speaking_coach_questions_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."tags" TO "anon";
GRANT ALL ON TABLE "public"."tags" TO "authenticated";
GRANT ALL ON TABLE "public"."tags" TO "service_role";



GRANT ALL ON TABLE "public"."topic_library" TO "anon";
GRANT ALL ON TABLE "public"."topic_library" TO "authenticated";
GRANT ALL ON TABLE "public"."topic_library" TO "service_role";



GRANT ALL ON TABLE "public"."transcript_lines" TO "anon";
GRANT ALL ON TABLE "public"."transcript_lines" TO "authenticated";
GRANT ALL ON TABLE "public"."transcript_lines" TO "service_role";



GRANT ALL ON TABLE "public"."user_exercise_answers" TO "anon";
GRANT ALL ON TABLE "public"."user_exercise_answers" TO "authenticated";
GRANT ALL ON TABLE "public"."user_exercise_answers" TO "service_role";



GRANT ALL ON TABLE "public"."user_exercise_bank_question_attempts" TO "anon";
GRANT ALL ON TABLE "public"."user_exercise_bank_question_attempts" TO "authenticated";
GRANT ALL ON TABLE "public"."user_exercise_bank_question_attempts" TO "service_role";



GRANT ALL ON TABLE "public"."user_exercise_bank_question_state" TO "anon";
GRANT ALL ON TABLE "public"."user_exercise_bank_question_state" TO "authenticated";
GRANT ALL ON TABLE "public"."user_exercise_bank_question_state" TO "service_role";



GRANT ALL ON TABLE "public"."user_exercise_bank_topic_progress" TO "anon";
GRANT ALL ON TABLE "public"."user_exercise_bank_topic_progress" TO "authenticated";
GRANT ALL ON TABLE "public"."user_exercise_bank_topic_progress" TO "service_role";



GRANT ALL ON TABLE "public"."user_lesson_answer_state" TO "anon";
GRANT ALL ON TABLE "public"."user_lesson_answer_state" TO "authenticated";
GRANT ALL ON TABLE "public"."user_lesson_answer_state" TO "service_role";



GRANT ALL ON SEQUENCE "public"."user_lesson_answer_state_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."user_lesson_answer_state_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."user_lesson_answer_state_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."user_lesson_progress" TO "anon";
GRANT ALL ON TABLE "public"."user_lesson_progress" TO "authenticated";
GRANT ALL ON TABLE "public"."user_lesson_progress" TO "service_role";



GRANT ALL ON SEQUENCE "public"."user_lesson_progress_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."user_lesson_progress_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."user_lesson_progress_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."user_lesson_unit_progress" TO "anon";
GRANT ALL ON TABLE "public"."user_lesson_unit_progress" TO "authenticated";
GRANT ALL ON TABLE "public"."user_lesson_unit_progress" TO "service_role";



GRANT ALL ON SEQUENCE "public"."user_lesson_unit_progress_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."user_lesson_unit_progress_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."user_lesson_unit_progress_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."user_speaking_coach_attempts" TO "anon";
GRANT ALL ON TABLE "public"."user_speaking_coach_attempts" TO "authenticated";
GRANT ALL ON TABLE "public"."user_speaking_coach_attempts" TO "service_role";



GRANT ALL ON TABLE "public"."user_speaking_coach_sessions" TO "anon";
GRANT ALL ON TABLE "public"."user_speaking_coach_sessions" TO "authenticated";
GRANT ALL ON TABLE "public"."user_speaking_coach_sessions" TO "service_role";



GRANT ALL ON TABLE "public"."user_speaking_coach_skips" TO "anon";
GRANT ALL ON TABLE "public"."user_speaking_coach_skips" TO "authenticated";
GRANT ALL ON TABLE "public"."user_speaking_coach_skips" TO "service_role";



GRANT ALL ON TABLE "public"."users" TO "anon";
GRANT ALL ON TABLE "public"."users" TO "authenticated";
GRANT ALL ON TABLE "public"."users" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "service_role";






























