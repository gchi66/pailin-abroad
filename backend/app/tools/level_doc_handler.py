# app/tools/level_doc_handler.py
import argparse
import subprocess
import sys
from typing import Dict, Tuple

# ---- CONFIG: level → (EN_ID, TH_ID) ----

LEVEL_DOC_IDS: Dict[int, Dict[str, str]] = {
    1: {"en": "1VdXoHKRFd1PGgN317-JLZsusQwZLygaXns4DeA6jBns", "th": "1dpC-DhKJ6OCRNt9GgsmNHw7BD5dcCRRQUg-GMDeAInk"},
    2: {"en": "1ca6cFOwVsyqrJaagNMz78-2THMFVqy7ZmmAMqdkfVBU", "th": "1IC1xkAQv7LpFY3F9GMCHAzi_x5ZV_n_rNxAxdMq4kcs"},
    3: {"en": "1m2DCqs00sY7iNjP6Wc6UdVn4EaFVWkKEB7j_f8u40IA", "th": "1CwbS5BS1BQssCLC6u3pVKpIe9QJx9F2wqcU3uXfPdt4"},
    4: {"en": "1Wqa5L39_1Z2pFbBTJGng_pl3WO7lR9uUcK0jvys_lZs", "th": "1zwrm-oiQWpSOiyTDBFqIHMvWSdOitCWcxeoBZBRhKxc"},
    5: {"en": "13-30sdtvpJHinbwOtgJ4bM3bNfJPEYneUg2Do8QGE24", "th": "1o0rYbdgPdAXyHIddVcSjuFoabte0V2GSs_cITS1noJo"},
    6: {"en": "1rAJZ7dgRjZ00Jz1-YsNSZKLPfTorb2wNexDQ6Cv8iFc", "th": "1j_zzzdmeYJscvq7LJfQOhH72FSqVOraHFnRlzgIGEqE"},
    7: {"en": "15zR8IzjvGcDekJOWYA9yIBgYyWYOMJf4_J6mjTNuaVA", "th": "1fPnqUi8W3jgV9GVqhBvMA_sUCu9CIem39cJKSZ9_FvQ"},
    8: {"en": "1voxQg8MogZNTPJ-5Wdf7Ul-tBzo71lBxNajdd2IiERc", "th": "1_05qcgZehlM8NtJ-ZZHXAAGUTb8Yys0rixYzEtHKx9M"},
    9: {"en": "1S228qJT1HAKY-EpBleCtsr4D1RVWxFgo-FoN4DM2HSk", "th": "1DHiK-zy0h8BCMCQEyNZBP5kL5DMt36sk27z3rbJfJGQ"},
    10: {"en": "14ogr25RAFGbIgUoeX6O9b5RuoRATRvyoaEVXZb4GhkM", "th": "1MfkKQDP26KG-PbwKNyeG9omyYus6AteQ7xcSlJ1SFdE"},
    11: {"en": "10TaSOUsaGj9YHZn-XlpEEw6x789CRajOQTgYZErdtek", "th": "14V4jovYayaMabpZwo5obWDS3gUb4a9kUisHHvdmhNko"},
    12: {"en": "1vBxUOrpK9UFgguG7oy7XDsKxhJQa4OugCVsCSQU2U48", "th": "1a9a9AuVvKqMPzViSGkP5FoE5Pkcwh8_uQhQYq0dxDlA"},
    13: {"en": "13iiq-u3npl0-7cNRn0W1L8boxuwkhvcUnVqag7znJsY", "th": ""},
    14: {"en": "1sRWYOhAs0BoLrsjLyQrYibCoDD2hR8O0gSALIydHZEc", "th": ""},
    15: {"en": "1kRrX97_DBEMNmunH79V8VFMUHcvEuTnB2zdEWsktPqw", "th": ""},
    16: {"en": "1tWkViUwHwAYb-6-xADXHWYEpf4T7ydXoiBgnfWqbHuQ", "th": ""},
}


def stage_for_level(level: int) -> str:
    if 1 <= level <= 4:
        return "Beginner"
    if 5 <= level <= 8:
        return "Intermediate"
    if 9 <= level <= 12:
        return "Advanced"
    if 13 <= level <= 16:
        return "Expert"
    raise ValueError(f"No stage mapping configured for level {level}")


def run(cmd: list[str]) -> None:
    print("\n→ Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def process_level(level: int, skip_import: bool, skip_th: bool, skip_en: bool, skip_parse: bool) -> None:
    stage = stage_for_level(level)
    en_id = LEVEL_DOC_IDS[level]["en"]
    th_id = LEVEL_DOC_IDS[level]["th"]

    en_out = f"data/level_{level}.json"
    th_out = f"data/level_{level}_th.json"

    if not en_id:
        raise ValueError(f"Missing EN doc id for level {level}")

    if not skip_en:
        print("\n===============================")
        print(f" Level {level} - {stage} (EN)")
        print("===============================")

        # Parse EN
        if not skip_parse:
            run([
                sys.executable, "-m", "app.tools.parser",
                en_id, "--stage", stage, "--output", en_out
            ])
        else:
            print("⚠️  Skipping EN parse; importing existing JSON.")

        # Import EN
        if not skip_import:
            run([
                sys.executable, "-m", "app.tools.import_lessons",
                en_out
            ])
    else:
        print(f"⚠️  Skipping English for level {level}")

    # Optionally skip Thai (or if no TH doc id configured)
    if skip_th or not th_id:
        if not th_id and not skip_th:
            print(f"⚠️  No Thai doc id for level {level}; skipping Thai.")
        print(f"⚠️  Skipping Thai for level {level}")
        return

    print("\n===============================")
    print(f" Level {level} - {stage} (TH)")
    print("===============================")

    # Parse TH
    if not skip_parse:
        run([
            sys.executable, "-m", "app.tools.parser",
            th_id, "--stage", stage, "--lang", "th", "--output", th_out
        ])
    else:
        print("⚠️  Skipping TH parse; importing existing JSON.")

    # Import TH
    if not skip_import:
        run([
            sys.executable, "-m", "app.tools.import_lessons",
            th_out, "--lang", "th"
        ])


def parse_args(argv: list[str]):
    parser = argparse.ArgumentParser(description="Parse + import lesson docs.")
    parser.add_argument("start", type=int)
    parser.add_argument("end", type=int, nargs="?")
    parser.add_argument("--skip-parse", action="store_true", help="Skip parsing; only import existing JSON")
    parser.add_argument("--skip-import", action="store_true", help="Skip importing into Supabase")
    parser.add_argument("--skip-th", action="store_true", help="Skip parsing/importing Thai docs")
    parser.add_argument("--skip-en", action="store_true", help="Skip parsing/importing English docs")
    args = parser.parse_args(argv)

    start = args.start
    end = args.end if args.end else start
    return start, end, args.skip_import, args.skip_th, args.skip_en, args.skip_parse


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    start, end, skip_import, skip_th, skip_en, skip_parse = parse_args(argv)

    print(f"Processing levels {start} → {end}")
    if skip_import:
        print("⚠️  Skipping imports")
    if skip_th:
        print("⚠️  Skipping Thai docs")
    if skip_en:
        print("⚠️  Skipping English docs")
    if skip_parse:
        print("⚠️  Skipping parsing; importing only")

    for level in range(start, end + 1):
        process_level(level, skip_import, skip_th, skip_en, skip_parse)

    print("\n✅ Done.")


if __name__ == "__main__":
    main()
