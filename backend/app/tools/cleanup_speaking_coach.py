"""Run speaking-coach retention cleanup from a worker or one-off Machine."""

import json

from app.speaking_coach_cleanup import run_retention_cleanup


def main() -> None:
    print(json.dumps(run_retention_cleanup(), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
