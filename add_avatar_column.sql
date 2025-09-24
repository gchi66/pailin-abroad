-- Add avatar_image column to users table
-- This migration adds support for storing user avatar images in the onboarding flow

ALTER TABLE public.users
ADD COLUMN avatar_image TEXT;

-- Add comment to document the column
COMMENT ON COLUMN public.users.avatar_image IS 'Path to user avatar image selected during onboarding';
