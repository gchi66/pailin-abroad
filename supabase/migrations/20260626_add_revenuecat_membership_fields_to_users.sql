alter table public.users
add column if not exists membership_source text,
add column if not exists revenuecat_environment text,
add column if not exists billing_provider text;

comment on column public.users.membership_source is
'Deterministic paid membership source: manual, stripe, revenuecat, or null.';

comment on column public.users.revenuecat_environment is
'RevenueCat environment when known: sandbox, production, unknown, or null.';

comment on column public.users.billing_provider is
'Billing platform/provider when known, such as stripe, app_store, or play_store.';

update public.users
set membership_source = 'revenuecat'
where is_paid = true
  and billing_provider is null
  and coalesce(stripe_customer_id, '') = ''
  and coalesce(stripe_subscription_id, '') = ''
  and membership_source is null;
