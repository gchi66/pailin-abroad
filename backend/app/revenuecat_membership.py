from datetime import datetime, timezone
from urllib.parse import quote
from uuid import UUID

import requests

from app.config import Config
from app.supabase_client import supabase_admin


REVENUECAT_API_BASE_URL = "https://api.revenuecat.com/v1"
FULL_ACCESS_ENTITLEMENT_ID = "full_access"
APP_STORE_STORES = {"app_store", "mac_app_store"}
PLAY_STORE_STORES = {"play_store"}
STRIPE_STORES = {"stripe"}
ACTIVE_EVENT_TYPES = {
    "INITIAL_PURCHASE",
    "RENEWAL",
    "NON_RENEWING_PURCHASE",
    "PRODUCT_CHANGE",
    "UNCANCELLATION",
    "SUBSCRIPTION_EXTENDED",
    "TEMPORARY_ENTITLEMENT_GRANT",
}
STRIPE_ACTIVE_STATUSES = {"active", "trialing"}


class RevenueCatAPIError(Exception):
    pass


def is_uuid(value):
    if not value:
        return False

    try:
        UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def is_guest_revenuecat_app_user_id(value):
    if not isinstance(value, str) or not value.startswith("guest:"):
        return False
    return is_uuid(value.split("guest:", 1)[1])


def _parse_iso8601(value):
    if not value:
        return None

    try:
        normalized = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _to_iso8601(value):
    dt = _parse_iso8601(value) if isinstance(value, str) else value
    if not dt:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def _is_future(date_value):
    dt = _parse_iso8601(date_value)
    if not dt:
        return False
    return dt > datetime.now(timezone.utc)


def _is_stripe_active(user_row):
    if not isinstance(user_row, dict):
        return False

    has_stripe_identity = bool(
        user_row.get("stripe_subscription_id") or user_row.get("stripe_customer_id")
    )
    if not has_stripe_identity:
        return False

    subscription_status = str(user_row.get("subscription_status") or "").lower()
    if subscription_status in STRIPE_ACTIVE_STATUSES:
        return True

    return bool(
        user_row.get("cancel_at_period_end") and _is_future(user_row.get("current_period_end"))
    )


def _pick_latest_subscription(subscriptions, preferred_product_id=None):
    if not isinstance(subscriptions, dict):
        return None

    candidates = []
    if preferred_product_id and preferred_product_id in subscriptions:
        candidates.append(subscriptions.get(preferred_product_id) or {})
    candidates.extend(
        subscription
        for product_id, subscription in subscriptions.items()
        if product_id != preferred_product_id and isinstance(subscription, dict)
    )

    def sort_key(subscription):
        expires = _parse_iso8601(subscription.get("expires_date"))
        purchase = _parse_iso8601(subscription.get("purchase_date"))
        original_purchase = _parse_iso8601(subscription.get("original_purchase_date"))
        return (
            expires or purchase or original_purchase or datetime.min.replace(tzinfo=timezone.utc)
        )

    valid_candidates = [candidate for candidate in candidates if isinstance(candidate, dict)]
    if not valid_candidates:
        return None
    return max(valid_candidates, key=sort_key)


def _has_app_store_history(subscriber):
    subscriptions = subscriber.get("subscriptions") or {}
    for subscription in subscriptions.values():
        if isinstance(subscription, dict) and subscription.get("store") in APP_STORE_STORES:
            return True

    non_subscriptions = subscriber.get("non_subscriptions") or {}
    for purchases in non_subscriptions.values():
        for purchase in purchases or []:
            if isinstance(purchase, dict) and purchase.get("store") in APP_STORE_STORES:
                return True

    other_purchases = subscriber.get("other_purchases") or {}
    for purchase in other_purchases.values():
        if isinstance(purchase, dict) and purchase.get("store") in APP_STORE_STORES:
            return True

    return False


def _normalize_platform_hint(value):
    normalized = str(value or "").strip().lower()
    if normalized in {"ios", "iphone", "ipad"}:
        return "ios"
    if normalized in {"android"}:
        return "android"
    return None


def _normalize_billing_provider(store_value):
    normalized = str(store_value or "").strip().lower()
    if normalized in APP_STORE_STORES:
        return "app_store"
    if normalized in PLAY_STORE_STORES:
        return "play_store"
    if normalized in STRIPE_STORES:
        return "stripe"
    return None


