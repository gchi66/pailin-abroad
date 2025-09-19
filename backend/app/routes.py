from flask import Blueprint, request, jsonify
from app.supabase_client import supabase
from app.resolver import resolve_lesson
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from app.config import Config

routes = Blueprint("routes", __name__)

@routes.route("/", methods=["GET"])
def home():
    return jsonify({}), 204

@routes.route('/api/login', methods=['GET', 'POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if hasattr(response, "error") and response.error:
            return jsonify({"error": str(response.error)}), 400

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
        return jsonify({"error": "Internal server error"}), 500


@routes.route('/api/user/profile', methods=['GET'])
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
            "is_admin": user_data.get("is_admin", False),
            "created_at": user_data.get("created_at"),
            "lessons_complete": lessons_complete
        }

        return jsonify({"profile": profile}), 200

    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route('/api/user/completed-lessons', methods=['GET'])
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
                # No completed lessons, find the very first lesson
                first_lesson_result = supabase.table('lessons').select('*').order('stage, level, lesson_order').limit(1).execute()
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
                    stage_order = ['Beginner', 'Lower Intermediate', 'Upper Intermediate', 'Advanced']
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
                        stage_order = ['Beginner', 'Lower Intermediate', 'Upper Intermediate', 'Advanced']
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


@routes.route('/api/signup', methods=['GET', 'POST'])
def signup():
    print("Endpoint hit!")
    data = request.json
    print("Received data:", data)  # Debug incoming data

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        print("Missing email or password")  # Debug missing fields
        return jsonify({"error": "Email and password are required"}), 400

    response = supabase.auth.sign_up({
        "email": email,
        "password": password
    })
    print("Supabase response:", response)  # Debug Supabase response

    # Check for errors in the response
    if hasattr(response, "error") and response.error:
        print("Error from Supabase:", response.error)  # Debug Supabase error
        return jsonify({"error": str(response.error)}), 400

    if not response.user:
        print("Sign-up failed: No user object returned")
        return jsonify({"error": "Sign-up failed. Please try again."}), 400

    return jsonify({"message": "Sign-up successful! Please verify your email."}), 200

@routes.route('/api/delete_account', methods=['DELETE'])
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

        # Delete the user using the service role client
        supabase.auth.admin.delete_user(user_id)

        # # Check if the delete action was successful
        # if delete_response is None or delete_response.error:
        #     return jsonify({"error": "Failed to delete the user."}), 400

        print("User deleted successfully:", user_id)
        # Return a success message immediately
        return jsonify({"message": "Account deleted successfully."}), 200


    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route("/contact", methods=["POST"])
def contact():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    message = data.get("message")

    if not (name and email and message):
        return jsonify({"message": "Missing required fields"}), 400

    # Build the message
    msg = MIMEMultipart()
    msg["From"] = Config.EMAIL_ADDRESS
    msg["To"] = Config.RECIPIENT_EMAIL
    msg["Subject"] = "New Contact Form Submission"

    body = f"""
    You have a new message from your contact form:

    Name: {name}
    Email: {email}

    Message:
    {message}
    """
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(Config.EMAIL_ADDRESS, Config.EMAIL_PASSWORD)
            server.send_message(msg)
        return jsonify({"message": "Email sent successfully!"}), 200
    except Exception as e:
        print("Error sending email:", e)
        return jsonify({"message": "Failed to send email."}), 500


@routes.route("/api/lessons/<lesson_id>/resolved", methods=["GET"])
def get_lesson_resolved(lesson_id):
    lang = (request.args.get("lang") or "en").lower()
    if lang not in ("en", "th"):
        return jsonify({"error": "lang must be 'en' or 'th'"}), 400
    try:
        payload = resolve_lesson(lesson_id, lang)
    except KeyError:
        return jsonify({"error": "Lesson not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    resp = jsonify(payload)
    resp.headers["Cache-Control"] = "public, max-age=60"
    resp.headers["Vary"] = "Accept-Encoding, lang"
    return resp, 200


@routes.route('/api/user/level-completion-status/<stage>/<int:level>', methods=['GET'])
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

        # Get total completed lessons count
        completed_lessons_result = supabase.table('user_lesson_progress').select('*', count='exact').eq('user_id', user_id).eq('is_completed', True).execute()
        lessons_completed = completed_lessons_result.count if completed_lessons_result.count else 0

        # Calculate completed levels
        # First, get all completed lessons with their stage/level info
        completed_with_lessons = supabase.table('user_lesson_progress').select('*, lessons(stage, level)').eq('user_id', user_id).eq('is_completed', True).execute()
        completed_data = completed_with_lessons.data if completed_with_lessons.data else []

        # Group completed lessons by stage and level
        completed_by_level = {}
        for progress in completed_data:
            lesson = progress.get('lessons', {})
            stage = lesson.get('stage')
            level = lesson.get('level')

            if stage and level is not None:
                key = f"{stage}_{level}"
                if key not in completed_by_level:
                    completed_by_level[key] = []
                completed_by_level[key].append(progress['lesson_id'])

        # Now check each stage/level combination to see if it's fully completed
        levels_completed = 0
        for level_key, completed_lesson_ids in completed_by_level.items():
            stage, level = level_key.split('_')
            level = int(level)

            # Get total lessons for this stage/level
            total_lessons_result = supabase.table('lessons').select('*', count='exact').eq('stage', stage).eq('level', level).execute()
            total_lessons_count = total_lessons_result.count if total_lessons_result.count else 0

            # If user completed all lessons in this level, count it as completed
            if len(completed_lesson_ids) == total_lessons_count and total_lessons_count > 0:
                levels_completed += 1

        return jsonify({
            "lessons_completed": lessons_completed,
            "levels_completed": levels_completed
        }), 200

    except Exception as e:
        print(f"Error fetching user stats: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route('/api/user/comments', methods=['GET'])
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
