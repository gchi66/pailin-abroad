ALTER TABLE public.user_lesson_progress
ADD COLUMN IF NOT EXISTS last_visited_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_user_lesson_progress_user_last_visited
ON public.user_lesson_progress (user_id, last_visited_at DESC)
WHERE last_visited_at IS NOT NULL;
