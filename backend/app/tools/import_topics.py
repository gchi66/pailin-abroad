#!/usr/bin/env python3
"""
Import topic library entries into Supabase from JSON files.

Usage:
  # Import a single topic JSON file
  python -m app.tools.import_topics data/topics/countable_uncountable.json

  # Import a folder of topic JSON files
  python -m app.tools.import_topics data/topics/

  # Import the main topic library array file
  python -m app.tools.import_topics data/topic_library.json

  # Dry run (print payloads without writing)
  python -m app.tools.import_topics data/topics/ --dry-run

  # Import Thai translations
  python -m app.tools.import_topics data/topics/th/ --lang th
"""

import os
import json
import argparse
import glob
from app.supabase_client import supabase


# Required top-level keys in each topic JSON object
REQUIRED_KEYS = {
    "name",
    "slug",
    "content_jsonb"
}


def _resolve_sentinel_links(nodes, supabase_client):
    """
    Walk through content_jsonb nodes and replace sentinel links
    (https://pa.invalid/lesson/X.Y) with real /lesson/<uuid>.
    """
    if not nodes:
        return nodes
    for node in nodes:
        inlines = node.get("inlines") or []
        for span in inlines:
            link = span.get("link")
            if link and link.startswith("https://pa.invalid/lesson/"):
                ext_id = link.rsplit("/", 1)[-1]
                try:
                    result = (
                        supabase_client
                        .table("lessons")
                        .select("id")
                        .eq("lesson_external_id", ext_id)
                        .single()
                        .execute()
                    )
                    if result.data:
                        span["link"] = f"/lesson/{result.data['id']}"
                except Exception as e:
                    print(f"[WARN] Could not resolve sentinel link {link}: {e}")
    return nodes


def _extract_th(val):
    """Extract Thai text from various formats."""
    if isinstance(val, dict):
        for k in ("th", "TH", "thai", "Thai"):
            v = val.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in val.values():
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""
    if isinstance(val, str):
        return val.strip()
    return ""


def validate_topic_schema(data):
    """
    Validate that the JSON matches expected structure.

    Expected structure:
    {
      "name": "Topic Name",
      "slug": "topic-slug",
      "idx": 1,  // optional
      "tags": [],  // optional
      "content_jsonb": [...]  // required array of nodes
    }
    """
    errors = []

    if not isinstance(data, dict):
        errors.append("Root must be an object/dict")
        return errors

    # Check required fields
    if "name" not in data:
        errors.append("Missing required field: 'name'")
    elif not isinstance(data["name"], str) or not data["name"].strip():
        errors.append("'name' must be a non-empty string")

    if "slug" not in data:
        errors.append("Missing required field: 'slug'")
    elif not isinstance(data["slug"], str) or not data["slug"].strip():
        errors.append("'slug' must be a non-empty string")

    if "content_jsonb" not in data:
        errors.append("Missing required field: 'content_jsonb'")
    elif not isinstance(data["content_jsonb"], list):
        errors.append("'content_jsonb' must be an array")
    elif len(data["content_jsonb"]) == 0:
        errors.append("'content_jsonb' array is empty")

    # Check optional fields have correct types
    if "idx" in data and data["idx"] is not None:
        if not isinstance(data["idx"], int):
            errors.append("'idx' must be an integer or null")

    if "tags" in data and data["tags"] is not None:
        if not isinstance(data["tags"], list):
            errors.append("'tags' must be an array")
        elif not all(isinstance(t, str) for t in data["tags"]):
            errors.append("'tags' array must contain only strings")

    # Validate content_jsonb structure (basic check)
    if "content_jsonb" in data and isinstance(data["content_jsonb"], list):
        for i, node in enumerate(data["content_jsonb"]):
            if not isinstance(node, dict):
                errors.append(f"content_jsonb[{i}] must be an object")
            elif "kind" not in node:
                errors.append(f"content_jsonb[{i}] missing 'kind' field")
            elif "inlines" not in node and node.get("kind") != "table":
                errors.append(f"content_jsonb[{i}] missing 'inlines' field (kind={node.get('kind')})")

    return errors


