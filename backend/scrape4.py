#!/usr/bin/env python3
"""Build a master list of SFU courses offered across 2025-2026 term pages.

This script:
1) Starts from the configured term course index URLs.
2) Discovers linked department course pages.
3) Extracts course codes + names from each department page.
4) Writes a de-duplicated master list.

Usage:
  python3 backend/data/professor_reviews_by_department/Engineering/scrape4.py
  python3 backend/data/professor_reviews_by_department/Engineering/scrape4.py --out-csv backend/data/sfu_courses_2025_2026.csv
"""

from __future__ import annotations

import argparse
import csv
import html
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

TERM_INDEX_URLS = [
    "https://www.sfu.ca/students/calendar/2026/summer/courses.html",
    "https://www.sfu.ca/students/calendar/2026/spring/courses.html",
    "https://www.sfu.ca/students/calendar/2025/winter/courses.html",
    "https://www.sfu.ca/students/calendar/2025/fall/courses.html",
    "https://www.sfu.ca/students/calendar/2025/summer/courses.html",
]

COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,6})\s*([0-9]{3}[A-Z]?)\b")


@dataclass(frozen=True)
class CourseRow:
    subject: str
    number: str
    code: str
    title: str
    source_url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-csv",
        default="backend/data/sfu_courses_2025_2026.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout seconds",
    )
    return parser.parse_args()


def get_html(url: str, timeout: float) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def extract_links(page_html: str, base_url: str) -> list[str]:
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', page_html, flags=re.IGNORECASE)
    links: list[str] = []
    seen: set[str] = set()

    for href in hrefs:
        abs_url = urljoin(base_url, href.split("#", 1)[0])
        parsed = urlparse(abs_url)

        if parsed.scheme not in {"http", "https"}:
            continue
        if "sfu.ca" not in parsed.netloc:
            continue

        path = parsed.path.lower()
        if "/students/calendar/" not in path:
            continue
        if "/courses/" not in path:
            continue
        if not path.endswith(".html"):
            continue
        if path.endswith("/courses.html"):
            continue

        if abs_url not in seen:
            seen.add(abs_url)
            links.append(abs_url)

    return links


def subject_from_url(url: str) -> str:
    name = Path(urlparse(url).path).stem
    return re.sub(r"[^a-zA-Z]", "", name).upper()[:6]


def normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"\u00a0", " ", text)
    text = re.sub(r"[\t\r]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def html_to_lines(page_html: str) -> list[str]:
    cleaned = re.sub(r"(?is)<script.*?>.*?</script>", " ", page_html)
    cleaned = re.sub(r"(?is)<style.*?>.*?</style>", " ", cleaned)
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</p>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</h[1-6]>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</li>", "\n", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)

    lines: list[str] = []
    for raw_line in cleaned.splitlines():
        line = normalize_text(raw_line)
        if line:
            lines.append(line)
    return lines


def parse_course_line(line: str) -> tuple[str, str, str] | None:
    match = COURSE_CODE_RE.search(line)
    if not match:
        return None

    subject = match.group(1).upper().strip()
    number = match.group(2).upper().strip()

    trailing = line[match.end() :].strip()
    trailing = re.sub(r"^\([^)]*\)\s*", "", trailing)  # remove credit units like (3)
    trailing = re.sub(r"^[-:–]+\s*", "", trailing)
    trailing = normalize_text(trailing)

    # Ignore lines that likely aren't title lines.
    if not trailing:
        return None
    lowered = trailing.lower()
    if lowered.startswith(("prerequisite", "corequisite", "equivalent", "students with")):
        return None
    if len(trailing) < 3:
        return None

    title = trailing[:180]
    return subject, number, title


def extract_courses_from_page(page_html: str, source_url: str, fallback_subject: str) -> list[CourseRow]:
    lines = html_to_lines(page_html)
    rows: list[CourseRow] = []
    seen_codes: set[str] = set()

    for line in lines:
        parsed = parse_course_line(line)
        if not parsed:
            continue

        subject, number, title = parsed
        if subject in {"SFU", "URL", "HTTP", "WWW"}:
            continue

        # If a parser glitch captures obvious non-course subject, fallback to URL subject.
        if len(subject) < 2 or len(subject) > 6:
            subject = fallback_subject

        code = f"{subject} {number}"
        if code in seen_codes:
            continue

        seen_codes.add(code)
        rows.append(
            CourseRow(
                subject=subject,
                number=number,
                code=code,
                title=title,
                source_url=source_url,
            )
        )

    return rows


def write_master_csv(out_csv: Path, rows: list[CourseRow]) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    rows_sorted = sorted(rows, key=lambda r: (r.subject, r.number, r.title.lower()))

    with out_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["subject", "number", "code", "title", "source_url"],
        )
        writer.writeheader()
        for row in rows_sorted:
            writer.writerow(
                {
                    "subject": row.subject,
                    "number": row.number,
                    "code": row.code,
                    "title": row.title,
                    "source_url": row.source_url,
                }
            )


def build_master_list(timeout: float) -> tuple[list[CourseRow], list[str], list[str]]:
    department_pages: list[str] = []
    errors: list[str] = []

    for term_url in TERM_INDEX_URLS:
        try:
            page_html = get_html(term_url, timeout=timeout)
            links = extract_links(page_html, term_url)
            department_pages.extend(links)
            print(f"[term] {term_url} -> {len(links)} department pages")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Failed term index {term_url}: {exc}")

    dedup_department_pages = sorted(set(department_pages))
    print(f"Discovered {len(dedup_department_pages)} unique department pages")

    courses_by_code: dict[str, CourseRow] = {}

    for idx, dept_url in enumerate(dedup_department_pages, start=1):
        try:
            page_html = get_html(dept_url, timeout=timeout)
            fallback_subject = subject_from_url(dept_url)
            extracted = extract_courses_from_page(page_html, dept_url, fallback_subject)

            for row in extracted:
                # Keep first seen source URL for each code.
                courses_by_code.setdefault(row.code, row)

            if idx % 25 == 0 or idx == len(dedup_department_pages):
                print(
                    f"[dept] {idx}/{len(dedup_department_pages)} pages processed | "
                    f"unique courses={len(courses_by_code)}"
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Failed department page {dept_url}: {exc}")

    return list(courses_by_code.values()), dedup_department_pages, errors


def main() -> int:
    args = parse_args()
    out_csv = Path(args.out_csv).expanduser().resolve()

    courses, department_pages, errors = build_master_list(timeout=args.timeout)

    write_master_csv(out_csv, courses)

    print(f"Saved master course list: {out_csv}")
    print(f"Total unique courses: {len(courses)}")
    print(f"Department pages crawled: {len(department_pages)}")

    if errors:
        print("\nCompleted with warnings:")
        for msg in errors:
            print(f"- {msg}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
