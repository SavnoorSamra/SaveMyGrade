#!/usr/bin/env python3
"""Export SFU professors (school_id=1482) from RateMyProfessor to CSV."""

from __future__ import annotations

import argparse
import base64
import csv
from pathlib import Path

try:
    import requests
    from tqdm import tqdm
    import RateMyProfessor_Database_APIs.main as rmp_main
except ModuleNotFoundError as exc:
    raise SystemExit(
        f"Missing dependency: {exc.name}\\n"
        "Install backend dependencies with:\\n"
        "  python3 -m pip install -r backend/requirements.txt"
    ) from exc

SFU_SCHOOL_ID = "1482"
SFU_SCHOOL_NAME = "Simon Fraser University"


def to_school_unique_id(legacy_school_id: str) -> str:
    raw = f"School-{legacy_school_id}".encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10, help="Number of rows to print to terminal")
    parser.add_argument(
        "--csv-out",
        default="",
        help="Output CSV path (default: backend/data/professors_1482.csv)",
    )
    return parser.parse_args()


def resolve_csv_path(csv_out_arg: str) -> Path:
    if csv_out_arg:
        return Path(csv_out_arg).expanduser().resolve()
    default_dir = Path(__file__).resolve().parent / "data"
    return (default_dir / f"professors_{SFU_SCHOOL_ID}.csv").resolve()


def fetch_professors_for_sfu() -> list:
    has_next_page = True
    cursor = None
    all_nodes = []
    batch_size = 500

    query = {
        "text": "",
        "schoolID": to_school_unique_id(SFU_SCHOOL_ID),
        "fallback": False,
        "departmentID": None,
    }

    total_teachers = None
    progress_bar = None

    while has_next_page:
        result = rmp_main.fetch_professors_in_a_page(
            count=batch_size,
            cursor=cursor,
            query=query,
            school_id=SFU_SCHOOL_ID,
        )

        teachers = result["data"]["search"]["teachers"]
        edges = teachers["edges"]

        if total_teachers is None:
            total_teachers = teachers["resultCount"]
            progress_bar = tqdm(total=total_teachers, desc=f"Fetching school {SFU_SCHOOL_ID}")

        all_nodes.extend([edge["node"] for edge in edges])
        progress_bar.update(len(edges))

        has_next_page = teachers["pageInfo"]["hasNextPage"]
        cursor = teachers["pageInfo"]["endCursor"]

    if progress_bar is not None:
        progress_bar.close()

    return [rmp_main.parse_professor_gist(node) for node in all_nodes]


def write_professors_csv(professors: list, csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "legacy_school_id",
        "school_name",
        "school_city",
        "school_state",
        "school_country",
        "professor_id",
        "professor_legacy_id",
        "first_name",
        "last_name",
        "department",
        "avg_rating",
        "avg_difficulty",
        "num_ratings",
        "would_take_again_percent",
        "is_saved",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for prof in professors:
            school = prof.school or {}
            writer.writerow(
                {
                    "legacy_school_id": school.get("legacyId", ""),
                    "school_name": school.get("name", ""),
                    "school_city": school.get("city", ""),
                    "school_state": school.get("state", ""),
                    "school_country": school.get("country", ""),
                    "professor_id": prof.id,
                    "professor_legacy_id": prof.legacy_id,
                    "first_name": prof.first_name,
                    "last_name": prof.last_name,
                    "department": prof.department,
                    "avg_rating": prof.avg_rating,
                    "avg_difficulty": prof.avg_difficulty,
                    "num_ratings": prof.num_ratings,
                    "would_take_again_percent": prof.would_take_again_percent,
                    "is_saved": prof.is_saved,
                }
            )


def main() -> int:
    args = parse_args()

    try:
        professors = fetch_professors_for_sfu()
    except requests.RequestException as exc:
        raise SystemExit(
            "Network error while fetching from RateMyProfessor.\\n"
            "Check internet/DNS/firewall and retry.\\n"
            f"Details: {exc}"
        ) from exc
    except Exception as exc:
        raise SystemExit(f"Scrape failed for school_id={SFU_SCHOOL_ID}: {exc}") from exc

    matched = [
        p
        for p in professors
        if str((p.school or {}).get("legacyId", "")).strip() == SFU_SCHOOL_ID
    ]

    print(f"Total fetched: {len(professors)}")
    print(f"Matched school '{SFU_SCHOOL_NAME}' (legacy_id={SFU_SCHOOL_ID}): {len(matched)}")

    if not matched:
        raise SystemExit("No SFU professors matched. Check RateMyProfessor response and retry.")

    csv_path = resolve_csv_path(args.csv_out)
    write_professors_csv(matched, csv_path)
    print(f"Saved CSV: {csv_path} ({len(matched)} rows)")

    for prof in matched[: args.limit]:
        print(prof)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
