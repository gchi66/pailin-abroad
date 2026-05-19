alter table public.exercise_bank
add column if not exists sort_order integer;

comment on column public.exercise_bank.sort_order is
'Preserves exercise order from the source document within each exercise-bank section.';
