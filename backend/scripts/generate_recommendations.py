#!/usr/bin/env python3
"""Generate course recommendations from scraped professor review files.

Input JSON on stdin keys:
- university: str (optional)
- query: str (optional)
- department: str (optional)
- professor: str (optional)
- max_results: int (optional, default 10)

Output JSON:
{
  "results": [ ... ],
  "meta": { ... }
}
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "professor_reviews_by_department"
CATALOG_PATH_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "backend" / "data" / "sfu_courses_2025_2026.csv",
    Path(__file__).resolve().parent.parent / "data" / "sfu_courses_2025_2026.csv",
]
DEFAULT_MAX_RESULTS = 10

EASY_TERMS = {
    "easy",
    "manageable",
    "straightforward",
    "fair",
    "doable",
    "clear",
    "helpful",
    "recommend",
    "interesting",
}

HARD_TERMS = {
    "hard",
    "difficult",
    "overwhelming",
    "confusing",
    "heavy",
    "memorization",
    "unclear",
    "rude",
    "unreasonable",
}


@dataclass
class ClassProfile:
    department: str
    professor: str
    course_code: str
    prof_avg_rating: float | None
    prof_avg_difficulty: float | None
    ratings_count: int = 0
    difficulty_sum: float = 0.0
    helpful_sum: float = 0.0
    clarity_sum: float = 0.0
    comments: list[str] = field(default_factory=list)

    def add_rating(self, rating: dict[str, Any]) -> None:
        self.ratings_count += 1

        difficulty = to_float(rating.get("Difficulty Rating"))
        helpful = to_float(rating.get("Helpful Rating"))
        clarity = to_float(rating.get("Clarity Rating"))

        if difficulty is not None:
            self.difficulty_sum += difficulty
        if helpful is not None:
            self.helpful_sum += helpful
        if clarity is not None:
            self.clarity_sum += clarity

        comment = (rating.get("Comment") or "").strip()
        if comment and len(self.comments) < 8:
            self.comments.append(comment)

    @property
    def avg_class_difficulty(self) -> float | None:
        if self.ratings_count == 0:
            return self.prof_avg_difficulty
        return self.difficulty_sum / self.ratings_count

    @property
    def avg_helpful(self) -> float | None:
        if self.ratings_count == 0:
            return None
        return self.helpful_sum / self.ratings_count

    @property
    def avg_clarity(self) -> float | None:
        if self.ratings_count == 0:
            return None
        return self.clarity_sum / self.ratings_count


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "n/a", "nan", "-1"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_input() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_for_match(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def normalize_course_code(value: str) -> str:
    # Normalize "CMPT120", "CMPT 120", "cmpt-120" -> "CMPT120"
    text = re.sub(r"[^A-Za-z0-9]", "", (value or "").upper())
    return text


def resolve_catalog_csv_path() -> Path | None:
    env_path = (os.getenv("SFU_CATALOG_CSV") or "").strip()
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.exists():
            return p
        return None

    for p in CATALOG_PATH_CANDIDATES:
        if p.exists():
            return p
    return None


def load_catalog_course_codes() -> tuple[set[str], Path | None]:
    csv_path = resolve_catalog_csv_path()
    if not csv_path:
        return set(), None

    codes: set[str] = set()
    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if not isinstance(row, dict):
                continue
            code_raw = clean_text(str(row.get("code", "")))
            subject = clean_text(str(row.get("subject", ""))).upper()
            number = clean_text(str(row.get("number", ""))).upper()

            if code_raw:
                normalized = normalize_course_code(code_raw)
                if normalized:
                    codes.add(normalized)

            combined = normalize_course_code(f"{subject}{number}")
            if combined:
                codes.add(combined)

    return codes, csv_path


def parse_professor_file(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    metadata: dict[str, str] = {}
    ratings: list[dict[str, str]] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- Rating #"):
            break
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
        i += 1

    while i < len(lines):
        line = lines[i]
        if not line.startswith("--- Rating #"):
            i += 1
            continue

        rating: dict[str, str] = {}
        i += 1

        while i < len(lines) and not lines[i].startswith("--- Rating #"):
            current = lines[i]
            if current.startswith("Comment:"):
                i += 1
                comment_lines: list[str] = []
                while i < len(lines) and not lines[i].startswith("--- Rating #"):
                    comment_lines.append(lines[i])
                    i += 1
                rating["Comment"] = clean_text("\n".join(comment_lines))
                continue

            if ":" in current:
                key, value = current.split(":", 1)
                rating[key.strip()] = value.strip()
            i += 1

        ratings.append(rating)

    return {"metadata": metadata, "ratings": ratings}


def iter_professor_files(data_root: Path, department: str | None, professor: str | None) -> list[Path]:
    if not data_root.exists():
        return []

    dept_filter = normalize_for_match(department or "")
    prof_filter = normalize_for_match(professor or "")

    available_departments = [p for p in data_root.iterdir() if p.is_dir()]
    if dept_filter:
        available_departments = [
            p for p in available_departments if normalize_for_match(p.name) == dept_filter
        ]

    files: list[Path] = []
    for dept_dir in sorted(available_departments):
        for txt_path in sorted(dept_dir.glob("*.txt")):
            if prof_filter:
                info = parse_filename_professor(txt_path)
                combined = normalize_for_match(f"{info['professor']} {info['legacy_id']}")
                if prof_filter not in combined:
                    continue
            files.append(txt_path)

    return files


def parse_filename_professor(path: Path) -> dict[str, str]:
    stem = path.stem
    parts = stem.split("_")
    if len(parts) < 3:
        return {"professor": stem.replace("_", " "), "legacy_id": ""}

    legacy_id = parts[-1]
    last_name = parts[0].replace("_", " ").strip()
    first_name = " ".join(p for p in parts[1:-1] if p).replace("_", " ").strip()
    professor_name = clean_text(f"{first_name} {last_name}")
    return {"professor": professor_name, "legacy_id": legacy_id}


def tokenize_query(query: str) -> set[str]:
    return {tok for tok in re.split(r"[^A-Za-z0-9]+", query.lower()) if tok}


def sentiment_score(comments: list[str]) -> float:
    if not comments:
        return 0.0

    text = " ".join(comments).lower()
    pos_hits = sum(text.count(term) for term in EASY_TERMS)
    neg_hits = sum(text.count(term) for term in HARD_TERMS)

    return max(-1.0, min(1.0, (pos_hits - neg_hits) / max(1, pos_hits + neg_hits)))


def score_candidate(profile: ClassProfile, query_tokens: set[str]) -> tuple[float, dict[str, Any]]:
    prof_rating = profile.prof_avg_rating if profile.prof_avg_rating is not None else 3.0
    class_difficulty = profile.avg_class_difficulty if profile.avg_class_difficulty is not None else 3.0
    helpful = profile.avg_helpful if profile.avg_helpful is not None else 3.0
    clarity = profile.avg_clarity if profile.avg_clarity is not None else 3.0

    sentiment = sentiment_score(profile.comments)

    ease_score = (
        (prof_rating / 5.0) * 35
        + ((5.0 - class_difficulty) / 5.0) * 35
        + ((helpful + clarity) / 10.0) * 20
        + ((sentiment + 1.0) / 2.0) * 10
    )

    search_blob = " ".join(
        [
            profile.course_code.lower(),
            profile.department.lower(),
            profile.professor.lower(),
            " ".join(c.lower() for c in profile.comments[:3]),
        ]
    )

    query_bonus = sum(1 for token in query_tokens if token in search_blob)
    # Prefer recommendations backed by more student reports.
    review_penalty = 0.0
    if profile.ratings_count < 3:
        review_penalty = (3 - profile.ratings_count) * 6.0

    final_score = ease_score + min(15, query_bonus * 2.5) - review_penalty

    return final_score, {
        "ease_score": round(final_score, 2),
        "prof_rating": round(prof_rating, 2),
        "difficulty": round(class_difficulty, 2),
        "review_count": profile.ratings_count,
        "low_review_penalty": round(review_penalty, 2),
        "avg_helpful": round(helpful, 2),
        "avg_clarity": round(clarity, 2),
        "sentiment": round(sentiment, 2),
    }


def build_profiles(files: list[Path]) -> list[ClassProfile]:
    profiles: dict[tuple[str, str, str], ClassProfile] = {}

    for path in files:
        parsed = parse_professor_file(path)
        meta = parsed["metadata"]
        ratings = parsed["ratings"]

        department = clean_text(meta.get("Department (CSV)", path.parent.name)) or path.parent.name
        professor = clean_text(meta.get("Professor", parse_filename_professor(path)["professor"]))
        prof_avg_rating = to_float(meta.get("Avg Rating"))
        prof_avg_difficulty = to_float(meta.get("Avg Difficulty"))

        for rating in ratings:
            course_code = clean_text(rating.get("Class", ""))
            if not course_code:
                continue

            key = (department, course_code.upper(), professor)
            if key not in profiles:
                profiles[key] = ClassProfile(
                    department=department,
                    professor=professor,
                    course_code=course_code.upper(),
                    prof_avg_rating=prof_avg_rating,
                    prof_avg_difficulty=prof_avg_difficulty,
                )

            profiles[key].add_rating(rating)

    return list(profiles.values())


def filter_profiles_by_catalog(
    profiles: list[ClassProfile], catalog_codes: set[str]
) -> tuple[list[ClassProfile], int]:
    if not catalog_codes:
        return profiles, 0

    kept: list[ClassProfile] = []
    removed = 0
    for profile in profiles:
        code_normalized = normalize_course_code(profile.course_code)
        if code_normalized in catalog_codes:
            kept.append(profile)
        else:
            removed += 1
    return kept, removed


def summarize_candidate(profile: ClassProfile, score_info: dict[str, Any]) -> dict[str, Any]:
    comments = profile.comments[:3]
    return {
        "course_code": profile.course_code,
        "title": f"{profile.course_code} (from RateMyProfessor reviews)",
        "department": profile.department,
        "professor": profile.professor,
        "prof_rating": score_info["prof_rating"],
        "difficulty": score_info["difficulty"],
        "avg_gpa": None,
        "review_count": score_info["review_count"],
        "ease_score": score_info["ease_score"],
        "reason": (
            f"Based on {score_info['review_count']} class reviews with avg difficulty "
            f"{score_info['difficulty']} and professor rating {score_info['prof_rating']}."
        ),
        "sample_comments": comments,
    }


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None

    return None


def run_gemini_ranking(
    candidates: list[dict[str, Any]],
    query: str,
    department: str,
    professor: str,
    exclude_taken_codes: list[str],
    max_results: int,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    api_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return None, "missing_api_key"

    try:
        from google import genai
    except Exception:
        return None, "google_genai_not_installed"

    model = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip()

    prompt_payload = {
        "query": query,
        "department": department,
        "professor": professor,
        "exclude_taken_codes": exclude_taken_codes,
        "candidates": candidates[:25],
        "max_results": max_results,
    }

    prompt = (
        "You are ranking SFU class options for easiest high-grade outcomes based only on provided data. "
        "Return strict JSON with this schema: "
        "{\"results\":[{\"course_code\":str,\"department\":str,\"professor\":str,"
        "\"ease_score\":number,\"reason\":str}],\"summary\":str}. "
        "Do not invent fields. Prefer lower difficulty, higher professor ratings, and positive comments. "
        "IMPORTANT: Ignore review evidence for classes not in the official SFU 2025-2026 course catalog. "
        "Course code matching is space-insensitive (e.g., CMPT120 == CMPT 120). "
        "Strongly down-rank classes with fewer than 3 reviews unless there are no stronger alternatives. "
        "Never include courses in exclude_taken_codes.\n\n"
        f"Input: {json.dumps(prompt_payload, ensure_ascii=True)}"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
        text = getattr(response, "text", "") or ""
        parsed = extract_json_object(text)
        if not parsed:
            return None, "invalid_model_json"

        results = parsed.get("results")
        if not isinstance(results, list):
            return None, "missing_results"

        trimmed: list[dict[str, Any]] = []
        for item in results[:max_results]:
            if not isinstance(item, dict):
                continue
            if not item.get("course_code"):
                continue
            trimmed.append(item)

        if not trimmed:
            return None, "empty_model_results"

        return trimmed, None
    except Exception as exc:  # noqa: BLE001
        return None, f"gemini_error:{exc}"


def merge_gemini_results(
    gemini_results: list[dict[str, Any]],
    candidate_lookup: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for item in gemini_results:
        course_code = clean_text(str(item.get("course_code", ""))).upper()
        department = clean_text(str(item.get("department", "")))
        professor = clean_text(str(item.get("professor", "")))

        key = (
            normalize_for_match(department),
            normalize_course_code(course_code),
            normalize_for_match(professor),
        )
        base = candidate_lookup.get(key, {}).copy()

        if not base:
            base = {
                "course_code": course_code,
                "department": department,
                "professor": professor,
            }

        if "ease_score" in item:
            base["ease_score"] = item["ease_score"]
        if item.get("reason"):
            base["reason"] = item["reason"]

        base["source"] = "gemini"
        merged.append(base)

    return merged


def build_recommendations(payload: dict[str, Any]) -> dict[str, Any]:
    university = clean_text(str(payload.get("university", "Simon Fraser University")))
    query = clean_text(str(payload.get("query", "")))
    department = clean_text(str(payload.get("department", "")))
    professor = clean_text(str(payload.get("professor", "")))
    exclude_taken_raw = payload.get("exclude_taken_courses", [])
    if isinstance(exclude_taken_raw, list):
        exclude_taken_codes = [
            normalize_course_code(str(code))
            for code in exclude_taken_raw
            if normalize_course_code(str(code))
        ]
    else:
        exclude_taken_codes = []
    exclude_taken_set = set(exclude_taken_codes)

    max_results_raw = payload.get("max_results", DEFAULT_MAX_RESULTS)
    try:
        max_results = max(1, min(20, int(max_results_raw)))
    except (TypeError, ValueError):
        max_results = DEFAULT_MAX_RESULTS

    files = iter_professor_files(DATA_ROOT, department=department or None, professor=professor or None)
    profiles = build_profiles(files)
    catalog_codes, catalog_path = load_catalog_course_codes()
    if not catalog_codes:
        return {
            "university": university,
            "query": query,
            "results": [],
            "meta": {
                "department": department,
                "professor": professor,
                "matched_professor_files": len(files),
                "class_profiles": 0,
                "model_used": "heuristic",
                "catalog_csv_path": str(catalog_path) if catalog_path else None,
                "catalog_loaded": False,
                "catalog_filtered_out": 0,
                "note": "Catalog CSV not found/loaded. Refusing to return unverified course recommendations.",
            },
        }
    profiles, catalog_filtered_out = filter_profiles_by_catalog(profiles, catalog_codes)
    excluded_taken_count = 0
    if exclude_taken_set:
        before = len(profiles)
        profiles = [
            p for p in profiles if normalize_course_code(p.course_code) not in exclude_taken_set
        ]
        excluded_taken_count = before - len(profiles)

    if not profiles:
        return {
            "university": university,
            "query": query,
            "results": [],
            "meta": {
                "department": department,
                "professor": professor,
                "matched_professor_files": len(files),
                "class_profiles": 0,
                "model_used": "heuristic",
                "catalog_csv_path": str(catalog_path) if catalog_path else None,
                "catalog_loaded": bool(catalog_codes),
                "catalog_filtered_out": catalog_filtered_out,
                "excluded_taken_count": excluded_taken_count,
                "note": "No matching data found for provided filters.",
            },
        }

    query_tokens = tokenize_query(query)

    scored: list[tuple[float, dict[str, Any]]] = []
    for profile in profiles:
        score, info = score_candidate(profile, query_tokens)
        candidate = summarize_candidate(profile, info)
        scored.append((score, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_candidates = [item for _, item in scored[:40]]

    lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for candidate in top_candidates:
        key = (
            normalize_for_match(candidate.get("department", "")),
            normalize_course_code(str(candidate.get("course_code", ""))),
            normalize_for_match(candidate.get("professor", "")),
        )
        lookup[key] = candidate

    gemini_ranked, gemini_error = run_gemini_ranking(
        candidates=top_candidates,
        query=query,
        department=department,
        professor=professor,
        exclude_taken_codes=sorted(exclude_taken_set),
        max_results=max_results,
    )

    if gemini_ranked:
        results = merge_gemini_results(gemini_ranked, lookup)
        model_used = "gemini"
    else:
        results = [dict(item, source="heuristic") for item in top_candidates[:max_results]]
        model_used = "heuristic"

    return {
        "university": university,
        "query": query,
        "results": results[:max_results],
        "meta": {
            "department": department,
            "professor": professor,
            "matched_professor_files": len(files),
            "class_profiles": len(profiles),
            "model_used": model_used,
            "gemini_error": gemini_error,
            "catalog_csv_path": str(catalog_path) if catalog_path else None,
            "catalog_loaded": bool(catalog_codes),
            "catalog_filtered_out": catalog_filtered_out,
            "excluded_taken_count": excluded_taken_count,
        },
    }


def main() -> int:
    payload = load_input()
    output = build_recommendations(payload)
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
