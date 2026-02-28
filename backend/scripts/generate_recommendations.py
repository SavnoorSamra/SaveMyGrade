#!/usr/bin/env python3
"""Mock recommendation generator.

Reads JSON from stdin with keys:
- university
- query

Prints JSON to stdout in the shape:
{ "results": [ ... ] }
"""

from __future__ import annotations

import json
import sys


def load_input() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def build_results(university: str, query: str) -> list[dict]:
    q = query.lower()

    suggestions = [
        {
            "course_code": "CMPT 120",
            "title": "Introduction to Computing Science and Programming I",
            "avg_gpa": 3.2,
            "difficulty": 2.3,
            "professor": "J. Lee",
            "prof_rating": 4.2,
            "reason": "Consistently strong student feedback and manageable assignments."
        },
        {
            "course_code": "EDUC 100",
            "title": "Selected Questions and Issues in Education",
            "avg_gpa": 3.4,
            "difficulty": 2.1,
            "professor": "A. Singh",
            "prof_rating": 4.4,
            "reason": "Reading-heavy but assessment style is usually straightforward."
        },
        {
            "course_code": "BISC 101",
            "title": "General Biology",
            "avg_gpa": 3.0,
            "difficulty": 2.6,
            "professor": "M. Chen",
            "prof_rating": 4.0,
            "reason": "Common elective with broad support resources and past exam patterns."
        }
    ]

    if "cmpt" in q or "comput" in q:
        return [suggestions[0], suggestions[1]]
    if "science" in q or "bio" in q:
        return [suggestions[2], suggestions[0]]
    return suggestions


def main() -> int:
    payload = load_input()
    university = payload.get("university", "Unknown University")
    query = payload.get("query", "")

    output = {
        "university": university,
        "query": query,
        "results": build_results(university, query)
    }

    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
