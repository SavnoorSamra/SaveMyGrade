#!/usr/bin/env python3
"""Export professor ratings/comments into department folders.

Workflow:
1) Create a folder for every department listed in a text file.
2) For every professor row in the CSV, fetch full professor details via
   RateMyProfessor_Database_APIs.main.fetch_a_professor.
3) Write one text file per professor under that professor's department folder.
4) Verify output count matches the unique-professor count exactly.
"""

from __future__ import annotations

import argparse
import base64
import csv
import random
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

import requests

try:
    import RateMyProfessor_Database_APIs.main as rmp_main
except ModuleNotFoundError as exc:
    raise SystemExit(
        f"Missing dependency: {exc.name}\n"
        "Install backend dependencies with:\n"
        "  python3 -m pip install -r backend/requirements.txt"
    ) from exc

IGNORED_DEPARTMENTS = {"ta", "not specified", "select department"}
REQUEST_LOCK = threading.Lock()
LAST_REQUEST_AT = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.set_defaults(resume=True)
    parser.add_argument(
        "--input-csv",
        default="backend/data/professors_1482.csv",
        help="Path to professors CSV",
    )
    parser.add_argument(
        "--departments-file",
        default="frontend/data/departments_1482.txt",
        help="Path to newline-separated departments list",
    )
    parser.add_argument(
        "--output-dir",
        default="backend/data/professor_reviews_by_department",
        help="Root folder for per-department professor files",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Concurrent fetch workers",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retries per professor fetch",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.0,
        help="Base seconds between retries (uses exponential backoff)",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.35,
        help="Minimum seconds between API requests across all workers",
    )
    parser.add_argument(
        "--cooldown-403",
        type=float,
        default=15.0,
        help="Base cooldown seconds when a 403 is returned",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not clear existing output directory before exporting",
    )
    parser.add_argument(
        "--resume",
        dest="resume",
        action="store_true",
        help="Skip professors that already have a valid output file (default)",
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Re-fetch even if a professor file already exists",
    )
    return parser.parse_args()


def canonical_department(value: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\bamp\b", "&", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*&\s*", " & ", text)
    text = re.sub(r"\s+", " ", text).strip()

    manual_map = {
        "Art Design": "Art & Design",
        "Biomedical Physiology Kinesiology": "Biomedical Physiology & Kinesiology",
        "Counseling Educational Psych": "Counseling & Educational Psych",
        "Molecular Biology Biochemistry": "Molecular Biology & Biochemistry",
        "Publishing Printing": "Publishing & Printing",
        "Sociology Anthropology": "Sociology & Anthropology",
    }
    return manual_map.get(text, text)


def is_ignored_department(value: str) -> bool:
    return canonical_department(value).strip().lower() in IGNORED_DEPARTMENTS


def sanitize_filename_component(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^A-Za-z0-9._-]", "", value)
    return value or "unknown"


def load_departments(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"Departments file not found: {path}")

    departments: list[str] = []
    seen: set[str] = set()

    for raw in path.read_text(encoding="utf-8").splitlines():
        dept = canonical_department(raw)
        if not dept:
            continue
        if dept not in seen:
            seen.add(dept)
            departments.append(dept)

    if not departments:
        raise SystemExit(f"No departments found in: {path}")

    return departments


def load_professors(csv_path: Path) -> tuple[list[dict[str, str]], int, int]:
    if not csv_path.exists():
        raise SystemExit(f"Input CSV not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        required = {"professor_legacy_id", "first_name", "last_name", "department"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV missing columns: {sorted(missing)}")

        rows = list(reader)

    if not rows:
        raise SystemExit("Input CSV has no professor rows.")

    unique_rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    skipped_duplicates = 0
    skipped_ignored_departments = 0

    for row in rows:
        legacy_id = (row.get("professor_legacy_id") or "").strip()
        if not legacy_id:
            raise SystemExit("Found row with empty professor_legacy_id.")
        if is_ignored_department(row.get("department", "")):
            skipped_ignored_departments += 1
            continue
        if legacy_id in seen_ids:
            skipped_duplicates += 1
            continue
        seen_ids.add(legacy_id)
        unique_rows.append(row)

    if not unique_rows:
        raise SystemExit("No valid professors found after de-duplication.")

    return unique_rows, skipped_duplicates, skipped_ignored_departments


def build_output_path(output_root: Path, department: str, legacy_id: str, first_name: str, last_name: str) -> Path:
    dept_folder = output_root / department
    filename = (
        f"{sanitize_filename_component(last_name)}_"
        f"{sanitize_filename_component(first_name)}_"
        f"{sanitize_filename_component(legacy_id)}.txt"
    )
    return dept_folder / filename


