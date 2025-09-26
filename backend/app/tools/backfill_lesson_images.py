"""
Populate the lesson_images table from objects
already uploaded to the lesson-images bucket.

File pattern: {lesson}_{context}_{seq}.webp
Example: 1.6_practice_1.webp

rclone (copy from Google Drive → Supabase):
    rclone copy \
      "pailin:Pailin Abroad/Site Images/Lesson Images" \
      supabase:"lesson-images" \
      --include "*.webp" \
      -P

Run:
    python -m app.tools.backfill_lesson_images
"""

import os, sys
from supabase import create_client, Client

# ─── 1. Config ─────────────────────────────────────────────────────────────
SUPABASE_URL  = os.getenv("SUPABASE_URL")
SERVICE_ROLE  = os.getenv("SUPABASE_KEY")
BUCKET        = "lesson-images"

if not (SUPABASE_URL and SERVICE_ROLE):
    sys.exit("Set SUPABASE_URL and SUPABASE_KEY in your environment")

sb: Client = create_client(SUPABASE_URL, SERVICE_ROLE)

# ─── 2. List objects with pagination ───────────────────────────────────────
def list_objects_recursive(prefix: str = "") -> list[str]:
    objects: list[str] = []

    def _walk(p: str):
        page = 0
        while True:
            resp = sb.storage.from_(BUCKET).list(
                p,
                {
                    "limit": 100,
                    "offset": page * 100,
                    "sortBy": {"column": "name", "order": "asc"},
                },
            )
            if not resp:
                break

            for obj in resp:
                name = obj["name"]
                full = f"{p}/{name}" if p else name
                if name.endswith("/") or "." not in name:
                    _walk(full.rstrip("/"))
                else:
                    objects.append(full)

            if len(resp) < 100:
                break
            page += 1

    _walk(prefix)
    return objects

# ─── 3. Main ───────────────────────────────────────────────────────────────
def main() -> None:
    print("Gathering lesson images …")
    all_objects = list_objects_recursive()
    print(f"Found {len(all_objects)} objects in bucket")

    rows = []
    seen = set()

    for path in all_objects:
        if not path.lower().endswith(".webp"):
            continue

        # Strip extension → becomes your image_key
        image_key = os.path.splitext(path.split("/")[-1])[0]

        # Lesson ID lookup: assumes "1.6" is the start of the filename
        lesson_external_id = image_key.split("_")[0]  # "1.6"

        # Look up the lesson UUID from lesson_external_id
        try:
            lesson_query = sb.table("lessons").select("id").eq("lesson_external_id", lesson_external_id).execute()
            if not lesson_query.data:
                print(f"SKIP: No lesson found for external_id '{lesson_external_id}' (file: {path})")
                continue
            lesson_id = lesson_query.data[0]["id"]
        except Exception as e:
            print(f"ERROR: Failed to lookup lesson '{lesson_external_id}': {e}")
            continue

        key = (lesson_id, image_key)
        if key in seen:
            continue
        seen.add(key)

        # Construct the public URL for the image
        url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"

        rows.append({
            "lesson_id": lesson_id,
            "image_key": image_key,
            "url": url
        })

    if not rows:
        print("No images to insert.")
        return

    print(f"Upserting {len(rows)} rows into lesson_images …")
    try:
        res = (
            sb.table("lesson_images")
              .upsert(rows, on_conflict="lesson_id,image_key")
              .execute()
        )
        print(f"✅ Success – {len(res.data)} rows upserted/updated.")
    except Exception as e:
        print(f"ERROR: Failed to upsert lesson images: {e}")


if __name__ == "__main__":
    main()
