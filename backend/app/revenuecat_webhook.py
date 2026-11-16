from flask import Blueprint, jsonify, request

from app.config import Config
from app.revenuecat_membership import (
    build_membership_updates_from_webhook_event,
    is_uuid,
    update_user_membership,
)
from app.posthog_events import capture_membership_state


revenuecat_webhook = Blueprint("revenuecat_webhook", __name__)

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

    membership_state = build_membership_updates_from_webhook_event(event)

    updated_user_id = None
    applied_updates = None
    access_sources = None
    for candidate_user_id in user_candidates:
        if not is_uuid(candidate_user_id):
            print(
                f"RevenueCat webhook skipping non-UUID candidate={candidate_user_id} type={event_type}",
                flush=True,
            )
            continue

        updates, result, sources = update_user_membership(
            candidate_user_id,
            membership_state,
        )
        if result.data:
            updated_user_id = candidate_user_id
            applied_updates = updates
            access_sources = sources
            break

    if not updated_user_id:
        print(
            f"⚠️ RevenueCat webhook user not found for candidates={user_candidates} type={event_type}",
            flush=True,
        )
        return jsonify({"status": "ignored", "reason": "user_not_found"}), 200

    print(
        "RevenueCat webhook membership update succeeded "
        f"for user_id={updated_user_id} type={event_type} "
        f"updates={applied_updates} access_sources={access_sources}",
        flush=True,
    )

    capture_membership_state(
        updated_user_id,
        source="revenuecat",
        event_type=str(event_type or "UNKNOWN"),
        is_paid=bool(applied_updates.get("is_paid")),
        subscription_status=applied_updates.get("subscription_status"),
        billing_provider=applied_updates.get("billing_provider"),
        current_period_end=applied_updates.get("current_period_end"),
        cancel_at_period_end=bool(applied_updates.get("cancel_at_period_end")),
        plan_id=event.get("product_id"),
        environment=event.get("environment"),
        event_id=event.get("id"),
        extra_properties={
            "period_type": event.get("period_type"),
            "store": event.get("store"),
            "currency": event.get("currency"),
            "price": event.get("price_in_purchased_currency"),
        },
    )

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
