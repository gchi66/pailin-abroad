from flask import Blueprint, jsonify, request

from app.config import Config
from app.revenuecat_membership import (
    build_membership_updates_from_webhook_event,
    is_uuid,
)
from app.supabase_client import supabase_admin


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

    updates = build_membership_updates_from_webhook_event(event)

    updated_user_id = None
    for candidate_user_id in user_candidates:
        if not is_uuid(candidate_user_id):
            print(
                f"RevenueCat webhook skipping non-UUID candidate={candidate_user_id} type={event_type}",
                flush=True,
            )
            continue

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
