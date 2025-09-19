#!/usr/bin/env python3
"""
Test script to verify title extraction behavior for Thai documents.
"""

import sys
import os
sys.path.append('/home/gchichester/code/pailin-abroad/backend')

from app.tools.parser import GoogleDocsParser

def test_title_extraction():
    parser = GoogleDocsParser()
    
    # Test case: LESSON 1.5: Good morning, Joey!\nบทเรียนที่ 1.5: สวัสดีตอนเช้า โจอี้!
    test_header = "LESSON 1.5: Good morning, Joey!\nบทเรียนที่ 1.5: สวัสดีตอนเช้า โจอี้!"
    
    print("Testing title extraction...")
    print(f"Input header: {repr(test_header)}")
    print()
    
    # Test English mode
    print("=== English mode (lang='en') ===")
    try:
        lesson_info_en, title_en = parser.parse_lesson_header(test_header, "Beginner", lang='en')
        print(f"Extracted title: {repr(title_en)}")
        print(f"Full lesson info: {lesson_info_en}")
    except Exception as e:
        print(f"Error in English mode: {e}")
    print()
    
    # Test Thai mode
    print("=== Thai mode (lang='th') ===")
    try:
        lesson_info_th, title_th = parser.parse_lesson_header(test_header, "Beginner", lang='th')
        print(f"Extracted title: {repr(title_th)}")
        print(f"Full lesson info: {lesson_info_th}")
    except Exception as e:
        print(f"Error in Thai mode: {e}")
    print()
    
    # Test another format - single line with both languages
    test_header2 = "LESSON 1.5: Good morning, Joey! บทเรียนที่ 1.5: สวัสดีตอนเช้า โจอี้!"
    print("=== Testing single-line format ===")
    print(f"Input header: {repr(test_header2)}")
    print()
    
    print("English mode:")
    try:
        lesson_info_en2, title_en2 = parser.parse_lesson_header(test_header2, "Beginner", lang='en')
        print(f"Extracted title: {repr(title_en2)}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\nThai mode:")
    try:
        lesson_info_th2, title_th2 = parser.parse_lesson_header(test_header2, "Beginner", lang='th')
        print(f"Extracted title: {repr(title_th2)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_title_extraction()