def _normalize_revenuecat_environment(value):
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"production", "sandbox", "unknown"}:
        return normalized
    return "unknown"


def _has_revenuecat_history(subscriber):
    return any(
        bool(subscriber.get(field))
        for field in ("entitlements", "subscriptions", "non_subscriptions", "other_purchases")
    )


def _normalized_status(has_access, is_lifetime, period_type, cancellation_detected, billing_issue, paused, has_history):
    normalized_period_type = str(period_type or "").lower()

    if is_lifetime and has_access:
        return "lifetime"
    if paused and has_access:
        return "paused"
    if has_access and normalized_period_type in {"trial", "intro"}:
        return "trialing"
    if has_access:
        return "active"
    if billing_issue:
        return "billing_issue"
    if paused:
        return "paused"
    if cancellation_detected and not has_access:
        return "cancelled"
    if has_history:
        return "expired"
    return None


def fetch_revenuecat_subscriber(app_user_id):
    api_key = Config.REVENUECAT_SECRET_API_KEY
    if not api_key:
        raise RevenueCatAPIError("REVENUECAT_SECRET_API_KEY is not configured")

    url = f"{REVENUECAT_API_BASE_URL}/subscribers/{quote(str(app_user_id), safe='')}"
    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=10,
    )

    if response.status_code >= 400:
        raise RevenueCatAPIError(
            f"RevenueCat subscriber lookup failed with status {response.status_code}: {response.text[:300]}"
        )

    try:
        return response.json()
    except Exception as exc:
        raise RevenueCatAPIError("RevenueCat returned invalid JSON") from exc


def derive_membership_state_from_subscriber(subscriber_response):
    subscriber = (subscriber_response or {}).get("subscriber") or {}
    entitlements = subscriber.get("entitlements") or {}
    full_access = entitlements.get(FULL_ACCESS_ENTITLEMENT_ID) or {}
    subscriptions = subscriber.get("subscriptions") or {}

    product_identifier = full_access.get("product_identifier")
    matched_subscription = _pick_latest_subscription(subscriptions, product_identifier)
    expires_at = full_access.get("expires_date")
    if not expires_at and matched_subscription:
        expires_at = matched_subscription.get("expires_date")

    is_lifetime = bool(full_access) and not expires_at
    has_access = bool(full_access) and (is_lifetime or _is_future(expires_at))

    period_type = str((matched_subscription or {}).get("period_type") or "").lower()
    unsubscribe_detected_at = (matched_subscription or {}).get("unsubscribe_detected_at")
    billing_issues_detected_at = (matched_subscription or {}).get("billing_issues_detected_at")
    refunded_at = (matched_subscription or {}).get("refunded_at")
    auto_resume_date = (matched_subscription or {}).get("auto_resume_date")

    has_history = _has_revenuecat_history(subscriber)
    subscription_status = _normalized_status(
        has_access=has_access,
        is_lifetime=is_lifetime,
        period_type=period_type,
        cancellation_detected=bool(unsubscribe_detected_at or refunded_at),
        billing_issue=bool(billing_issues_detected_at),
        paused=bool(auto_resume_date),
        has_history=has_history,
    )

    cancel_at_period_end = bool(has_access and unsubscribe_detected_at)
    cancel_at = None
    if unsubscribe_detected_at:
        cancel_at = _to_iso8601(unsubscribe_detected_at)
    elif refunded_at:
        cancel_at = _to_iso8601(refunded_at)

    matched_store = _normalize_billing_provider((matched_subscription or {}).get("store"))
    billing_provider = matched_store
    platform_hint = _normalize_platform_hint((subscriber_response or {}).get("platform_hint"))
    if not billing_provider and _has_app_store_history(subscriber):
        billing_provider = "app_store"
    elif not billing_provider and has_access and platform_hint == "ios":
        billing_provider = "app_store"

    revenuecat_environment = _normalize_revenuecat_environment(
        (subscriber_response or {}).get("environment")
        or subscriber.get("environment")
        or full_access.get("environment")
        or (matched_subscription or {}).get("environment")
    )
    current_period_end = None if is_lifetime else _to_iso8601(expires_at)

    return {
        "has_access": has_access,
        "subscription_status": subscription_status,
        "current_period_end": current_period_end,
        "cancel_at_period_end": cancel_at_period_end,
        "cancel_at": cancel_at,
        "billing_provider": billing_provider,
        "membership_source": "revenuecat",
        "revenuecat_environment": revenuecat_environment,
        "has_revenuecat_history": has_history,
    }


