"""Backfill historical signups and current membership state into PostHog.

Dry-run by default. Pass --apply after configuring POSTHOG_PROJECT_TOKEN.
"""

import argparse

from app.config import Config
from app.posthog_events import capture_posthog_batch
from app.supabase_client import supabase_admin


USER_SELECT = (
    "id,username,email,created_at,is_admin,is_paid,onboarding_completed,subscription_status,"
    "billing_provider,membership_source,current_period_end,cancel_at_period_end"
)
BATCH_SIZE = 100


def _fetch_users():
    users = []
    offset = 0
    while True:
        response = (
            supabase_admin.table("users")
            .select(USER_SELECT)
            .range(offset, offset + BATCH_SIZE - 1)
            .execute()
        )
        rows = response.data or []
        users.extend(rows)
        if len(rows) < BATCH_SIZE:
            return users
        offset += BATCH_SIZE


def _signup_event(user):
    user_id = user["id"]
    created_at = user.get("created_at")
    person_properties = {
        "email": user.get("email"),
        "username": user.get("username"),
        "signed_up_at": created_at,
        "is_admin": user.get("is_admin") is True,
        "is_paid": user.get("is_paid") is True,
        "onboarding_completed": user.get("onboarding_completed") is True,
        "subscription_status": user.get("subscription_status"),
        "billing_provider": user.get("billing_provider"),
        "membership_source": user.get("membership_source"),
        "current_period_end": user.get("current_period_end"),
        "cancel_at_period_end": user.get("cancel_at_period_end") is True,
    }
    event = {
        "event": "sign_up_completed",
        "properties": {
            "distinct_id": user_id,
            "$lib": "pailin-abroad-backend-backfill",
            "$insert_id": f"signup-backfill:{user_id}",
            "method": "historical_backfill",
            "$set": {
                key: value
                for key, value in person_properties.items()
                if value is not None
            },
        },
    }
    if created_at:
        event["timestamp"] = created_at
    return event


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    users = _fetch_users()
    print(f"Prepared {len(users)} signup/person records for PostHog.")
    if not args.apply:
        print("Dry run only. Re-run with --apply to send them.")
        return

    if not Config.POSTHOG_PROJECT_TOKEN:
        raise RuntimeError("POSTHOG_PROJECT_TOKEN is required for --apply")

    events = [_signup_event(user) for user in users]
    for start in range(0, len(events), BATCH_SIZE):
        batch = events[start:start + BATCH_SIZE]
        if not capture_posthog_batch(batch):
            raise RuntimeError(f"PostHog rejected batch beginning at record {start}")
        print(f"Sent {min(start + len(batch), len(events))}/{len(events)} records.")


if __name__ == "__main__":
    main()
