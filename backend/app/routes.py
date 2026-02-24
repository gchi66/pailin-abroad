from flask import Blueprint, request, jsonify
from functools import wraps
from app.supabase_client import supabase, supabase_admin
from app.resolver import resolve_lesson
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import re
import os
from datetime import datetime, timedelta, timezone
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from app.config import Config
from app.pricing_utils import resolve_region_key
import requests

routes = Blueprint("routes", __name__)

CATEGORY_LABELS = {
    "verbs_and_tenses": "Verbs and Tenses",
    "nouns_and_articles": "Nouns and Articles",
    "adjectives": "Adjectives",
    "pronouns": "Pronouns",
    "other_concepts": "Other Concepts",
}

PUBLIC_TRY_LESSON_IDS = [
    "a34f5a4b-0729-430e-9b92-900dcad2f977",
    "5f9d09b4-ed35-40ac-b89f-50dbd7e96c0c",
    "27e50504-7021-4a7b-b30d-0cae34a094bf",
]

LESSON_AUDIO_BUCKET = "lesson-audio"
TRY_AUDIO_TTL_SECONDS = 2 * 60 * 60
TRY_AUDIO_CACHE_TTL_SECONDS = 50 * 60
TRY_AUDIO_MAX_WORKERS = 8
_try_audio_cache = {}



def _sign_audio_path(path):
    if not path:
        return None
    try:
        result = supabase_admin.storage.from_(LESSON_AUDIO_BUCKET).create_signed_url(
            path, TRY_AUDIO_TTL_SECONDS
        )
        return result.get("signedURL") or result.get("signedUrl")
    except Exception as e:
        print(f"Warning: could not sign audio path {path}: {e}")
        return None


def _get_try_audio_cache(lesson_id):
    cached = _try_audio_cache.get(lesson_id)
    if not cached:
        return None
    if time.time() - cached["ts"] > TRY_AUDIO_CACHE_TTL_SECONDS:
        _try_audio_cache.pop(lesson_id, None)
        return None
    return cached["payload"]


def _set_try_audio_cache(lesson_id, payload):
    _try_audio_cache[lesson_id] = {"ts": time.time(), "payload": payload}


def _sign_audio_batch(items):
    results = []
    with ThreadPoolExecutor(max_workers=TRY_AUDIO_MAX_WORKERS) as executor:
        future_map = {
            executor.submit(_sign_audio_path, item["path"]): item
            for item in items
            if item.get("path")
        }
        for future in as_completed(future_map):
            item = future_map[future]
            signed_url = None
            try:
                signed_url = future.result()
            except Exception as e:
                print(f"Warning: signing failed for {item.get('path')}: {e}")
            if signed_url:
                results.append({**item, "signed_url": signed_url})
    return results


def _slugify(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-") or "section"


def _category_label(key: str) -> str:
    if not key:
        return "Uncategorized"
    return CATEGORY_LABELS.get(key, key.replace("_", " ").title())


def _category_slug(key: str) -> str:
    return _slugify(key or "category")


def _section_slug(section: str) -> str:
    return _slugify(section or "section")


def handle_options(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'OPTIONS':
            return '', 204
        return f(*args, **kwargs)
    return decorated_function


@routes.route("/", methods=["GET"])
@handle_options
def home():
    return jsonify({}), 204


@routes.route("/api/pricing", methods=["GET"])
@handle_options
def get_pricing():
    region_key = resolve_region_key()
    tiers_result = (
        supabase
        .table("pricing_tiers")
        .select("billing_period, currency, amount_total, amount_per_month, is_promo, sort_order")
        .eq("active", True)
        .eq("region_key", region_key)
        .order("sort_order", desc=False)
        .execute()
    )

    tiers = tiers_result.data or []
    if not tiers:
        return jsonify({"error": "No active pricing tiers found"}), 404

    currency = tiers[0].get("currency")
    response = {
        "region_key": region_key,
        "currency": currency,
        "plans": [
            {
                "billing_period": tier.get("billing_period"),
                "amount_total": tier.get("amount_total"),
                "amount_per_month": tier.get("amount_per_month"),
                "is_promo": tier.get("is_promo"),
            }
            for tier in tiers
        ],
    }

    return jsonify(response), 200

@routes.route('/api/try-lessons/<lesson_id>/audio-url', methods=['GET'])
@handle_options
def get_try_lesson_audio(lesson_id):
    if lesson_id not in PUBLIC_TRY_LESSON_IDS:
        return jsonify({"error": "Not allowed"}), 403

    try:
        cached = _get_try_audio_cache(lesson_id)
        if cached:
            return jsonify(cached), 200

        lesson_result = (
            supabase_admin
            .table("lessons")
            .select("id, lesson_external_id, conversation_audio_url")
            .eq("id", lesson_id)
            .limit(1)
            .execute()
        )
        lesson_rows = lesson_result.data or []
        if not lesson_rows:
            return jsonify({"error": "Lesson not found"}), 404

        lesson_row = lesson_rows[0]
        lesson_external_id = lesson_row.get("lesson_external_id")
        conversation_path = lesson_row.get("conversation_audio_url")

        conversation = {"path": conversation_path}

        snippets_out = []
        if lesson_external_id:
            snippets_result = (
                supabase_admin
                .table("audio_snippets")
                .select("section, seq, storage_path, audio_key")
                .eq("lesson_external_id", lesson_external_id)
                .execute()
            )
            for row in snippets_result.data or []:
                audio_key = row.get("audio_key")
                storage_path = row.get("storage_path")
                if not audio_key or not storage_path:
                    continue
                snippets_out.append({
                    "audio_key": audio_key,
                    "section": row.get("section"),
                    "seq": row.get("seq"),
                    "storage_path": storage_path,
                })

        phrase_ids = []
        phrases_links = (
            supabase_admin
            .table("lesson_phrases")
            .select("phrase_id")
            .eq("lesson_id", lesson_id)
            .execute()
        )
        for row in phrases_links.data or []:
            phrase_id = row.get("phrase_id")
            if phrase_id:
                phrase_ids.append(phrase_id)

        phrases_out = []
        if phrase_ids:
            phrases_result = (
                supabase_admin
                .table("phrases_audio_snippets")
                .select("phrase_id, variant, seq, storage_path, audio_key")
                .in_("phrase_id", phrase_ids)
                .execute()
            )
            items = []
            for row in phrases_result.data or []:
                audio_key = row.get("audio_key")
                storage_path = row.get("storage_path")
                if not audio_key or not storage_path:
                    continue
                items.append({
                    "audio_key": audio_key,
                    "phrase_id": row.get("phrase_id"),
                    "variant": row.get("variant") or 0,
                    "seq": row.get("seq"),
                    "path": storage_path,
                })
            signed_phrases = _sign_audio_batch(items)
            for row in signed_phrases:
                phrases_out.append({
                    "audio_key": row.get("audio_key"),
                    "phrase_id": row.get("phrase_id"),
                    "variant": row.get("variant") or 0,
                    "seq": row.get("seq"),
                    "signed_url": row.get("signed_url"),
                })

        payload = {
            "conversation": conversation,
            "snippets": snippets_out,
            "phrases": phrases_out,
            "expires_in": TRY_AUDIO_TTL_SECONDS,
        }
        _set_try_audio_cache(lesson_id, payload)
        return jsonify(payload), 200

    except Exception as e:
        print(f"Error generating try lesson audio URLs: {e}")
        return jsonify({"error": "Internal server error"}), 500

@routes.route('/api/login', methods=['GET', 'POST'])
@handle_options
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({
                "error": "MISSING_FIELDS",
                "message": "Email and password are required."
            }), 400

        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if hasattr(response, "error") and response.error:
            error_message = str(response.error)
            if "invalid login credentials" in error_message.lower():
                return jsonify({
                    "error": "INVALID_CREDENTIALS",
                    "message": "Invalid email or password."
                }), 401
            return jsonify({
                "error": "AUTH_ERROR",
                "message": error_message or "Authentication failed."
            }), 401

        session_data = {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": {
                "id": response.user.id,
                "email": response.user.email,
            }
        }

        return jsonify({"message": "Login successful!", "session": session_data}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            "error": "SERVER_ERROR",
            "message": "Internal server error."
        }), 500


