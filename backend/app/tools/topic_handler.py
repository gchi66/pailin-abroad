# app/tools/topic_handler.py
import argparse
import subprocess
import sys

# ---- CONFIG: topic library doc IDs ----
# Fill these with the Google Doc IDs for the topic library.
TOPIC_DOC_IDS = {
    "en": "1YYf5EjiriqCSenSRQQ5wFR3Hp3ckFn9A_jRgSggcdiM",
    "th": "1bOYQ1U4haqh0KV_ObLw-WXs2coMiJtQdXAy3tS1zhs0",
}


def run(cmd: list[str]) -> None:
    print("\n→ Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def process_topics(skip_import: bool, skip_th: bool, skip_en: bool) -> None:
    en_id = TOPIC_DOC_IDS.get("en", "").strip()
    th_id = TOPIC_DOC_IDS.get("th", "").strip()

    if not skip_en:
        if not en_id:
            raise ValueError("Missing TOPIC_DOC_IDS['en'] in topic_handler.py")
        print("\n===============================")
        print(" Topic Library (EN)")
        print("===============================")
        run([
            sys.executable, "-m", "app.tools.topic_parser",
            en_id, "--output", "data/topic_library.json",
        ])
        if not skip_import:
            run([
                sys.executable, "-m", "app.tools.import_topics",
                "data/topic_library.json",
            ])
    else:
        print("⚠️  Skipping English topic library")

    if skip_th:
        print("⚠️  Skipping Thai topic library")
        return

    if not th_id:
        raise ValueError("Missing TOPIC_DOC_IDS['th'] in topic_handler.py")
    print("\n===============================")
    print(" Topic Library (TH)")
    print("===============================")
    run([
        sys.executable, "-m", "app.tools.topic_parser",
        th_id, "--lang", "th", "--output", "data/topic_library_th.json",
    ])
    if not skip_import:
        run([
            sys.executable, "-m", "app.tools.import_topics",
            "data/topic_library_th.json", "--lang", "th",
        ])


def parse_args(argv: list[str]):
    parser = argparse.ArgumentParser(description="Parse + import topic library docs.")
    parser.add_argument("--skip-import", action="store_true", help="Skip importing into Supabase")
    parser.add_argument("--skip-th", action="store_true", help="Skip parsing/importing Thai doc")
    parser.add_argument("--skip-en", action="store_true", help="Skip parsing/importing English doc")
    args = parser.parse_args(argv)
    return args.skip_import, args.skip_th, args.skip_en


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    skip_import, skip_th, skip_en = parse_args(argv)

    if skip_import:
        print("⚠️  Skipping imports")
    if skip_th:
        print("⚠️  Skipping Thai doc")
    if skip_en:
        print("⚠️  Skipping English doc")

    process_topics(skip_import, skip_th, skip_en)
    print("\n✅ Done.")


if __name__ == "__main__":
    main()
