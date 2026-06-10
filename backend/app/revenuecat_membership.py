from datetime import datetime, timezone
from urllib.parse import quote

import requests

from app.config import Config
from app.supabase_client import supabase_admin


REVENUECAT_API_BASE_URL = "https://api.revenuecat.com/v1"
FULL_ACCESS_ENTITLEMENT_ID = "full_access"
APP_STORE_STORES = {"app_store", "mac_app_store"}


class RevenueCatAPIError(Exception):
    pass


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


def _has_revenuecat_history(subscriber):
    return any(
        bool(subscriber.get(field))
        for field in ("entitlements", "subscriptions", "non_subscriptions", "other_purchases")
    )


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

    if is_lifetime and has_access:
        subscription_status = "lifetime"
    elif has_access and period_type in {"trial", "intro"}:
        subscription_status = "trialing"
    elif has_access:
        subscription_status = "active"
    elif billing_issues_detected_at:
        subscription_status = "billing_issue"
    elif auto_resume_date:
        subscription_status = "paused"
    elif full_access or matched_subscription:
        subscription_status = "expired"
    else:
        subscription_status = None

    cancel_at_period_end = bool(has_access and unsubscribe_detected_at)
    cancel_at = None
    if unsubscribe_detected_at:
        cancel_at = _to_iso8601(unsubscribe_detected_at)
    elif refunded_at:
        cancel_at = _to_iso8601(refunded_at)

    billing_provider = "app_store" if _has_app_store_history(subscriber) else None
    current_period_end = None if is_lifetime else _to_iso8601(expires_at)

    return {
        "has_access": has_access,
        "subscription_status": subscription_status,
        "current_period_end": current_period_end,
        "cancel_at_period_end": cancel_at_period_end,
        "cancel_at": cancel_at,
        "billing_provider": billing_provider,
        "has_revenuecat_history": _has_revenuecat_history(subscriber),
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

    if event_type == "EXPIRATION":
        subscription_status = "expired"
    elif event_type == "BILLING_ISSUE":
        subscription_status = "billing_issue"
    elif event_type == "SUBSCRIPTION_PAUSED":
        subscription_status = "paused"
    elif event_type == "CANCELLATION":
        subscription_status = "cancelled"
    elif has_access and event.get("period_type") in {"TRIAL", "INTRO"}:
        subscription_status = "trialing"
    elif event_type in {
        "INITIAL_PURCHASE",
        "RENEWAL",
        "NON_RENEWING_PURCHASE",
        "PRODUCT_CHANGE",
        "UNCANCELLATION",
        "SUBSCRIPTION_EXTENDED",
        "TEMPORARY_ENTITLEMENT_GRANT",
    } and has_access:
        subscription_status = "active"
    else:
        subscription_status = (event_type or "unknown").lower()

    return {
        "is_paid": has_access,
        "subscription_status": subscription_status,
        "current_period_end": expiration_iso,
        "cancel_at_period_end": cancel_at_period_end,
        "cancel_at": cancel_at,
    }


def update_user_membership(user_id, membership_state):
    updates = {
        "is_paid": membership_state["has_access"],
        "subscription_status": membership_state["subscription_status"],
        "current_period_end": membership_state["current_period_end"],
        "cancel_at_period_end": membership_state["cancel_at_period_end"],
        "cancel_at": membership_state["cancel_at"],
    }

    if membership_state.get("billing_provider"):
        updates["billing_provider"] = membership_state["billing_provider"]

    result = supabase_admin.table("users").update(updates).eq("id", user_id).execute()
    return updates, result