@routes.route('/api/user/profile', methods=['GET'])
@handle_options
def get_user_profile():
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)

        if not user_response.user:
            return jsonify({"error": "Invalid token"}), 401

        user_id = user_response.user.id

        # Fetch user data from users table
        result = supabase.table('users').select('*').eq('id', user_id).execute()

        if not result.data:
            return jsonify({"error": "User not found"}), 404

        user_data = result.data[0]

        # Count completed lessons from user_lesson_progress table
        lessons_complete = 0
        try:
            progress_result = supabase.table('user_lesson_progress').select('*', count='exact').eq('user_id', user_id).eq('is_completed', True).execute()
            lessons_complete = progress_result.count if progress_result.count is not None else 0
        except Exception as e:
            print(f"Warning: Could not fetch lesson progress: {e}")
            # Use fallback value of 0 if query fails

        # Prepare profile response with username fallback to email
        profile = {
            "id": user_data.get("id"),
            "name": user_data.get("username") or user_data.get("email", "User"),
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "avatar_image": user_data.get("avatar_image"),
            "is_admin": user_data.get("is_admin", False),
            "created_at": user_data.get("created_at"),
            "lessons_complete": lessons_complete
        }

        return jsonify({"profile": profile}), 200

    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route('/api/user/profile', methods=['PUT'])
