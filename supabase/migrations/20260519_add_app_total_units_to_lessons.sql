alter table public.lessons
add column if not exists app_total_units integer;

comment on column public.lessons.app_total_units is
'Cached total count of app lesson units used for progress summaries.';