def format_professor_text(prof: object, source_department: str) -> str:
    ratings = list(getattr(prof, "ratings", []) or [])
    lines = [
        f"Professor: {getattr(prof, 'first_name', '')} {getattr(prof, 'last_name', '')}".strip(),
        f"Professor Legacy ID: {getattr(prof, 'legacy_id', '')}",
        f"Professor ID: {getattr(prof, 'id', '')}",
        f"Department (CSV): {source_department}",
        f"Department (Fetched): {getattr(prof, 'department', '')}",
        f"Avg Rating: {getattr(prof, 'avg_rating', '')}",
        f"Avg Difficulty: {getattr(prof, 'avg_difficulty', '')}",
        f"Num Ratings: {getattr(prof, 'num_ratings', '')}",
        f"Would Take Again Percent: {getattr(prof, 'would_take_again_percent', '')}",
        "",
        f"Ratings Count Returned: {len(ratings)}",
        "",
    ]

    for idx, rating in enumerate(ratings, start=1):
        lines.extend(
            [
                f"--- Rating #{idx} ---",
                f"Class: {rating.get('class', '')}",
                f"Date: {rating.get('date', '')}",
                f"Helpful Rating: {rating.get('helpfulRating', '')}",
                f"Clarity Rating: {rating.get('clarityRating', '')}",
                f"Difficulty Rating: {rating.get('difficultyRating', '')}",
                f"Attendance Mandatory: {rating.get('attendanceMandatory', '')}",
                f"Textbook Use: {rating.get('textbookUse', '')}",
                f"For Credit: {rating.get('isForCredit', '')}",
                f"Online Class: {rating.get('isForOnlineClass', '')}",
                "Comment:",
                (rating.get("comment") or "").strip(),
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def to_professor_unique_id(legacy_professor_id: str) -> str:
    raw = f"Teacher-{legacy_professor_id}".encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def pace_requests(min_delay_seconds: float) -> None:
    global LAST_REQUEST_AT
    with REQUEST_LOCK:
        now = time.monotonic()
        wait_seconds = min_delay_seconds - (now - LAST_REQUEST_AT)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        LAST_REQUEST_AT = time.monotonic()


def fetch_professor_direct(professor_legacy_id: str):
    headers = (getattr(rmp_main, "HEADERS", {}) or {}).copy()
    headers["Referer"] = f"https://www.ratemyprofessors.com/professor/{professor_legacy_id}"
    headers["Origin"] = "https://www.ratemyprofessors.com"
    headers["Accept"] = "application/json"

    query_string = rmp_main.fetch_a_professors_query_string
    variables = {"id": to_professor_unique_id(professor_legacy_id)}

    response = requests.post(
        rmp_main.GRAPHQL_ENDPOINT,
        json={"query": query_string, "variables": variables},
        headers=headers,
        timeout=30,
    )

    if response.status_code == 200:
        return rmp_main.parse_professor(response.json())

    raise requests.HTTPError(
        f"Query failed with status code {response.status_code}: {response.text[:500]}",
        response=response,
    )


def fetch_with_retries(
    professor_legacy_id: str,
    retries: int,
    retry_delay: float,
    request_delay: float,
    cooldown_403: float,
):
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            pace_requests(request_delay)
            return fetch_professor_direct(professor_legacy_id)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            status_code = None
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                status_code = exc.response.status_code

            if attempt < retries:
                if status_code == 403:
                    # 403 from RMP is usually temporary anti-bot/rate-limit pressure.
                    sleep_s = cooldown_403 * attempt + random.uniform(0.0, 2.0)
                else:
                    sleep_s = retry_delay * (2 ** (attempt - 1)) + random.uniform(0.0, 0.5)
                time.sleep(sleep_s)
    assert last_exc is not None
    raise last_exc


def ensure_department_folders(output_root: Path, departments: Iterable[str]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for department in departments:
        (output_root / department).mkdir(parents=True, exist_ok=True)


def is_existing_professor_file_valid(path: Path, legacy_id: str) -> bool:
    if not path.exists() or path.suffix.lower() != ".txt" or path.stat().st_size == 0:
        return False
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return (
        f"Professor Legacy ID: {legacy_id}" in content
        and "Ratings Count Returned:" in content
    )


def export_one(
    row: dict[str, str],
    output_root: Path,
    retries: int,
    retry_delay: float,
    request_delay: float,
    cooldown_403: float,
) -> Path:
    legacy_id = row["professor_legacy_id"].strip()
    first_name = row.get("first_name", "")
    last_name = row.get("last_name", "")
    department = canonical_department(row.get("department", ""))

    prof = fetch_with_retries(
        legacy_id,
        retries=retries,
        retry_delay=retry_delay,
        request_delay=request_delay,
        cooldown_403=cooldown_403,
    )

    out_path = build_output_path(output_root, department, legacy_id, first_name, last_name)
    content = format_professor_text(prof, source_department=department)
    out_path.write_text(content, encoding="utf-8")
    return out_path


def main() -> int:
    args = parse_args()
    csv_path = Path(args.input_csv).expanduser().resolve()
    departments_path = Path(args.departments_file).expanduser().resolve()
    output_root = Path(args.output_dir).expanduser().resolve()

    departments = load_departments(departments_path)
    professors, skipped_duplicates, skipped_ignored_departments = load_professors(csv_path)

    departments_set = set(departments)
    csv_departments = {
        canonical_department(row.get("department", ""))
        for row in professors
        if canonical_department(row.get("department", ""))
    }
    missing_departments = sorted(csv_departments - departments_set)
    if missing_departments:
        raise SystemExit(
            "Departments found in CSV but not in departments file:\n"
            + "\n".join(missing_departments)
        )

    if output_root.exists() and not args.no_clean:
        if args.resume:
            print("Output directory exists. Resume mode is ON, keeping existing files.")
        else:
            shutil.rmtree(output_root)

    ensure_department_folders(output_root, departments)

    expected_count = len(professors)
    skipped_existing = 0
    pending_professors: list[dict[str, str]] = []
    for row in professors:
        legacy_id = row["professor_legacy_id"].strip()
        out_path = build_output_path(
            output_root=output_root,
            department=canonical_department(row.get("department", "")),
            legacy_id=legacy_id,
            first_name=row.get("first_name", ""),
            last_name=row.get("last_name", ""),
        )
        if args.resume and is_existing_professor_file_valid(out_path, legacy_id):
            skipped_existing += 1
            continue
        pending_professors.append(row)

    print(f"Departments: {len(departments)}")
    print(f"Professors to export (unique): {expected_count}")
    print(f"Already scraped and skipped: {skipped_existing}")
    print(f"Remaining to fetch now: {len(pending_professors)}")
    print(f"Duplicate CSV rows skipped: {skipped_duplicates}")
    print(f"Ignored-department rows skipped: {skipped_ignored_departments}")
    print(f"Output root: {output_root}")

    written_paths: list[Path] = []
    failures: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_to_row = {
            executor.submit(
                export_one,
                row,
                output_root,
                args.retries,
                args.retry_delay,
                args.request_delay,
                args.cooldown_403,
            ): row
            for row in pending_professors
        }

        completed = 0
        for future in as_completed(future_to_row):
            row = future_to_row[future]
            legacy_id = row.get("professor_legacy_id", "")
            completed += 1
            try:
                path = future.result()
                written_paths.append(path)
            except Exception as exc:  # noqa: BLE001
                failures.append((legacy_id, str(exc)))

            total_pending = len(pending_professors)
            if total_pending and (completed % 100 == 0 or completed == total_pending):
                print(f"Progress: {completed}/{total_pending} | failures={len(failures)}")

    if failures:
        error_preview = "\n".join(
            f"  - {legacy_id}: {message}" for legacy_id, message in failures[:20]
        )
        raise SystemExit(
            f"Failed to export {len(failures)} professors. Sample failures:\n{error_preview}"
        )

    missing_files: list[Path] = []
    for row in professors:
        expected_path = build_output_path(
            output_root=output_root,
            department=canonical_department(row.get("department", "")),
            legacy_id=row["professor_legacy_id"].strip(),
            first_name=row.get("first_name", ""),
            last_name=row.get("last_name", ""),
        )
        if not is_existing_professor_file_valid(expected_path, row["professor_legacy_id"].strip()):
            missing_files.append(expected_path)

    if missing_files:
        raise SystemExit(
            "Missing or invalid professor files after export.\n"
            f"Expected complete set: {expected_count}, missing/invalid: {len(missing_files)}\n"
            "Sample missing paths:\n"
            + "\n".join(str(p) for p in missing_files[:20])
        )

    file_count = len(list(output_root.rglob("*.txt")))
    print(f"Success: verified {expected_count} expected professor files (found {file_count} total .txt files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
