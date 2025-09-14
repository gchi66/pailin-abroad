#!/usr/bin/env python3

# Test the new logic
problematic_text = "แฟรงค์บอกกับสาวๆว่าให้กลับมาตอน 12:00 จากเวลาที่แฟรงค์พูด เขาหมายถึง 12AM หรือ 12PM กันล่ะ?"
legitimate_header = "USES OF 'IS' การใช้คำว่า 'is'"

print("Testing problematic text:")
print(f"Text: {repr(problematic_text)}")
print(f"First character: {repr(problematic_text[0])}")
print(f"Is uppercase: {problematic_text[0].isupper()}")
print(f"Is alpha: {problematic_text[0].isalpha()}")
print(f"Would pass first check: {problematic_text[0].isupper() and problematic_text[0].isalpha()}")

print("\nTesting legitimate header:")
print(f"Text: {repr(legitimate_header)}")
print(f"First character: {repr(legitimate_header[0])}")
print(f"Is uppercase: {legitimate_header[0].isupper()}")
print(f"Is alpha: {legitimate_header[0].isalpha()}")
print(f"Would pass first check: {legitimate_header[0].isupper() and legitimate_header[0].isalpha()}")