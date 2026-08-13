# Placement Test Architecture

## Goal

The dedicated placement entry screen appears when a user:

1. Continues into the app as a guest.
2. Completes account onboarding.

It plays up to three audio conversations, asks multiple-choice comprehension questions, and assigns the user to Level 1, 2, 5, 9, or 13. The placement result should affect My Pathway even when the user closes the completed-test popup instead of pressing the button that navigates directly to the assigned lesson.

## Minimal architecture

Use Supabase Storage for the audio and Postgres for structured test content and registered-user placement state. Do not store individual answers, per-conversation scores, or attempt history for the initial implementation.

### Implementation status

- [x] Created the public `placement-test-audio` Storage bucket.
- [x] Uploaded all three placement-test audio files.
- [x] Created the `placement_conversations` table.
- [x] Added `placement_level` and `placement_completed_at` to `public.users`.
- [x] Added placement-level and placement-state constraints to `public.users`.
- [x] Enabled row-level security on `placement_conversations`.
- [x] Added read-only access for anonymous and authenticated clients.
- [x] Added and validated the version-controlled JSON source containing all 10 questions.
- [x] Added a repeatable validation and seed tool.
- [x] Seeded the three conversation rows into Supabase.
- [x] Added an admin-only Profile preview entry point in the mobile app.
- [x] Added direct client retrieval and local scoring for the placement-test preview.
- [x] Added a dedicated Thai placement entry screen used after onboarding, on guest entry, and by the admin Profile trigger.
- [x] Completed the manual choose-level path and result screen. Each choice opens lesson 1 of Level 1, 2, 5, 6, or 9; the result copy currently uses the same provisional Thai lesson primer for every level.
- [x] Completed the placement-test listening card for each conversation, including real Supabase audio, playback progress, and transition into the persistent lesson-style audio tray. The placement tray intentionally hides playback speed while lesson trays retain it.
- [ ] Replace the provisional Thai copy in the manual choose-level path with the translator-approved translations when they are delivered.
- [ ] Add guest placement persistence and guest-to-account transfer.
- [ ] Integrate the saved result with My Pathway and popup triggering.

### Audio storage

The audio files are stored in the public Supabase Storage bucket `placement-test-audio`:

```text
placement-test-audio/
  placement_test_1.mp3
  placement_test_2.mp3
  placement_test_3.mp3
```

Store the object path, such as `placement_test_1.mp3`, in the database rather than storing a complete public URL. The app can generate the public URL through the Supabase Storage client. Because guests must be able to play the test audio and the files contain no private user data, the bucket is public. Public access applies to file delivery only; no client upload, update, or delete policies are required.

### Placement conversation content

The `placement_conversations` table has been created with one row per audio conversation. Questions, choices, correct answers, and scoring rules use JSONB because the test is small and fixed.

```sql
create table public.placement_conversations (
  id uuid primary key default gen_random_uuid(),
  conversation_order integer not null unique,
  audio_path text not null,
  questions jsonb not null,
  scoring_rules jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

The version-controlled source of truth is `backend/data/placement-test.json`. It contains all three audio paths, 10 questions, four choices per question, zero-based correct-answer indexes, and the complete scoring rules.

Validate it without writing to Supabase:

```bash
cd backend
./venv/bin/python -m app.tools.seed_placement_test --validate-only
```

After validation, seed or update the three rows:

```bash
cd backend
./venv/bin/python -m app.tools.seed_placement_test
```

The seeder upserts on `conversation_order`, so rerunning it updates the existing three rows instead of creating duplicates. It uses the backend's admin Supabase client because normal clients have read-only access and cannot modify placement content.

### Client read policy

The placement test is low-stakes guidance, users can freely navigate between levels, and its result does not control payments or content access. The app therefore reads the questions, answer indexes, and scoring rules directly and scores the test locally. The following read-only policy has been applied:

```sql
create policy "Placement conversations are publicly readable"
on public.placement_conversations
for select
to anon, authenticated
using (true);
```

There are no client insert, update, or delete policies on this table.

There is no need to store the written transcripts unless subtitles, accessibility, translations, or transcript display are added later.

An example `questions` value:

```json
[
  {
    "prompt": "What is the woman's job?",
    "choices": [
      "She's a nurse.",
      "She's a doctor.",
      "She's a student.",
      "She's a hospital manager."
    ],
    "correctChoice": 0
  }
]
```

An example `scoring_rules` value for conversation 1:

```json
[
  { "minCorrect": 0, "maxCorrect": 1, "level": 1 },
  { "minCorrect": 2, "maxCorrect": 2, "level": 2 },
  { "minCorrect": 3, "maxCorrect": 3, "nextConversation": 2 }
]
```

The complete routing rules are:

| Conversation | Correct answers | Result |
| --- | ---: | --- |
| 1 | 0-1 | Level 1 |
| 1 | 2 | Level 2 |
| 1 | 3 | Continue to conversation 2 |
| 2 | 0-1 | Level 2 |
| 2 | 2-3 | Level 5 |
| 2 | 4 | Continue to conversation 3 |
| 3 | 0-2 | Level 9 |
| 3 | 3 | Level 13 |

## Persisted user result

The final level and completion time columns have been added to `public.users`:

```sql
alter table public.users
  add column placement_level integer,
  add column placement_completed_at timestamptz;

