#!/usr/bin/env python3
"""Extract unique departments from professors_1482.csv."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-csv",
        default="backend/data/professors_1482.csv",
        help="Path to professors CSV",
    )
    parser.add_argument(
        "--output-file",
        default="frontend/data/departments_1482.txt",
        help="Output file path (default: frontend/data/departments_1482.txt)",
    )
    parser.add_argument(
        "--normalize-csv-in-place",
        action="store_true",
        help="Normalize department labels and rewrite input CSV in place",
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


def normalize_csv_departments(csv_path: Path) -> tuple[int, int]:
    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    if "department" not in fieldnames:
        raise SystemExit("CSV does not contain a 'department' column.")

    changed = 0
    for row in rows:
        old = row.get("department", "")
        new = canonical_department(old)
        if old != new:
            row["department"] = new
            changed += 1

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return changed, len(rows)


def load_departments(csv_path: Path) -> list[str]:
    if not csv_path.exists():
        raise SystemExit(f"Input CSV not found: {csv_path}")

    departments = set()
    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        if "department" not in (reader.fieldnames or []):
            raise SystemExit("CSV does not contain a 'department' column.")

        for row in reader:
            dept = canonical_department(row.get("department", ""))
            if dept and dept.lower() not in {"select department", "not specified"}:
                departments.add(dept)

    return sorted(departments, key=str.lower)


def write_output(path: Path, departments: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.suffix.lower() == ".csv":
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["department"])
            for dept in departments:
                writer.writerow([dept])
    else:
        with path.open("w", encoding="utf-8") as file:
            for dept in departments:
                file.write(dept + "\n")


def main() -> int:
    args = parse_args()
    input_csv = Path(args.input_csv).expanduser().resolve()

    if args.normalize_csv_in_place:
        changed, total = normalize_csv_departments(input_csv)
        print(f"Normalized departments in CSV: {changed} of {total} rows updated")

    departments = load_departments(input_csv)

    print(f"Found {len(departments)} unique departments")
    for dept in departments:
        print(dept)

    out = Path(args.output_file).expanduser().resolve()
    write_output(out, departments)
    print(f"Saved department list: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