def process_topic(data, lang="en", dry_run=False):
    """Process a single topic object."""
    keys = set(data.keys())
    if not REQUIRED_KEYS.issubset(keys):
        print(f"[ERROR] Missing keys: {REQUIRED_KEYS - keys}")
        return False

    return upsert_topic(data, lang=lang, dry_run=dry_run)


def upsert_topic(data, lang="en", dry_run=False):
    """
    Upsert a topic into the topic_library table.
    EN: inserts/updates base columns (name, content_jsonb)
    TH: updates Thai columns (name_th, content_jsonb_th)

    Args:
        data: Topic data matching database schema
        lang: Language code ('en' or 'th')
        dry_run: If True, print actions without writing to database

    Returns:
        bool: True if successful, False otherwise
    """
    lang = (lang or "en").lower()
    if lang not in ("en", "th"):
        raise ValueError("lang must be 'en' or 'th'")

    # Validate schema
    errors = validate_topic_schema(data)
    if errors:
        print(f"[ERROR] Schema validation failed for '{data.get('name', 'unknown')}':")
        for error in errors:
            print(f"  - {error}")
        return False

    slug = data["slug"].strip()

    if lang == "en":
        # Resolve sentinel links in content_jsonb
        content_jsonb = data.get("content_jsonb") or []
        if content_jsonb:
            content_jsonb = _resolve_sentinel_links(content_jsonb, supabase)

        # Base-language columns
        record = {
            "name": data["name"].strip(),
            "slug": slug,
            "content_jsonb": content_jsonb,
            "tags": data.get("tags", []) or [],
        }

        if "idx" in data and data["idx"] is not None:
            record["idx"] = data["idx"]

        subtitle = data.get("subtitle")
        if isinstance(subtitle, str) and subtitle.strip():
            record["subtitle"] = subtitle.strip()

        if dry_run:
            print(f"\n[DRY RUN] Topic EN UPSERT:")
            print(f"  name: {record['name']}")
            print(f"  slug: {record['slug']}")
            print(f"  idx: {record.get('idx', 'null')}")
            print(f"  tags: {record['tags']}")
            print(f"  content_jsonb nodes: {len(record['content_jsonb'])}")

            # Show first few nodes for verification
            print(f"\n  First 3 nodes:")
            for i, node in enumerate(record['content_jsonb'][:3]):
                node_text = ""
                if "inlines" in node:
                    node_text = "".join(inline.get("text", "") for inline in node["inlines"])[:50]
                print(f"    [{i}] {node.get('kind')}: {node_text}...")

            if len(record['content_jsonb']) > 3:
                print(f"    ... and {len(record['content_jsonb']) - 3} more nodes")

            return True

        try:
            result = (
                supabase
                .table("topic_library")
                .upsert(record, on_conflict="slug")
                .execute()
            )

            if result.data:
                topic_id = result.data[0].get("id")
                print(f"[SUCCESS] Upserted topic (EN): {record['name']} (id: {topic_id}, slug: {record['slug']})")
                return True
            else:
                print(f"[ERROR] EN upsert returned no data for: {record['name']}")
                return False

        except Exception as e:
            print(f"[ERROR] Failed to upsert topic (EN) '{record['name']}': {e}")
            import traceback
            traceback.print_exc()
            return False

    # ---------- TH path: update-only ----------
    # Resolve sentinel links in content_jsonb_th
    content_jsonb_th = data.get("content_jsonb_th") or data.get("content_jsonb") or []
    if content_jsonb_th:
        content_jsonb_th = _resolve_sentinel_links(content_jsonb_th, supabase)

    name_th_val = data.get("name_th") or data.get("name") or ""
    subtitle_th_val = data.get("subtitle_th") or data.get("subtitle") or ""

    name_th = _extract_th(name_th_val)
    if not name_th and isinstance(name_th_val, str):
        name_th = name_th_val.strip()

    th_update = {
        "name_th": name_th,
        "content_jsonb_th": content_jsonb_th
    }

    subtitle_th_val = _extract_th(subtitle_th_val)
    if subtitle_th_val:
        th_update["subtitle_th"] = subtitle_th_val

    if dry_run:
        print(f"\n[DRY RUN] Topic TH UPDATE where slug='{slug}':")
        print(f"  name_th: {th_update['name_th']}")
        print(f"  content_jsonb_th nodes: {len(th_update['content_jsonb_th'])}")
        if subtitle_th_val:
            print(f"  subtitle_th: {subtitle_th_val}")
        return True

    try:
        upd = (
            supabase.table("topic_library")
            .update(th_update)
            .eq("slug", slug)
            .execute()
        )

        if not (upd.data or []):
            print(f"[WARN] TH update found no EN base row for slug '{slug}'. Run EN import first.")
            return False

        print(f"[SUCCESS] Updated topic (TH): {th_update['name_th']} (slug: {slug})")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to update topic (TH) for slug '{slug}': {e}")
        import traceback
        traceback.print_exc()
        return False


