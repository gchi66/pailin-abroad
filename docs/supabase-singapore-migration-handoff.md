# Supabase Singapore Migration Handoff

Last updated: September 15, 2026

This checklist tracks the migration from the West US Supabase project to the new Singapore project. Do not place API keys, database passwords, access tokens, or connection strings in this document.

Singapore project URL: `https://fuqulecxzfpjcbnhhsna.supabase.co`
Singapore project ref: `fuqulecxzfpjcbnhhsna`

## Completed

- Created the new Supabase project in Southeast Asia (Singapore).
- Dumped and restored database roles, schema, and data.
- Verified the restored database contains:
  - 40 public tables
  - 134 auth users
  - 7 storage buckets
  - 11,164 storage object records
- Transferred the Vault/pgsodium root encryption key.
- Enabled `pg_cron` and `pg_net` in the new project.
- Restored the custom auth triggers and storage policies identified by the schema comparison.
- Confirmed there are no Supabase Edge Functions to migrate.
- Copied all 11,164 storage objects to the new project with zero reported failures.
- Configured Apple, Google, and email authentication in the new Supabase project.
- Added the new Supabase OAuth callback URL to the Google web OAuth client while retaining the old callback during the transition.
- Updated local Supabase configuration values for development/testing.

## Tomorrow: rotate the exposed Azure key

The previously used Azure API key appeared in IDE-provided chat context. It was not published publicly, but it should still be treated as exposed and rotated.

1. Open the relevant Azure AI resource in the Azure Portal.
2. Go to **Resource Management > Keys and Endpoint**.
3. Determine whether the backend currently uses Key 1 or Key 2.
4. Regenerate the unused key.
5. Update the local backend environment to use the newly generated key.
6. Update the corresponding Fly secret and allow the backend to redeploy.
7. Exercise an Azure-powered backend feature and check Fly logs for authentication errors.
8. Regenerate the original exposed key so it becomes invalid.
9. Never paste either key into chat, source control, logs, or this document.

## Remaining Supabase configuration

- Compare the old and new Auth settings:
  - Site URL
  - Allowed redirect URLs
  - Custom SMTP configuration
  - Email subjects and templates
  - Email confirmation and security settings
- Test existing-user sign-in against the new project:
  - Email/password
  - Google on each supported platform
  - Apple on iOS
- Recreate the Vault secret named `speaking_coach_cleanup_secret` in the new project.
  - It must match the backend cleanup secret used by Fly.
  - If the original value is unavailable, generate a new value and update the new Vault secret and Fly secret together.
- Confirm the Speaking Coach retention cron job exists and is enabled in the new database after the Vault secret is available.
- Check whether the app uses Supabase Realtime subscriptions. If it does, recreate the required publication/table settings in the new project.

## Validation before production cutover

- Verify representative files can be downloaded from every storage bucket in the new project; metadata counts alone are not sufficient.
- Run the web frontend locally against the new project and test authentication, lesson content, audio, images, and account flows.
- Run the mobile app locally against the new project and test the same flows, including native Google and Apple sign-in.
- Run the backend against the new project and exercise all important authenticated endpoints.
- Retest Speaking Coach startup and record its server timings. Compare auth and query timings with the West US baseline.
- Confirm no code or deployment configuration still contains the old project URL or project reference, except migration tooling and deliberate rollback documentation.

## Coordinated production cutover

The database can receive new writes between the initial backup and the cutover, so perform a final delta synchronization or schedule a short maintenance window before switching production.

1. Announce or begin the maintenance window if one is required.
2. Stop or minimize writes to the old project.
3. Copy database and storage changes made since the initial migration.
4. Re-run validation counts and smoke tests against the new project.
5. Update production configuration for:
   - Fly backend
   - Vercel frontend
   - Expo/EAS mobile app
6. Deploy the backend and web frontend in a coordinated window.
7. Build and release the mobile app with the new Supabase project configuration.
8. Expect existing installations to require reauthentication because sessions issued by the old project are not interchangeable with the new project.
9. Monitor authentication failures, API errors, storage failures, and Speaking Coach latency.
10. Keep the old Supabase project active and unchanged as a rollback source until the new system has been stable for an agreed period.

## After stabilization

- Revoke the temporary Supabase personal access token used for migration if it is no longer needed.
- Unset migration-only shell variables containing database URLs, passwords, access tokens, or service-role keys.
- Remove or securely archive the SQL dumps and generated schema-diff files. Do not commit them.
- Resolve the overwritten tracked `schema.sql` carefully; preserve any required backup before restoring or replacing it.
- Decide whether the storage migration script should be retained and committed as operational tooling.
- Establish a clean migration baseline from the actual Singapore database because the historical local migration chain is incomplete.
- Remove the old Google OAuth callback only after the old Supabase project is no longer needed for rollback.
- Pause or delete the old project only after production has been stable and backups have been verified.