@handle_options
def update_user_profile():
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user - handle potential session issues from OTP flow
        try:
            user_response = supabase.auth.get_user(access_token)

            if not user_response.user:
                return jsonify({"error": "Invalid token"}), 401

            user_id = user_response.user.id

        except Exception as auth_error:
            print(f"Auth error with get_user: {auth_error}")
            # Fallback - try to decode the JWT to get user info
            try:
                import jwt
                # Decode without verification since we trust our own tokens in this flow
                decoded = jwt.decode(access_token, options={"verify_signature": False})
                user_id = decoded.get('sub')
                if not user_id:
                    return jsonify({"error": "Invalid token format"}), 401
            except Exception as jwt_error:
                print(f"JWT decode error: {jwt_error}")
                return jsonify({"error": "Invalid token"}), 401

        # Get request data
        data = request.json
        username = data.get('username')
        avatar_image = data.get('avatar_image')
        onboarding_completed = data.get('onboarding_completed')

        # Validate required fields
        if not username:
            return jsonify({"error": "Username is required"}), 400

        # Update user data in users table
        update_data = {
            "username": username.strip()
        }

        # Only update avatar_image if provided
        if avatar_image:
            update_data["avatar_image"] = avatar_image

        # Allow marking onboarding as complete (one-way)
        if onboarding_completed is True:
            update_data["onboarding_completed"] = True
            update_data["is_paid"] = True

        result = supabase.table('users').update(update_data).eq('id', user_id).execute()

        if not result.data:
            return jsonify({"error": "Failed to update profile"}), 400

        return jsonify({
            "message": "Profile updated successfully",
            "profile": {
                "username": username,
                "avatar_image": avatar_image
            }
        }), 200

    except Exception as e:
        print(f"Error updating user profile: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route('/api/user/completed-lessons', methods=['GET'])
@handle_options
def get_completed_lessons():
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)

        if not user_response.user:
            return jsonify({"error": "Invalid token"}), 401

        user_id = user_response.user.id

        # Fetch completed lessons from user_lesson_progress table
        completed_lessons = []
        try:
            progress_result = supabase.table('user_lesson_progress').select('*, lessons(*)').eq('user_id', user_id).eq('is_completed', True).execute()
            completed_lessons = progress_result.data if progress_result.data else []
        except Exception as e:
            print(f"Warning: Could not fetch completed lessons: {e}")
            # Return empty list if query fails

        return jsonify({"completed_lessons": completed_lessons}), 200

    except Exception as e:
        print(f"Error fetching completed lessons: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route('/api/user/next-lesson', methods=['GET'])
@handle_options
def get_next_lesson():
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)

        if not user_response.user:
            return jsonify({"error": "Invalid token"}), 401

        user_id = user_response.user.id

        # Find the highest completed lesson (by level and lesson_order)
        try:
            completed_result = supabase.table('user_lesson_progress').select('*, lessons(level, lesson_order, stage, title, title_th)').eq('user_id', user_id).eq('is_completed', True).execute()
            completed_lessons = completed_result.data if completed_result.data else []

            if not completed_lessons:
                # No completed lessons, find the very first lesson (Beginner Level 1 Lesson 1)
                first_lesson_result = supabase.table('lessons').select('*').eq('stage', 'Beginner').eq('level', 1).eq('lesson_order', 1).limit(1).execute()
                if first_lesson_result.data:
                    first_lesson = first_lesson_result.data[0]
                    return jsonify({
                        "next_lesson": {
                            "level": first_lesson.get("level"),
                            "lesson_order": first_lesson.get("lesson_order"),
                            "title": first_lesson.get("title"),
                            "stage": first_lesson.get("stage"),
                            "formatted": f"Level {first_lesson.get('level')} • Lesson {first_lesson.get('lesson_order')}"
                        }
                    }), 200
                else:
                    # Fallback: try to find the first lesson in Beginner stage, level 1
                    fallback_result = supabase.table('lessons').select('*').eq('stage', 'Beginner').order('level, lesson_order').limit(1).execute()
                    if fallback_result.data:
                        first_lesson = fallback_result.data[0]
                        return jsonify({
                            "next_lesson": {
                                "level": first_lesson.get("level"),
                                "lesson_order": first_lesson.get("lesson_order"),
                                "title": first_lesson.get("title"),
                                "stage": first_lesson.get("stage"),
                                "formatted": f"Level {first_lesson.get('level')} • Lesson {first_lesson.get('lesson_order')}"
                            }
                        }), 200
                    else:
                        return jsonify({"next_lesson": None}), 200

            # Find the highest level and lesson_order among completed lessons
            highest_level = 0
            highest_lesson_order = 0
            highest_stage = "Beginner"

            for progress in completed_lessons:
                lesson = progress.get('lessons', {})
                level = lesson.get('level', 0)
                lesson_order = lesson.get('lesson_order', 0)
                stage = lesson.get('stage', 'Beginner')

                if level > highest_level or (level == highest_level and lesson_order > highest_lesson_order):
                    highest_level = level
                    highest_lesson_order = lesson_order
                    highest_stage = stage

            # Find the next lesson after the highest completed one
            # First try to find the next lesson in the same level
            next_lesson_result = supabase.table('lessons').select('*').eq('level', highest_level).eq('stage', highest_stage).gt('lesson_order', highest_lesson_order).order('lesson_order').limit(1).execute()

            if next_lesson_result.data:
                next_lesson = next_lesson_result.data[0]
            else:
                # No more lessons in this level, try the next level in the same stage
                next_level_result = supabase.table('lessons').select('*').eq('stage', highest_stage).gt('level', highest_level).order('level, lesson_order').limit(1).execute()

                if next_level_result.data:
                    next_lesson = next_level_result.data[0]
                else:
                    # No more lessons in this stage, try the next stage
                    stage_order = ['Beginner', 'Intermediate', 'Advanced', 'Expert']
                    current_stage_index = stage_order.index(highest_stage) if highest_stage in stage_order else 0

                    if current_stage_index < len(stage_order) - 1:
                        next_stage = stage_order[current_stage_index + 1]
                        next_stage_result = supabase.table('lessons').select('*').eq('stage', next_stage).order('level, lesson_order').limit(1).execute()

                        if next_stage_result.data:
                            next_lesson = next_stage_result.data[0]
                        else:
                            return jsonify({"next_lesson": None}), 200
                    else:
                        return jsonify({"next_lesson": None}), 200

            return jsonify({
                "next_lesson": {
                    "level": next_lesson.get("level"),
                    "lesson_order": next_lesson.get("lesson_order"),
                    "title": next_lesson.get("title"),
                    "stage": next_lesson.get("stage"),
                    "formatted": f"Level {next_lesson.get('level')} • Lesson {next_lesson.get('lesson_order')}"
                }
            }), 200

        except Exception as e:
            print(f"Warning: Could not fetch next lesson: {e}")
            return jsonify({"next_lesson": None}), 200

    except Exception as e:
        print(f"Error fetching next lesson: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route('/api/user/pathway-lessons', methods=['GET'])
@handle_options
def get_pathway_lessons():
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)

        if not user_response.user:
            return jsonify({"error": "Invalid token"}), 401

        user_id = user_response.user.id

        # Find the highest completed lesson to determine starting point
        try:
            completed_result = supabase.table('user_lesson_progress').select('*, lessons(level, lesson_order, stage)').eq('user_id', user_id).eq('is_completed', True).execute()
            completed_lessons = completed_result.data if completed_result.data else []

            # Determine starting lesson
            start_level = 1
            start_lesson_order = 1
            start_stage = "Beginner"

            if completed_lessons:
                # Find the highest completed lesson
                highest_level = 0
                highest_lesson_order = 0
                highest_stage = "Beginner"

                for progress in completed_lessons:
                    lesson = progress.get('lessons', {})
                    level = lesson.get('level', 0)
                    lesson_order = lesson.get('lesson_order', 0)
                    stage = lesson.get('stage', 'Beginner')

                    if level > highest_level or (level == highest_level and lesson_order > highest_lesson_order):
                        highest_level = level
                        highest_lesson_order = lesson_order
                        highest_stage = stage

                # Set starting point to the next lesson after highest completed
                start_level = highest_level
                start_lesson_order = highest_lesson_order + 1
                start_stage = highest_stage

            # Fetch the next 5 lessons starting from the determined point
            pathway_lessons = []
            lessons_found = 0
            current_level = start_level
            current_stage = start_stage

            while lessons_found < 5:
                # Try to get lessons from current level starting from start_lesson_order
                lesson_order_filter = start_lesson_order if current_level == start_level else 1

                lessons_result = supabase.table('lessons').select('*').eq('stage', current_stage).eq('level', current_level).gte('lesson_order', lesson_order_filter).order('lesson_order').execute()

                current_lessons = lessons_result.data if lessons_result.data else []

                for lesson in current_lessons:
                    if lessons_found < 5:
                        pathway_lessons.append(lesson)
                        lessons_found += 1
                    else:
                        break

                if lessons_found < 5:
                    # Move to next level in same stage
                    current_level += 1

                    # Check if this level exists in current stage
                    level_check = supabase.table('lessons').select('level').eq('stage', current_stage).eq('level', current_level).limit(1).execute()

                    if not level_check.data:
                        # No more levels in current stage, move to next stage
                        stage_order = ['Beginner', 'Intermediate', 'Advanced', 'Expert']
                        current_stage_index = stage_order.index(current_stage) if current_stage in stage_order else 0

                        if current_stage_index < len(stage_order) - 1:
                            current_stage = stage_order[current_stage_index + 1]
                            current_level = 1
                        else:
                            # No more stages, break
                            break

            return jsonify({"pathway_lessons": pathway_lessons}), 200

        except Exception as e:
            print(f"Warning: Could not fetch pathway lessons: {e}")
            return jsonify({"pathway_lessons": []}), 200

    except Exception as e:
        print(f"Error fetching pathway lessons: {e}")
        return jsonify({"error": "Internal server error"}), 500