def import_topic_from_file(file_path, lang="en", dry_run=False):
    """Import topics from a JSON file (single topic or array)."""
    if not os.path.isfile(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return False

    print(f"\nImporting from: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in {file_path}: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to read {file_path}: {e}")
        return False

    # Handle both single topic object and array of topics
    if isinstance(data, list):
        topics = data
        print(f"Processing {len(topics)} topics from array")
    else:
        topics = [data]
        print(f"Processing single topic")

    success_count = 0
    fail_count = 0

    for i, topic in enumerate(topics):
        print(f"\nProcessing topic {i+1}/{len(topics)}: {topic.get('name', 'unknown')}")
        if dry_run:
            print("\n--- Full JSON content for topic ---")
            print(json.dumps(topic, indent=2, ensure_ascii=False))
            print("--- End JSON content ---\n")

        if process_topic(topic, lang=lang, dry_run=dry_run):
            success_count += 1
        else:
            fail_count += 1

    print(f"\nFile import complete: {success_count} success, {fail_count} failed")
    return fail_count == 0


def import_topics_from_folder(folder_path, lang="en", dry_run=False):
    """Import all JSON files from a folder."""
    if not os.path.isdir(folder_path):
        print(f"[ERROR] Folder not found: {folder_path}")
        return False

    json_files = sorted(glob.glob(os.path.join(folder_path, "*.json")))

    if not json_files:
        print(f"[WARN] No JSON files found in: {folder_path}")
        return False

    print(f"\n{'='*60}")
    print(f"Found {len(json_files)} JSON file(s) in {folder_path}")
    print(f"Language: {lang}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*60}")

    total_success = 0
    total_fail = 0

    for file_path in json_files:
        print(f"\nImporting file: {file_path}")
        if import_topic_from_file(file_path, lang=lang, dry_run=dry_run):
            total_success += 1
        else:
            total_fail += 1

    print(f"\n{'='*60}")
    print(f"Folder Import Complete: {total_success} files succeeded, {total_fail} files failed")
    print(f"{'='*60}\n")

    return total_fail == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import topic library entries into Supabase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import a single topic (EN)
  python -m app.tools.import_topics data/topics/countable_uncountable.json

  # Import all topics in a folder (EN)
  python -m app.tools.import_topics data/topics/

  # Dry run to preview changes
  python -m app.tools.import_topics data/topics/ --dry-run

  # Import Thai translations
  python -m app.tools.import_topics data/topics/th/ --lang th
        """
    )
    parser.add_argument(
        "path",
        help="Path to a JSON file or folder of JSON files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without writing to database"
    )
    parser.add_argument(
        "--lang",
        choices=["en", "th"],
        default="en",
        help="Language of the topic data (default: en)"
    )

    args = parser.parse_args()

    if os.path.isdir(args.path):
        import_topics_from_folder(args.path, lang=args.lang, dry_run=args.dry_run)
    elif os.path.isfile(args.path):
        import_topic_from_file(args.path, lang=args.lang, dry_run=args.dry_run)
    else:
        print(f"[ERROR] Path not found: {args.path}")
