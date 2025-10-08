# Auth Token Fix for Free User Lesson Access

## ✅ Issue Fixed

**Problem:** Free users (logged in but `is_paid = false`) were seeing the first lesson of each level as unlocked in LessonsIndex, but when they clicked it, the lesson content was still locked.

**Root Cause:** The `fetchResolvedLesson` function was NOT sending the Authorization header with the user's access token. So the backend couldn't identify the user and treated ALL requests as guest users (fully locked).

## 🔧 Solution

Updated `fetchResolvedLesson.js` to:
1. Get the current user session from Supabase
2. Extract the access token
3. Include it in the Authorization header when fetching lessons

## 📝 Code Changes

### Frontend: `fetchResolvedLesson.js`

**Before:**
```javascript
export async function fetchResolvedLesson(lessonId, lang = "en") {
  const res = await fetch(`/api/lessons/${lessonId}/resolved?lang=${lang}`);
  if (!res.ok) throw new Error(`Failed to fetch lesson (${res.status})`);
  return await res.json();
}
```

**After:**
```javascript
import supabaseClient from "../supabaseClient";

export async function fetchResolvedLesson(lessonId, lang = "en") {
  // Get the current session to include auth token
  const { data: { session } } = await supabaseClient.auth.getSession();

  const headers = {
    'Content-Type': 'application/json',
  };

  // Add Authorization header if user is logged in
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }

  const res = await fetch(`/api/lessons/${lessonId}/resolved?lang=${lang}`, {
    headers,
  });

  if (!res.ok) throw new Error(`Failed to fetch lesson (${res.status})`);
  return await res.json();
}
```

### Backend: `routes.py` (Debug Logging Added)

Added detailed console logging to verify the first lesson detection logic:
- Logs current lesson details (stage, level, lesson_order)
- Logs first lesson of the level
- Logs whether it's a match (unlock) or not (keep locked)

This will help debug any issues in the backend logic.

## 🎯 How It Works Now

### Data Flow:
```
1. User clicks lesson in LessonsIndex
   ↓
2. fetchResolvedLesson() called
   ↓
3. Gets user session from Supabase
   ↓
4. Includes "Authorization: Bearer {token}" header
   ↓
5. Backend receives request with auth token
   ↓
6. Backend validates user via supabase.auth.get_user(token)
   ↓
7. Backend checks users.is_paid
   ↓
8. If is_paid = false:
   - Query lessons for same stage/level
   - Order by lesson_order ASC
   - Compare current lesson_id with first lesson's id
   - If match → unlock (locked: false)
   - If no match → lock (locked: true)
   ↓
9. Frontend receives response with correct locked status
   ↓
10. LessonContent shows full content or locked overlay
```

## 🧪 Test Scenarios

### Scenario 1: Guest User (No Account)
- ❌ No Authorization header sent
- ✅ Backend treats as guest
- ✅ All lessons return `locked: true`
- ✅ Shows locked overlay

### Scenario 2: Free User (Account, is_paid = false)
- ✅ Authorization header with valid token
- ✅ Backend identifies user
- ✅ Checks is_paid = false
- ✅ First lesson of each level: `locked: false` ← **NOW WORKS**
- ✅ Other lessons: `locked: true`
- ✅ First lessons show full content
- ✅ Other lessons show locked overlay

### Scenario 3: Paid User (Account, is_paid = true)
- ✅ Authorization header with valid token
- ✅ Backend identifies user
- ✅ Checks is_paid = true
- ✅ All lessons: `locked: false`
- ✅ All lessons show full content

## 📊 Debug Output (Backend Console)

When a free user accesses a lesson, you'll now see:
```
Checking lesson abc-123: stage=Beginner, level=1, lesson_order=1
First lesson of Beginner Level 1: id=abc-123, lesson_order=1
Current lesson_id: abc-123, First lesson_id: abc-123, Match: True
✓ Unlocking lesson abc-123 (first lesson of level)
```

Or for a locked lesson:
```
Checking lesson xyz-456: stage=Beginner, level=1, lesson_order=5
First lesson of Beginner Level 1: id=abc-123, lesson_order=1
Current lesson_id: xyz-456, First lesson_id: abc-123, Match: False
✗ Keeping lesson xyz-456 locked (not first lesson)
```

## ✅ Files Modified

1. `/frontend/src/lib/fetchResolvedLesson.js`
   - Added Supabase import
   - Added session fetching
   - Added Authorization header conditionally

2. `/backend/app/routes.py`
   - Added debug logging for first lesson detection
   - Added explicit `desc=False` to order() for clarity

## 🎉 Result

Free users can now:
- ✅ See first lesson of each level unlocked in LessonsIndex (UI matches reality)
- ✅ Click and view full content for first lessons
- ✅ See locked overlay for all other lessons
- ✅ Experience proper tier-based access control

The frontend lock icons and backend access control are now perfectly synchronized!