@routes.route('/api/signup-email', methods=['POST'])
@handle_options
def signup_email():
    """Send magic link for account creation - no real account until onboarding complete"""
    data = request.json

    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    try:
        # Check if user already has a completed account
        existing_user = supabase.table('users').select('*').eq('email', email).neq('password_hash', 'pending_onboarding').execute()

        if existing_user.data:
            return jsonify({"error": "An account with this email already exists. Please use the login form."}), 400

        # Use sign_up with a temporary password that meets requirements
        # This creates the auth user but they'll set real password in onboarding
        from app.config import Config
        response = supabase.auth.sign_up({
            "email": email,
            "password": "TempPass123!",  # Meets Supabase requirements, will be changed in onboarding
            "options": {
                "email_redirect_to": f"{Config.FRONTEND_URL}/onboarding"
            }
        })

        if hasattr(response, "error") and response.error:
            print("Error from Supabase:", response.error)
            return jsonify({"error": str(response.error)}), 400
        return jsonify({
            "message": "Confirmation email sent! Please check your email to verify your account.",
            "email": email,
            "email_sent": True
        }), 200

    except Exception as e:
        print(f"Error in email signup: {e}")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500



@routes.route('/api/confirm-email', methods=['POST'])
@handle_options
def confirm_email():
    """Handle email confirmation and create user record in database"""
    data = request.json

    # Get the access token from the confirmed user session
    access_token = data.get('access_token')

    if not access_token:
        return jsonify({"error": "Access token is required"}), 400

    try:
        # Get user info from Supabase using the access token
        user_response = supabase.auth.get_user(access_token)

        if not user_response.user:
            return jsonify({"error": "Invalid access token"}), 400

        user_id = user_response.user.id
        user_email = user_response.user.email

        # Check if user record already exists in our database
        existing_user = supabase.table('users').select('*').eq('id', user_id).execute()

        if not existing_user.data:
            # Create user record in users table and mark verified
            user_insert_result = supabase.table('users').insert({
                'id': user_id,
                'email': user_email,
                'username': user_email,  # Default username to email, can be changed in onboarding
                'password_hash': 'pending_onboarding',  # Flag that email is confirmed but password needs to be set
                'is_verified': True
            }).execute()

            if not user_insert_result.data:
                print(f"Warning: User record creation may have failed for {user_email}")
        else:
            # Ensure existing user is marked verified
            try:
                supabase.table('users').update({
                    'is_verified': True
                }).eq('id', user_id).execute()
            except Exception as upd_e:
                print(f"Warning: failed to update existing user's is_verified: {upd_e}")

        return jsonify({
            "message": "Email confirmed successfully!",
            "user_id": user_id,
            "ready_for_onboarding": True
        }), 200

    except Exception as e:
        print(f"Error in email confirmation: {e}")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

