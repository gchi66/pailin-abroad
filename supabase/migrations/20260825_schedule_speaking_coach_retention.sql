-- Hourly speaking-coach retention cleanup.
--
-- Before this job can authenticate, store the same random token in:
--   1. Fly as SPEAKING_COACH_CLEANUP_SECRET
--   2. Supabase Vault under the name speaking_coach_cleanup_secret
--
-- The job is safe to install before the Vault secret exists; calls will receive
-- 401 until the secret is configured and no learner data will be changed.

create extension if not exists pg_cron;
create extension if not exists pg_net;

do $$
begin
  if to_regclass('public.user_speaking_coach_attempts') is not null then
    execute '
      create index if not exists user_speaking_attempts_audio_expiry_cleanup_idx
      on public.user_speaking_coach_attempts (audio_expires_at)
      where audio_deleted_at is null and audio_object_path is not null
    ';
  end if;
end
$$;

select cron.unschedule(jobid)
from cron.job
where jobname = 'speaking-coach-retention-hourly';

select cron.schedule(
  'speaking-coach-retention-hourly',
  '17 * * * *',
  $job$
    select net.http_post(
      url := 'https://backend-red-morning-4216.fly.dev/api/internal/speaking/cleanup',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'Authorization', 'Bearer ' || coalesce(
          (
            select decrypted_secret
            from vault.decrypted_secrets
            where name = 'speaking_coach_cleanup_secret'
            limit 1
          ),
          ''
        )
      ),
      body := jsonb_build_object('scheduled_at', now()),
      timeout_milliseconds := 30000
    ) as request_id;
  $job$
);
