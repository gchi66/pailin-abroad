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


@routes.route('/api/user/profile', methods=['PUT'])
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



@routes.route('/api/signup-email', methods=['POST'])
def signup_email():
    """Send magic link for account creation - no real account until onboarding complete"""
    print("Email signup endpoint hit!")
    data = request.json
    print("Received data:", data)

    email = data.get('email')

    if not email:
        print("Missing email")
        return jsonify({"error": "Email is required"}), 400

    try:
        # Check if user already has a completed account
        existing_user = supabase.table('users').select('*').eq('email', email).neq('password_hash', 'pending_onboarding').execute()

        if existing_user.data:
            return jsonify({"error": "An account with this email already exists. Please use the login form."}), 400

        # Use sign_up with a temporary password that meets requirements
        # This creates the auth user but they'll set real password in onboarding
        response = supabase.auth.sign_up({
            "email": email,
            "password": "TempPass123!",  # Meets Supabase requirements, will be changed in onboarding
            "options": {
                "email_redirect_to": "http://localhost:3000/onboarding"
            }
        })

        if hasattr(response, "error") and response.error:
            print("Error from Supabase:", response.error)
            return jsonify({"error": str(response.error)}), 400
        print("Supabase response:", response)
        print(f"Confirmation email sent to {email}")

        return jsonify({
            "message": "Confirmation email sent! Please check your email to verify your account.",
            "email": email,
            "email_sent": True
        }), 200

    except Exception as e:
        print(f"Error in email signup: {e}")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500



@routes.route('/api/confirm-email', methods=['POST'])
def confirm_email():
    """Handle email confirmation and create user record in database"""
    print("Email confirmation endpoint hit!")
    data = request.json
    print("Received data:", data)

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

            if user_insert_result.data:
                print(f"User record created successfully for {user_email} and marked verified")
            else:
                print(f"Warning: User record creation may have failed for {user_email}")
        else:
            # Ensure existing user is marked verified
            try:
                supabase.table('users').update({
                    'is_verified': True
                }).eq('id', user_id).execute()
                print(f"User record already exists for {user_email}, updated is_verified")
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
def set_password():
    """Set password for user during onboarding (after email confirmation)"""
    print("Set password endpoint hit!")
    data = request.json
    print("Received data:", data)

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
            print(f"Password set and fresh session created for user {user_email}")

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
def complete_signup():
    """Complete the signup process - this creates the real account after onboarding"""
    print("Complete signup endpoint hit!")
    data = request.json
    print("Received data:", data)

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

        # Update user record in users table to mark as complete
        update_result = supabase.table('users').update({
            'username': username,
            'avatar_image': avatar_image,
            'password_hash': 'set_during_onboarding',
            'is_active': True  # Now the account is active
        }).eq('id', user_id).execute()

        if not update_result.data:
            print(f"Warning: User record update may have failed for {email}")

        print(f"Account setup completed for user {email}")

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

    # Check if user is authenticated and has paid access
    is_locked = True
    user_id = None

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
                else:
                    # For free users, check if this is a first lesson of any level
                    lesson_result = supabase.table('lessons').select('stage, level, lesson_order').eq('id', lesson_id).single().execute()
                    if lesson_result.data:
                        lesson = lesson_result.data
                        print(f"Checking lesson {lesson_id}: stage={lesson['stage']}, level={lesson['level']}, lesson_order={lesson['lesson_order']}")

                        # Get all lessons for this stage-level combination, ordered by lesson_order
                        level_lessons = supabase.table('lessons').select('id, lesson_order').eq('stage', lesson['stage']).eq('level', lesson['level']).order('lesson_order', desc=False).execute()

                        if level_lessons.data and len(level_lessons.data) > 0:
                            # Check if this is the first lesson (lowest lesson_order)
                            first_lesson = level_lessons.data[0]
                            first_lesson_id = first_lesson['id']
                            print(f"First lesson of {lesson['stage']} Level {lesson['level']}: id={first_lesson_id}, lesson_order={first_lesson['lesson_order']}")
                            print(f"Current lesson_id: {lesson_id}, First lesson_id: {first_lesson_id}, Match: {lesson_id == first_lesson_id}")

                            if lesson_id == first_lesson_id:
                                is_locked = False
                                print(f"✓ Unlocking lesson {lesson_id} (first lesson of level)")
                            else:
                                print(f"✗ Keeping lesson {lesson_id} locked (not first lesson)")
        except Exception as e:
            print(f"Auth check error: {e}")
            # If auth fails, keep is_locked = True

    try:
        payload = resolve_lesson(lesson_id, lang)
    except KeyError:
        return jsonify({"error": "Lesson not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Add locked status to payload
    payload['locked'] = is_locked

    # If locked, remove sensitive content but keep metadata
    if is_locked:
        # Keep basic metadata and structure info but remove detailed content
        safe_payload = {
            'locked': True,
            'id': payload.get('id'),
            'title': payload.get('title'),
            'title_th': payload.get('title_th'),
            'title_en': payload.get('title_en'),
            'subtitle': payload.get('subtitle'),
            'subtitle_th': payload.get('subtitle_th'),
            'subtitle_en': payload.get('subtitle_en'),
            'stage': payload.get('stage'),
            'level': payload.get('level'),
            'lesson_order': payload.get('lesson_order'),
            'lesson_external_id': payload.get('lesson_external_id'),
            'focus': payload.get('focus'),
            'focus_th': payload.get('focus_th'),
            'image_url': payload.get('image_url'),
            'conversation_audio_url': payload.get('conversation_audio_url'),
            'backstory': payload.get('backstory'),
            'backstory_th': payload.get('backstory_th'),
            # Keep empty arrays so UI can show sidebar structure
            'sections': payload.get('sections', []),
            'questions': [],
            'transcript': [],
            'practice_exercises': [],
            'phrases': [],
        }
        payload = safe_payload

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
def send_magic_link():
    """Send a magic link for passwordless login"""
    print("Magic link endpoint hit!")
    data = request.json
    print("Received data:", data)

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

        print(f"Magic link sent to {email}")
        return jsonify({
            "message": "Magic link sent! Check your email and click the link to sign in.",
            "email": email
        }), 200

    except Exception as e:
        print(f"Error in magic link: {e}")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500


@routes.route('/api/forgot-password/reset', methods=['POST'])
def reset_password():
    """Send password reset email"""
    print("Password reset endpoint hit!")
    data = request.json
    print("Received data:", data)

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

        print(f"Password reset email sent to {email}")
        return jsonify({
            "message": "Password reset email sent! Check your email and follow the instructions to reset your password.",
            "email": email
        }), 200

    except Exception as e:
        print(f"Error in password reset: {e}")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500


@routes.route('/api/topic-library', methods=['GET'])
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
                "content_jsonb": content_jsonb,
                "created_at": topic.get('created_at'),
                "updated_at": topic.get('updated_at')
            })

        return jsonify({"topics": topics}), 200

    except Exception as e:
        print(f"Error fetching topic library: {e}")
        return jsonify({"error": "Failed to fetch topic library"}), 500


@routes.route('/api/topic-library/<slug>', methods=['GET'])
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
            "content_jsonb": content_jsonb,
            "created_at": topic.get('created_at'),
            "updated_at": topic.get('updated_at')
        }

        return jsonify({"topic": response_topic}), 200

    except Exception as e:
        print(f"Error fetching topic {slug}: {e}")
        return jsonify({"error": "Failed to fetch topic"}), 500