@routes.route('/api/set-password', methods=['POST'])
@handle_options
def set_password():
    """Set password for user during onboarding (after email confirmation)"""
    data = request.json

    # Get authorization header with access token
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Authorization token required"}), 401

    access_token = auth_header.split(' ')[1]
    password = data.get('password')

    if not password:
        return jsonify({"error": "Password is required"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters long"}), 400

    try:
        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)

        if not user_response.user:
            return jsonify({"error": "Invalid access token"}), 401

        user_id = user_response.user.id
        user_email = user_response.user.email

        # Update the user's password using Supabase admin API
        try:
            password_update_response = supabase.auth.admin.update_user_by_id(
                user_id,
                {"password": password}
            )

            if hasattr(password_update_response, "error") and password_update_response.error:
                print("Error updating password:", password_update_response.error)
                return jsonify({"error": "Failed to update password"}), 400

        except Exception as password_error:
            print(f"Error updating password with admin API: {password_error}")
            return jsonify({"error": "Failed to update password"}), 400

        # Ensure a user record exists and mark password as set
        existing_user = supabase.table('users').select('*').eq('id', user_id).execute()
        if existing_user.data:
            supabase.table('users').update({
                'password_hash': 'set_by_user_in_onboarding'
            }).eq('id', user_id).execute()
        else:
            supabase.table('users').insert({
                'id': user_id,
                'email': user_email,
                'username': user_email,
                'password_hash': 'set_by_user_in_onboarding'
            }).execute()

        # Now sign in the user with their new password to get a fresh, valid session
        try:
            login_response = supabase.auth.sign_in_with_password({
                "email": user_email,
                "password": password
            })

            if hasattr(login_response, "error") and login_response.error:
                print("Error signing in after password set:", login_response.error)
                # Password was set successfully, but login failed - still return success
                return jsonify({
                    "message": "Password set successfully!",
                    "password_updated": True
                }), 200

            # Return the fresh session data for the frontend to use
            return jsonify({
                "message": "Password set successfully!",
                "password_updated": True,
                "session": {
                    "access_token": login_response.session.access_token,
                    "refresh_token": login_response.session.refresh_token,
                    "user": {
                        "id": login_response.user.id,
                        "email": login_response.user.email
                    }
                }
            }), 200

        except Exception as login_error:
            print(f"Error creating fresh session after password set: {login_error}")
            # Password was set successfully, return success even if session refresh failed
            return jsonify({
                "message": "Password set successfully!",
                "password_updated": True
            }), 200

    except Exception as e:
        print(f"Error in set password: {e}")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

@routes.route('/api/complete-signup', methods=['POST'])
@handle_options
def complete_signup():
    """Complete the signup process - this creates the real account after onboarding"""
    data = request.json

    email = data.get('email')
    password = data.get('password')
    username = data.get('username')
    avatar_image = data.get('avatar_image')

    if not all([email, password, username]):
        return jsonify({"error": "Email, password, and username are required"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters long"}), 400

    try:
        # Check if there's a pending user record for this email
        pending_user = supabase.table('users').select('*').eq('email', email).eq('password_hash', 'pending_onboarding').execute()

        if not pending_user.data:
            return jsonify({"error": "No pending signup found for this email. Please start the signup process again."}), 400

        user_record = pending_user.data[0]
        user_id = user_record['id']

        # Update the user's password in Supabase auth using admin API
        try:
            admin_response = supabase.auth.admin.update_user_by_id(
                user_id,
                {"password": password}
            )

            if hasattr(admin_response, "error") and admin_response.error:
                print("Error updating password:", admin_response.error)
                return jsonify({"error": "Failed to set password"}), 400

        except Exception as password_error:
            print(f"Password update error: {password_error}")
            return jsonify({"error": "Failed to set password. Please try again."}), 400

        # Update user record in users table to mark onboarding as complete
        update_result = supabase.table('users').update({
            'username': username,
            'avatar_image': avatar_image,
            'password_hash': 'set_during_onboarding',
            'onboarding_completed': True,
            'is_paid': True
        }).eq('id', user_id).execute()

        if not update_result.data:
            print(f"Warning: User record update may have failed for {email}")

        # Now sign them in to get a proper session
        signin_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if hasattr(signin_response, "error") and signin_response.error:
            # Account was created but signin failed - they can still login manually
            return jsonify({
                "message": "Account created successfully! Please log in.",
                "account_created": True,
                "signin_required": True
            }), 200

        # Return session data for immediate login
        session_data = {
            "access_token": signin_response.session.access_token,
            "refresh_token": signin_response.session.refresh_token,
            "user": {
                "id": signin_response.user.id,
                "email": signin_response.user.email,
            }
        }

        return jsonify({
            "message": "Account created successfully!",
            "session": session_data,
            "account_created": True
        }), 200

    except Exception as e:
        print(f"Error completing signup: {e}")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

@routes.route('/api/delete_account', methods=['DELETE'])
@handle_options
def delete_account():
    try:
        data = request.json
        access_token = data.get('access_token')

        if not access_token:
            return jsonify({"error": "Access token is required"}), 400

        # Fetch the user's details using the access token
        user_response = supabase.auth.get_user(access_token)

        if user_response.user is None:
            return jsonify({"error": "Unable to retrieve user details. User may not exist."}), 401

        user_id = user_response.user.id

        # Delete the user from auth.users
        supabase.auth.admin.delete_user(user_id)

        # Delete the user from the public.users table
        supabase.table("users").delete().eq("id", user_id).execute()

        # # Check if the delete action was successful
        # if delete_response is None or delete_response.error:
        #     return jsonify({"error": "Failed to delete the user."}), 400

        # Return a success message immediately
        return jsonify({"message": "Account deleted successfully."}), 200


    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route("/contact", methods=["POST"])
@handle_options
def contact():
    data = request.get_json()
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()

    if not (name and email and message):
        return jsonify({"message": "Missing required fields"}), 400

    if not Config.POSTMARK_SERVER_TOKEN or not Config.POSTMARK_FROM or not Config.POSTMARK_TO:
        print("[contact] Missing Postmark config values.")
        return jsonify({"message": "Email service not configured."}), 500

    # Simple per-email rate limit: 5 messages per 24 hours.
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        rate_limit_result = (
            supabase.table("contact_messages")
            .select("id", count="exact")
            .eq("email", email)
            .gte("created_at", cutoff.isoformat())
            .execute()
        )
        recent_count = rate_limit_result.count or 0
        if recent_count >= 5:
            return jsonify({"message": "Too many messages sent from this email. Please try again later."}), 429
    except Exception as e:
        print("[contact] Rate limit check failed:", e)

    body = (
        "You have a new message from your contact form:\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n\n"
        "Message:\n"
        f"{message}\n"
    )

    payload = {
        "From": Config.POSTMARK_FROM,
        "To": Config.POSTMARK_TO,
        "Subject": "New Contact Form Submission",
        "TextBody": body,
        "ReplyTo": email
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": Config.POSTMARK_SERVER_TOKEN
    }

    try:
        response = requests.post("https://api.postmarkapp.com/email", json=payload, headers=headers, timeout=10)
        if response.ok:
            try:
                forwarded_for = request.headers.get("X-Forwarded-For", "")
                ip_address = (forwarded_for.split(",")[0].strip() if forwarded_for else request.remote_addr)
                user_agent = request.headers.get("User-Agent")
                supabase.table("contact_messages").insert({
                    "email": email,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "message": message
                }).execute()
            except Exception as e:
                print("[contact] Failed to log contact message:", e)
            return jsonify({"message": "Email sent successfully!"}), 200
        return jsonify({"message": "Failed to send email."}), 500
    except Exception as e:
        print("Error sending email:", e)
        return jsonify({"message": "Failed to send email."}), 500


@routes.route("/api/notify-comment", methods=["POST"])
@handle_options
def notify_comment():
    data = request.get_json() or {}
    comment_id = (data.get("comment_id") or "").strip()

    if not comment_id:
        return jsonify({"error": "comment_id is required"}), 400

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Authorization token required"}), 401

    access_token = auth_header.split(" ")[1]
    user_response = supabase.auth.get_user(access_token)
    if not user_response.user:
        return jsonify({"error": "Invalid token"}), 401

    if not Config.POSTMARK_SERVER_TOKEN or not Config.POSTMARK_FROM:
        print("[notify-comment] Missing Postmark config values.")
        return jsonify({"error": "Email service not configured."}), 500

    try:
        comment_result = (
            supabase_admin.table("comments")
            .select(
                "id, body, body_th, created_at, lesson_id, user_id,"
                " lessons(title, level, lesson_order, stage),"
                " users(username, email, is_admin)"
            )
            .eq("id", comment_id)
            .single()
            .execute()
        )
    except Exception as e:
        print("[notify-comment] Failed to fetch comment:", e)
        return jsonify({"error": "Failed to fetch comment"}), 500

    comment = comment_result.data if comment_result else None
    if not comment:
        return jsonify({"error": "Comment not found"}), 404

    if comment.get("user_id") != user_response.user.id:
        return jsonify({"error": "Not authorized to notify this comment"}), 403

    commenter = comment.get("users") or {}
    if commenter.get("is_admin"):
        return jsonify({"message": "Skipped admin comment"}), 200

    lesson = comment.get("lessons") or {}
    lesson_title = lesson.get("title") or "Lesson"
    lesson_level = lesson.get("level")
    lesson_order = lesson.get("lesson_order")
    lesson_stage = lesson.get("stage")
    lesson_label_parts = [lesson_title]
    if lesson_stage or lesson_level or lesson_order:
        label_bits = []
        if lesson_stage:
            label_bits.append(str(lesson_stage))
        if lesson_level:
            label_bits.append(f"Level {lesson_level}")
        if lesson_order:
            label_bits.append(f"Lesson {lesson_order}")
        lesson_label_parts.append(f"({', '.join(label_bits)})")
    lesson_label = " ".join(lesson_label_parts)

    lesson_url = f"{Config.FRONTEND_URL.rstrip('/')}/lesson/{comment.get('lesson_id')}"
    commenter_name = commenter.get("username") or commenter.get("email") or "Anonymous"
    comment_body = comment.get("body") or ""
    comment_body_th = comment.get("body_th") or ""
    body_parts = [
        "New comment posted:",
        "",
        f"From: {commenter_name}",
        f"Email: {commenter.get('email') or 'Unknown'}",
        f"Lesson: {lesson_label}",
        f"Link: {lesson_url}",
        "",
        "Comment:",
        comment_body,
    ]
    if comment_body_th:
        body_parts += ["", "Comment (TH):", comment_body_th]

    payload = {
        "From": Config.POSTMARK_FROM,
        "To": Config.POSTMARK_TO or Config.RECIPIENT_EMAIL,
        "Subject": f"New comment on {lesson_title}",
        "TextBody": "\n".join(body_parts),
        "ReplyTo": commenter.get("email") or None,
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": Config.POSTMARK_SERVER_TOKEN,
    }

    try:
        response = requests.post(
            "https://api.postmarkapp.com/email",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if response.ok:
            return jsonify({"message": "Notification sent"}), 200
        print("[notify-comment] Postmark failed:", response.text)
        return jsonify({"error": "Failed to send email"}), 500
    except Exception as e:
        print("[notify-comment] Error sending email:", e)
        return jsonify({"error": "Failed to send email"}), 500


@routes.route("/api/lessons/<lesson_id>/resolved", methods=["GET"])
@handle_options
def get_lesson_resolved(lesson_id):
    lang = (request.args.get("lang") or "en").lower()
    if lang not in ("en", "th"):
        return jsonify({"error": "lang must be 'en' or 'th'"}), 400

    # Check if user is authenticated and has paid access
    is_public_try_lesson = lesson_id in PUBLIC_TRY_LESSON_IDS
    is_locked = not is_public_try_lesson
    user_id = None
    lesson_row = None

    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        try:
            access_token = auth_header.split(' ')[1]
            user_response = supabase.auth.get_user(access_token)

            if user_response.user:
                user_id = user_response.user.id

                # Check if user has paid access
                user_result = supabase.table('users').select('is_paid').eq('id', user_id).single().execute()
                is_paid = user_result.data.get('is_paid', False) if user_result.data else False

                if is_paid:
                    is_locked = False
                elif is_locked:
                    # For free users, check if this is a first lesson of any level
                    lesson_result = supabase.table('lessons').select(
                        'id, stage, level, lesson_order, lesson_external_id, '
                        'title, title_th, subtitle, subtitle_th, focus, focus_th, backstory, backstory_th, '
                        'image_url, conversation_audio_url, header_img'
                    ).eq('id', lesson_id).single().execute()
                    lesson_row = lesson_result.data
                    if lesson_row:
                        lesson = lesson_row

                        # Get all lessons for this stage-level combination, ordered by lesson_order
                        level_lessons = supabase.table('lessons').select('id, lesson_order').eq('stage', lesson['stage']).eq('level', lesson['level']).order('lesson_order', desc=False).execute()

                        if level_lessons.data and len(level_lessons.data) > 0:
                            # Check if this is the first lesson (lowest lesson_order)
                            first_lesson = level_lessons.data[0]
                            first_lesson_id = first_lesson['id']
                            if lesson_id == first_lesson_id:
                                is_locked = False
        except Exception as e:
            print(f"Auth check error: {e}")
            # If auth fails, keep is_locked = True

    if is_locked:
        if not lesson_row:
            lesson_result = supabase.table('lessons').select(
                'id, stage, level, lesson_order, lesson_external_id, '
                'title, title_th, subtitle, subtitle_th, focus, focus_th, backstory, backstory_th, '
                'image_url, conversation_audio_url, header_img'
            ).eq('id', lesson_id).single().execute()
            lesson_row = lesson_result.data

        if not lesson_row:
            return jsonify({"error": "Lesson not found"}), 404

        def pick_lang(en_value, th_value):
            if lang == "th":
                return th_value or en_value
            return en_value or th_value

        raw_header_img = (lesson_row.get("header_img") or "").strip()
        header_image_path = None
        header_image_url = None
        if raw_header_img:
            lowered = raw_header_img.lower()
            if lowered.startswith("http://") or lowered.startswith("https://"):
                header_image_url = raw_header_img
            else:
                relative = raw_header_img.lstrip("/")
                if relative.lower().startswith("lesson-images/"):
                    relative = relative.split("/", 1)[1]
                relative = relative.split("?", 1)[0].split("#", 1)[0]
                if not relative.lower().startswith("headers/") and "/" not in relative:
                    relative = f"headers/{relative}"
                if not os.path.splitext(relative)[1]:
                    relative = f"{relative}.webp"
                header_image_path = relative
                base_url = (Config.SUPABASE_URL or "").rstrip("/")
                if base_url:
                    header_image_url = (
                        f"{base_url}/storage/v1/object/public/lesson-images/{relative}"
                    )

        safe_payload = {
            'locked': True,
            'id': lesson_row.get('id'),
            'title': pick_lang(lesson_row.get('title'), lesson_row.get('title_th')),
            'title_th': lesson_row.get('title_th'),
            'title_en': lesson_row.get('title'),
            'subtitle': pick_lang(lesson_row.get('subtitle'), lesson_row.get('subtitle_th')),
            'subtitle_th': lesson_row.get('subtitle_th'),
            'subtitle_en': lesson_row.get('subtitle'),
            'stage': lesson_row.get('stage'),
            'level': lesson_row.get('level'),
            'lesson_order': lesson_row.get('lesson_order'),
            'lesson_external_id': lesson_row.get('lesson_external_id'),
            'focus': pick_lang(lesson_row.get('focus'), lesson_row.get('focus_th')),
            'focus_th': lesson_row.get('focus_th'),
            'focus_en': lesson_row.get('focus'),
            'image_url': lesson_row.get('image_url'),
            'conversation_audio_url': lesson_row.get('conversation_audio_url'),
            'backstory': pick_lang(lesson_row.get('backstory'), lesson_row.get('backstory_th')),
            'backstory_th': lesson_row.get('backstory_th'),
            'backstory_en': lesson_row.get('backstory'),
            'header_img': raw_header_img or None,
            'header_image_path': header_image_path,
            'header_image_url': header_image_url,
            'sections': [],
            'questions': [],
            'transcript': [],
            'practice_exercises': [],
            'phrases': [],
        }
        resp = jsonify(safe_payload)
        resp.headers["Cache-Control"] = "public, max-age=60"
        resp.headers["Vary"] = "Accept-Encoding, lang"
        return resp, 200

    try:
        payload = resolve_lesson(lesson_id, lang)
    except KeyError:
        return jsonify({"error": "Lesson not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Add locked status to payload
    payload['locked'] = is_locked

    resp = jsonify(payload)
    resp.headers["Cache-Control"] = "public, max-age=60"
    resp.headers["Vary"] = "Accept-Encoding, lang"
    return resp, 200


@routes.route('/api/user/level-completion-status/<stage>/<int:level>', methods=['GET'])
@handle_options
def get_level_completion_status(stage, level):
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)

        if not user_response.user:
            return jsonify({"error": "Invalid token"}), 401

        user_id = user_response.user.id

        # Get all lessons for this stage and level
        lessons_result = supabase.table('lessons').select('id').eq('stage', stage).eq('level', level).execute()
        all_lessons = lessons_result.data if lessons_result.data else []

        if not all_lessons:
            return jsonify({"is_completed": False, "total_lessons": 0, "completed_lessons": 0}), 200

        lesson_ids = [lesson['id'] for lesson in all_lessons]

        # Get completed lessons for this user in this stage/level
        completed_result = supabase.table('user_lesson_progress').select('lesson_id').eq('user_id', user_id).eq('is_completed', True).in_('lesson_id', lesson_ids).execute()
        completed_lessons = completed_result.data if completed_result.data else []

        total_lessons = len(all_lessons)
        completed_count = len(completed_lessons)
        is_completed = completed_count == total_lessons and total_lessons > 0

        return jsonify({
            "is_completed": is_completed,
            "total_lessons": total_lessons,
            "completed_lessons": completed_count
        }), 200

    except Exception as e:
        print(f"Error checking level completion status: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route('/api/user/stats', methods=['GET'])
@handle_options
def get_user_stats():
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)

        if not user_response.user:
            return jsonify({"error": "Invalid token"}), 401

        user_id = user_response.user.id

        # Get total completed lessons count (simple query first)
        try:
            completed_lessons_result = supabase.table('user_lesson_progress').select('*', count='exact').eq('user_id', user_id).eq('is_completed', True).execute()
            lessons_completed = completed_lessons_result.count if completed_lessons_result.count else 0
        except Exception as e:
            print(f"Error counting completed lessons: {e}")
            lessons_completed = 0

        # Try to get levels completed (with error handling)
        levels_completed = 0
        try:
            # Get completed lessons with lesson details
            completed_with_lessons = supabase.table('user_lesson_progress').select('lesson_id, lessons!inner(stage, level)').eq('user_id', user_id).eq('is_completed', True).execute()

            if completed_with_lessons.data:
                # Group by stage and level
                level_groups = {}
                for progress in completed_with_lessons.data:
                    lesson = progress.get('lessons', {})
                    stage = lesson.get('stage')
                    level = lesson.get('level')

                    if stage and level is not None:
                        key = f"{stage}_{level}"
                        if key not in level_groups:
                            level_groups[key] = []
                        level_groups[key].append(progress['lesson_id'])

                # Count completed levels
                for level_key, completed_lesson_ids in level_groups.items():
                    stage, level = level_key.split('_')
                    level = int(level)

                    # Get total lessons for this level
                    total_lessons_result = supabase.table('lessons').select('id', count='exact').eq('stage', stage).eq('level', level).execute()
                    total_count = total_lessons_result.count if total_lessons_result.count else 0

                    if len(completed_lesson_ids) == total_count and total_count > 0:
                        levels_completed += 1

        except Exception as e:
            print(f"Error calculating levels completed: {e}")
            # Fallback to 0 if level calculation fails

        return jsonify({
            "lessons_completed": lessons_completed,
            "levels_completed": levels_completed
        }), 200

    except Exception as e:
        print(f"Error fetching user stats: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route('/api/user/comments', methods=['GET'])
@handle_options
def get_user_comments():
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)

        if not user_response.user:
            return jsonify({"error": "Invalid token"}), 401

        user_id = user_response.user.id

        # Fetch user's comments with lesson details
        comments_result = supabase.table('comments').select('*, lessons(id, title, level, lesson_order, stage)').eq('user_id', user_id).order('created_at', desc=True).execute()
        comments = comments_result.data if comments_result.data else []

        return jsonify({"comments": comments}), 200

    except Exception as e:
        print(f"Error fetching user comments: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route('/api/forgot-password/magic-link', methods=['POST'])
@handle_options
def send_magic_link():
    """Send a magic link for passwordless login"""
    data = request.json

    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Simple email validation
    import re
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, email):
        return jsonify({"error": "Please enter a valid email address"}), 400

    try:
        # Check if user exists
        existing_user = supabase.table('users').select('*').eq('email', email).execute()

        if not existing_user.data:
            return jsonify({"error": "No account found with this email address"}), 404

        # Send magic link using Supabase OTP
        response = supabase.auth.sign_in_with_otp({
            "email": email,
            "options": {
                "email_redirect_to": f"{Config.FRONTEND_URL}/pathway"
            }
        })

        if hasattr(response, "error") and response.error:
            print("Error sending magic link:", response.error)
            return jsonify({"error": "Failed to send magic link"}), 400

        return jsonify({
            "message": "Magic link sent! Check your email and click the link to sign in.",
            "email": email
        }), 200

    except Exception as e:
        print(f"Error in magic link: {e}")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500


@routes.route('/api/forgot-password/reset', methods=['POST'])
@handle_options
def reset_password():
    """Send password reset email"""
    data = request.json

    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Simple email validation
    import re
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, email):
        return jsonify({"error": "Please enter a valid email address"}), 400

    try:
        # Check if user exists
        existing_user = supabase.table('users').select('*').eq('email', email).execute()

        if not existing_user.data:
            return jsonify({"error": "No account found with this email address"}), 404

        # Send password reset email using Supabase
        response = supabase.auth.reset_password_email(email, {
            "redirect_to": f"{Config.FRONTEND_URL}/reset-password"
        })

        if hasattr(response, "error") and response.error:
            print("Error sending reset email:", response.error)
            return jsonify({"error": "Failed to send reset email"}), 400

        return jsonify({
            "message": "Password reset email sent! Check your email and follow the instructions to reset your password.",
            "email": email
        }), 200

    except Exception as e:
        print(f"Error in password reset: {e}")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500


@routes.route('/api/exercise-bank/sections', methods=['GET'])
@handle_options
def get_exercise_sections():
    """Return sections grouped by category for the exercise bank."""
    try:
        category_filter = (request.args.get("category") or "").strip().lower()
        featured_result = (
            supabase.table("featured_sections")
            .select("section")
            .execute()
        )
        featured_sections = {
            (row.get("section") or "").strip()
            for row in (featured_result.data or [])
            if row.get("section")
        }

        result = (
            supabase.table("exercise_bank")
            .select("id, category, section, section_th")
            .execute()
        )

        rows = result.data or []
        sections_map = {}

        for row in rows:
            category = row.get("category") or ""
            section = row.get("section") or ""
            key = (category, section)
            is_featured = section in featured_sections

            if key not in sections_map:
                section_th = row.get("section_th") or None
                sections_map[key] = {
                    "category": category,
                    "category_label": _category_label(category),
                    "category_slug": _category_slug(category),
                    "section": section,
                    "section_th": section_th,
                    "section_slug": _section_slug(section),
                    "exercise_count": 0,
                    "featured_count": 1 if is_featured else 0,
                    "is_featured": is_featured,
                }

            sections_map[key]["exercise_count"] += 1

        sections = list(sections_map.values())
        if category_filter:
            sections = [
                section
                for section in sections
                if section["category_slug"] == category_filter
                or section["category"].lower() == category_filter
            ]

        sections.sort(key=lambda item: (item["category_label"], item["section"]))

        # Build the category list with aggregated data
        categories = defaultdict(
            lambda: {"label": "", "slug": "", "section_count": 0, "exercise_count": 0}
        )
        for section in sections_map.values():
            key = section["category"]
            cat_entry = categories[key]
            cat_entry["label"] = _category_label(key)
            cat_entry["slug"] = _category_slug(key)
            cat_entry["section_count"] += 1
            cat_entry["exercise_count"] += section["exercise_count"]

        category_list = [
            {
                "category": key,
                "category_label": value["label"],
                "category_slug": value["slug"],
                "section_count": value["section_count"],
                "exercise_count": value["exercise_count"],
            }
            for key, value in categories.items()
        ]
        category_list.sort(key=lambda item: item["category_label"])

        return jsonify({"sections": sections, "categories": category_list}), 200

    except Exception as exc:
        print(f"Error fetching exercise sections: {exc}")
        return jsonify({"error": "Failed to fetch exercise sections"}), 500


@routes.route('/api/exercise-bank/featured', methods=['GET'])
@handle_options
def get_featured_exercises():
    """Return featured exercises across the exercise bank."""
    try:
        featured_result = (
            supabase.table("featured_sections")
            .select("section")
            .execute()
        )
        featured_sections = [
            (row.get("section") or "").strip()
            for row in (featured_result.data or [])
            if row.get("section")
        ]
        if not featured_sections:
            return jsonify({"featured": []}), 200

        result = (
            supabase.table("exercise_bank")
            .select("category, section, section_th")
            .in_("section", featured_sections)
            .execute()
        )

        rows = result.data or []
        sections_map = {}
        for row in rows:
            category = row.get("category") or ""
            section = row.get("section") or ""
            key = (category, section)
            if key not in sections_map:
                sections_map[key] = {
                    "category": category,
                    "category_label": _category_label(category),
                    "category_slug": _category_slug(category),
                    "section": section,
                    "section_th": row.get("section_th") or None,
                    "section_slug": _section_slug(section),
                    "exercise_count": 0,
                }
            sections_map[key]["exercise_count"] += 1

        featured = list(sections_map.values())
        featured.sort(key=lambda item: (item["category_label"], item["section"]))

        return jsonify({"featured": featured}), 200

    except Exception as exc:
        print(f"Error fetching featured exercises: {exc}")
        return jsonify({"error": "Failed to fetch featured exercises"}), 500


@routes.route('/api/exercise-bank/section/<category_slug>/<section_slug>', methods=['GET'])
@handle_options
def get_exercise_section(category_slug, section_slug):
    """Return all exercises for a specific section."""
    try:
        result = (
            supabase.table("exercise_bank")
            .select(
                "id, category, section, section_th, title, title_th, prompt, prompt_th, "
                "exercise_type, items, items_th, is_featured"
            )
            .execute()
        )

        rows = result.data or []
        filtered = [
            row
            for row in rows
            if _category_slug(row.get("category")) == category_slug
            and _section_slug(row.get("section")) == section_slug
        ]

        if not filtered:
            return jsonify({"error": "Section not found"}), 404

        filtered.sort(key=lambda row: (row.get("sort_order") or 0, row.get("title") or ""))
        sample = filtered[0]

        exercises = [
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "title_th": row.get("title_th"),
                "prompt": row.get("prompt"),
                "prompt_th": row.get("prompt_th"),
                "exercise_type": row.get("exercise_type"),
                "items": row.get("items") or [],
                "items_th": row.get("items_th") or [],
                "sort_order": row.get("sort_order"),
                "is_featured": bool(row.get("is_featured")),
            }
            for row in filtered
        ]

        response = {
            "category": sample.get("category"),
            "category_label": _category_label(sample.get("category")),
            "category_slug": _category_slug(sample.get("category")),
            "section": sample.get("section"),
            "section_th": sample.get("section_th"),
            "section_slug": _section_slug(sample.get("section")),
            "exercises": exercises,
        }

        return jsonify({"section": response}), 200

    except Exception as exc:
        print(f"Error fetching exercise section: {exc}")
        return jsonify({"error": "Failed to fetch exercise section"}), 500


@routes.route('/api/topic-library', methods=['GET'])
@handle_options
def get_topic_library():
    """Get all topics from topic library"""
    try:
        lang = (request.args.get("lang") or "en").lower()
        if lang not in ("en", "th"):
            lang = "en"

        # Fetch all topics ordered by idx
        result = supabase.table('topic_library').select('*').order('idx', desc=False).execute()

        if not result.data:
            return jsonify({"topics": []}), 200

        topics = []
        for topic in result.data:
            # Choose the appropriate content based on language
            if lang == "th" and topic.get('content_jsonb_th'):
                content_jsonb = topic['content_jsonb_th']
                name = topic.get('name_th') or topic['name']
                subtitle = topic.get('subtitle_th') or topic.get('subtitle')
            else:
                content_jsonb = topic['content_jsonb']
                name = topic['name']
                subtitle = topic.get('subtitle')

            topics.append({
                "id": topic['id'],
                "name": name,
                "subtitle": subtitle,
                "slug": topic['slug'],
                "tags": topic.get('tags', []),
                "is_featured": bool(topic.get('is_featured')),
                "content_jsonb": content_jsonb,
                "created_at": topic.get('created_at'),
                "updated_at": topic.get('updated_at')
            })

        return jsonify({"topics": topics}), 200

    except Exception as e:
        print(f"Error fetching topic library: {e}")
        return jsonify({"error": "Failed to fetch topic library"}), 500


@routes.route('/api/topic-library/<slug>', methods=['GET'])
@handle_options
def get_topic_by_slug(slug):
    """Get a specific topic by slug"""
    try:
        lang = (request.args.get("lang") or "en").lower()
        if lang not in ("en", "th"):
            lang = "en"

        # Fetch topic by slug
        result = supabase.table('topic_library').select('*').eq('slug', slug).execute()

        if not result.data:
            return jsonify({"error": "Topic not found"}), 404

        topic = result.data[0]

        # Choose the appropriate content based on language
        if lang == "th" and topic.get('content_jsonb_th'):
            content_jsonb = topic['content_jsonb_th']
            name = topic.get('name_th') or topic['name']
            subtitle = topic.get('subtitle_th') or topic.get('subtitle')
        else:
            content_jsonb = topic['content_jsonb']
            name = topic['name']
            subtitle = topic.get('subtitle')

        response_topic = {
            "id": topic['id'],
            "name": name,
            "subtitle": subtitle,
            "slug": topic['slug'],
            "tags": topic.get('tags', []),
            "is_featured": bool(topic.get('is_featured')),
            "content_jsonb": content_jsonb,
            "created_at": topic.get('created_at'),
            "updated_at": topic.get('updated_at')
        }

        return jsonify({"topic": response_topic}), 200

    except Exception as e:
        print(f"Error fetching topic {slug}: {e}")
        return jsonify({"error": "Failed to fetch topic"}), 500
