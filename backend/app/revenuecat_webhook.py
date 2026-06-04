from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.config import Config
from app.supabase_client import supabase_admin


revenuecat_webhook = Blueprint("revenuecat_webhook", __name__)

ACTIVE_EVENT_TYPES = {
    "INITIAL_PURCHASE",
    "RENEWAL",
    "NON_RENEWING_PURCHASE",
    "PRODUCT_CHANGE",
    "UNCANCELLATION",
    "SUBSCRIPTION_EXTENDED",
    "TEMPORARY_ENTITLEMENT_GRANT",
}


def _ms_to_iso8601(value):
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def _ms_in_future(value):
    if value in (None, ""):
        return False
    try:
        return int(value) > int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    except Exception:
        return False


def _candidate_user_ids(event):
    candidates = [
        event.get("app_user_id"),
        event.get("original_app_user_id"),
    ]
    candidates.extend(event.get("aliases") or [])

    unique_candidates = []
    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        unique_candidates.append(candidate)
    return unique_candidates


def _normalized_status(event_type, period_type, has_access):
    if event_type == "EXPIRATION":
        return "expired"
    if event_type == "BILLING_ISSUE":
        return "billing_issue"
    if event_type == "SUBSCRIPTION_PAUSED":
        return "paused"
    if event_type == "CANCELLATION":
        return "cancelled"
    if has_access and period_type in {"TRIAL", "INTRO"}:
        return "trialing"
    if event_type in ACTIVE_EVENT_TYPES and has_access:
        return "active"
    return (event_type or "unknown").lower()


def _build_user_updates(event):
    event_type = event.get("type")
    expiration_at_ms = event.get("expiration_at_ms")
    cancel_reason = event.get("cancel_reason")
    has_access = _ms_in_future(expiration_at_ms)
    expiration_iso = _ms_to_iso8601(expiration_at_ms)

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

    return {
        "is_paid": has_access,
        "subscription_status": _normalized_status(
            event_type, event.get("period_type"), has_access
        ),
        "current_period_end": expiration_iso,
        "cancel_at_period_end": cancel_at_period_end,
        "cancel_at": cancel_at,
    }


@revenuecat_webhook.route("/api/revenuecat/webhook", methods=["POST"])
def revenuecat_webhook_handler():
    auth_header = request.headers.get("Authorization")
    expected_auth = Config.REVENUECAT_WEBHOOK_AUTH_SECRET

    if not expected_auth:
        print("❌ REVENUECAT_WEBHOOK_AUTH_SECRET is not configured", flush=True)
        return jsonify({"error": "Webhook auth not configured"}), 500

    if auth_header != expected_auth:
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    event = payload.get("event")
    if not isinstance(event, dict):
        return jsonify({"error": "Missing event payload"}), 400

    event_type = event.get("type")
    if event_type == "TEST":
        return jsonify({"status": "ignored", "reason": "test_event"}), 200

    user_candidates = _candidate_user_ids(event)
    if not user_candidates:
        return jsonify({"status": "ignored", "reason": "no_app_user_id"}), 200

    updates = _build_user_updates(event)

    updated_user_id = None
    for candidate_user_id in user_candidates:
        result = (
            supabase_admin.table("users")
            .update(updates)
            .eq("id", candidate_user_id)
            .execute()
        )
        if result.data:
            updated_user_id = candidate_user_id
            break

    if not updated_user_id:
        print(
            f"⚠️ RevenueCat webhook user not found for candidates={user_candidates} type={event_type}",
            flush=True,
        )
        return jsonify({"status": "ignored", "reason": "user_not_found"}), 200

    return (
        jsonify(
            {
                "status": "success",
                "event_type": event_type,
                "user_id": updated_user_id,
            }
        ),
        200,
    )
