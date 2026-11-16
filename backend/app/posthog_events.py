"""Small, failure-tolerant PostHog capture helpers for backend-owned events."""

from __future__ import annotations

from typing import Any

import requests

from app.config import Config


POSTHOG_CAPTURE_TIMEOUT_SECONDS = 3


def capture_posthog_event(
    distinct_id: str,
    event: str,
    *,
    properties: dict[str, Any] | None = None,
    person_properties: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> bool:
    """Capture an event without allowing analytics failures to break app flows."""
    project_token = Config.POSTHOG_PROJECT_TOKEN
    if not project_token or not distinct_id or not event:
        return False

    event_properties = {
        "distinct_id": str(distinct_id),
        "$lib": "pailin-abroad-backend",
        **(properties or {}),
    }
    if person_properties:
        event_properties["$set"] = {
            key: value
            for key, value in person_properties.items()
            if value is not None
        }

    payload: dict[str, Any] = {
        "api_key": project_token,
        "event": event,
        "properties": event_properties,
    }
    if timestamp:
        payload["timestamp"] = timestamp

    capture_url = f"{Config.POSTHOG_HOST.rstrip('/')}/i/v0/e/"
    try:
        response = requests.post(
            capture_url,
            json=payload,
            timeout=POSTHOG_CAPTURE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as error:
        print(
            f"PostHog capture failed event={event} distinct_id={distinct_id}: {error}",
            flush=True,
        )
        return False


def capture_posthog_batch(events: list[dict[str, Any]]) -> bool:
    """Capture a prepared batch, primarily for one-off historical backfills."""
    project_token = Config.POSTHOG_PROJECT_TOKEN
    if not project_token or not events:
        return False

    capture_url = f"{Config.POSTHOG_HOST.rstrip('/')}/batch/"
    try:
        response = requests.post(
            capture_url,
            json={"api_key": project_token, "batch": events},
            timeout=POSTHOG_CAPTURE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as error:
        print(f"PostHog batch capture failed: {error}", flush=True)
        return False


def capture_membership_state(
    distinct_id: str,
    *,
    source: str,
    event_type: str,
    is_paid: bool,
    subscription_status: str | None,
    billing_provider: str | None,
    current_period_end: str | None,
    cancel_at_period_end: bool,
    plan_id: str | None = None,
    environment: str | None = None,
    event_id: str | None = None,
    extra_properties: dict[str, Any] | None = None,
) -> bool:
    """Capture the canonical membership change and update the person's current state."""
    properties = {
        "source": source,
        "membership_event_type": event_type,
        "is_paid": is_paid,
        "subscription_status": subscription_status,
        "billing_provider": billing_provider,
        "current_period_end": current_period_end,
        "cancel_at_period_end": cancel_at_period_end,
        "plan_id": plan_id,
        "environment": environment,
        **(extra_properties or {}),
    }
    if event_id:
        properties["$insert_id"] = event_id

    return capture_posthog_event(
        distinct_id,
        "membership_status_changed",
        properties={key: value for key, value in properties.items() if value is not None},
        person_properties={
            "is_paid": is_paid,
            "subscription_status": subscription_status,
            "billing_provider": billing_provider,
            "membership_source": source,
            "current_period_end": current_period_end,
            "cancel_at_period_end": cancel_at_period_end,
            "current_plan_id": plan_id,
            "membership_environment": environment,
        },
    )