alter table public.users
  add constraint users_placement_level_check
  check (
    placement_level is null
    or placement_level in (1, 2, 5, 9, 13)
  );

alter table public.users
  add constraint users_placement_state_check
  check (
    (placement_level is null and placement_completed_at is null)
    or
    (placement_level is not null and placement_completed_at is not null)
  );
```

The applied migration also enforces that `placement_level` and `placement_completed_at` are either both null or both populated. Valid placement levels are limited to 1, 2, 5, 9, and 13.

A separate `placement_completed` Boolean is unnecessary:

- `placement_completed_at is null`: placement is not completed.
- `placement_completed_at is not null`: placement is completed.

The application should write `placement_level` and `placement_completed_at` together when the final result is calculated. It should not store individual selected answers or intermediate scores.

## Guest behavior

Guests do not have a `users` row, so save equivalent state locally using the app's persistent guest storage:

```json
{
  "placementLevel": 5,
  "placementCompletedAt": "2026-08-12T12:00:00.000Z"
}
```

When the guest creates an account:

1. Copy the locally stored level and completion time into the new `users` row.
2. Confirm that the account update succeeded.
3. Clear the local guest placement state.

This prevents a converted guest from being asked to take the placement test twice.

## Entry-screen behavior

### Placement entry presentation

Placement begins on a dedicated screen rather than over My Pathway. The screen uses the normal app background and a My Pathway-style welcome header, but it never says "Welcome back." Authenticated users see a welcome with their first name and their selected avatar. Guests see Pailin's avatar and a welcome without a name. Both see the same supporting subheader.

The placement experience intentionally has no language toggle and is always presented in Thai, regardless of the language selected during onboarding. This does not modify the user's saved global app-language preference. Closing placement takes the user to My Pathway, where the app returns to their selected language.

The placement introduction, controls, questions, and answer choices are all Thai. The test is intended to assess basic listening comprehension rather than broader English reading ability.

The Thai copy currently in the application and seed data is provisional design copy produced for layout testing. Pailin Abroad's Thai translator is preparing the official translations. The provisional strings must be reviewed and replaced with the translator-approved copy before release.

The real guest and onboarding flows navigate directly to the dedicated placement entry screen, without rendering My Pathway behind it. The admin-only Profile button opens this same entry screen for testing; it no longer opens a modal preview over My Pathway.

Show the automatic placement entry only when no completed placement state exists:

- Registered user: `placement_completed_at` is null.
- Guest: local `placementCompletedAt` is absent.

Completing the test records the result before presenting the final screen. Therefore, both actions on that screen behave correctly:

- **Go to Level:** navigate to the first lesson for `placement_level`.
- **Close:** dismiss the popup; My Pathway will still use the saved placement level.

If dismissal before completing the test is supported, keep completion unset so the app can offer the test again. Whether it reappears immediately on every launch or is delayed is a product decision separate from placement completion.

## My Pathway integration

Placement establishes the initial pathway position, but must not continually reset existing lesson progress. Resolve the pathway starting point in this order:

```ts
const pathwayStartLevel =
  existingLessonProgressLevel ??
  placementLevel ??
  1;
```

This means:

1. Existing learning progress takes priority.
2. A placement result is used when no lesson progress exists.
3. Level 1 remains the fallback when neither exists.

The existing direct-navigation code can continue to handle the **Go to Level** button. The saved placement result mainly ensures My Pathway reflects the assigned level when the final popup is closed.

## Scoring responsibility

The mobile client calculates the number of correct answers and applies `scoring_rules` locally. This intentionally avoids unnecessary content and answer-submission endpoints. If the placement result ever controls paid access or another consequential entitlement, scoring should move to a trusted backend at that time.
