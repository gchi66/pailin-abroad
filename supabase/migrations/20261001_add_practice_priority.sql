alter table public.practice_exercises
add column if not exists practice_priority text not null default 'core';

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'practice_exercises_priority_valid'
      and conrelid = 'public.practice_exercises'::regclass
  ) then
    alter table public.practice_exercises
    add constraint practice_exercises_priority_valid
    check (practice_priority in ('core', 'extra'));
  end if;
end
$$;
