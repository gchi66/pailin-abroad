#!/usr/bin/env python3
"""
Debug script to test the user stats endpoint logic.
"""

import sys
import os
sys.path.append('/home/gchichester/code/pailin-abroad/backend')

from app.supabase_client import supabase

def test_stats_queries():
    print("Testing Supabase queries for user stats...")

    # Test user ID (you can replace this with a real user ID from your database)
    test_user_id = "test_user_id"  # Replace with actual user ID if you have one

    try:
        print("\n1. Testing basic completed lessons count...")
        # This is the query that might be failing
        completed_lessons_result = supabase.table('user_lesson_progress').select('lesson_id', count='exact').eq('user_id', test_user_id).eq('is_completed', True).execute()
        print(f"Result: {completed_lessons_result}")

    except Exception as e:
        print(f"Error in basic count query: {e}")

    try:
        print("\n2. Testing lessons with stage/level join...")
        # This is the more complex query
        completed_with_lessons = supabase.table('user_lesson_progress').select('*, lessons(stage, level)').eq('user_id', test_user_id).eq('is_completed', True).execute()
        print(f"Result: {completed_with_lessons}")

    except Exception as e:
        print(f"Error in join query: {e}")

    try:
        print("\n3. Testing lessons table count...")
        total_lessons_result = supabase.table('lessons').select('id', count='exact').eq('stage', 'Beginner').eq('level', 1).execute()
        print(f"Result: {total_lessons_result}")

    except Exception as e:
        print(f"Error in lessons count query: {e}")

if __name__ == "__main__":
    test_stats_queries()
