-- Listening is now a first-class app progress unit for lessons with conversation audio.
-- Null totals remain null so the API's existing fallback can calculate them from scratch.
update public.lessons
set app_total_units = app_total_units + 1
where app_total_units is not null
  and nullif(btrim(conversation_audio_url), '') is not null;