def build_membership_updates_from_webhook_event(event):
    event_type = event.get("type")
    expiration_at_ms = event.get("expiration_at_ms")
    cancel_reason = event.get("cancel_reason")

    expiration_iso = None
    has_access = False
    if expiration_at_ms not in (None, ""):
        try:
            dt = datetime.fromtimestamp(int(expiration_at_ms) / 1000, tz=timezone.utc)
            expiration_iso = dt.isoformat()
            has_access = dt > datetime.now(timezone.utc)
        except Exception:
            expiration_iso = None
            has_access = False

    cancel_at_period_end = False
    cancel_at = None
    if event_type == "CANCELLATION" and cancel_reason == "UNSUBSCRIBE" and has_access:
        cancel_at_period_end = True
        cancel_at = expiration_iso
    elif event_type == "SUBSCRIPTION_PAUSED" and has_access:
        cancel_at_period_end = True
        cancel_at = expiration_iso

    if event_type == "UNCANCELLATION":
        cancel_at_period_end = False
        cancel_at = None
    elif event_type == "EXPIRATION":
        cancel_at_period_end = False
        cancel_at = expiration_iso

    has_history = event_type != "TEST"
    subscription_status = _normalized_status(
        has_access=has_access,
        is_lifetime=False,
        period_type=event.get("period_type"),
        cancellation_detected=event_type == "CANCELLATION",
        billing_issue=event_type == "BILLING_ISSUE",
        paused=event_type == "SUBSCRIPTION_PAUSED",
        has_history=has_history,
    )

    billing_provider = _normalize_billing_provider(event.get("store"))
    revenuecat_environment = _normalize_revenuecat_environment(event.get("environment"))

    return {
        "has_access": has_access,
        "subscription_status": subscription_status,
        "current_period_end": expiration_iso,
        "cancel_at_period_end": cancel_at_period_end,
        "cancel_at": cancel_at,
        "billing_provider": billing_provider,
        "membership_source": "revenuecat",
        "revenuecat_environment": revenuecat_environment,
    }


def update_user_membership(user_id, membership_state, clear_missing_app_store_provider=False):
    existing_user = (
        supabase_admin.table("users")
        .select(
            "manual_membership, billing_provider, stripe_customer_id, stripe_subscription_id, "
            "subscription_status, current_period_end, cancel_at_period_end, "
            "membership_source, revenuecat_environment"
        )
        .eq("id", user_id)
        .single()
        .execute()
    )
    existing_user_row = existing_user.data or {}

    manual_active = bool(existing_user_row.get("manual_membership"))
    stripe_active = _is_stripe_active(existing_user_row)
    revenuecat_active = bool(membership_state["has_access"])
    effective_paid = manual_active or stripe_active or revenuecat_active
    existing_provider = existing_user_row.get("billing_provider")
    preserve_stripe_fields = existing_provider == "stripe" and stripe_active

    updates = {
        "is_paid": effective_paid,
    }
    if not preserve_stripe_fields:
        updates["subscription_status"] = membership_state["subscription_status"]
        updates["current_period_end"] = membership_state["current_period_end"]
        updates["cancel_at_period_end"] = membership_state["cancel_at_period_end"]
        updates["cancel_at"] = membership_state["cancel_at"]

    incoming_provider = membership_state.get("billing_provider")
    if incoming_provider:
        updates["billing_provider"] = incoming_provider

    incoming_membership_source = membership_state.get("membership_source")
    if incoming_membership_source:
        updates["membership_source"] = incoming_membership_source

    incoming_environment = membership_state.get("revenuecat_environment")
    existing_environment = existing_user_row.get("revenuecat_environment")
    if incoming_environment == "production":
        updates["revenuecat_environment"] = incoming_environment
    elif incoming_environment == "sandbox":
        if existing_environment != "production":
            updates["revenuecat_environment"] = incoming_environment
    elif incoming_environment == "unknown":
        if existing_environment not in {"production", "sandbox"}:
            updates["revenuecat_environment"] = incoming_environment

    result = supabase_admin.table("users").update(updates).eq("id", user_id).execute()
    access_sources = {
        "manual_active": manual_active,
        "stripe_active": stripe_active,
        "revenuecat_active": revenuecat_active,
        "effective_paid": effective_paid,
    }
    return updates, result, access_sources
