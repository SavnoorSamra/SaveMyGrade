#!/usr/bin/env python3
"""Train a difficulty risk forecast model from RateMyProfessor time-series data.

This script builds a term-level forecasting dataset from professor review files and trains
a multi-class classifier that predicts whether a class is likely to become:
  - easier
  - stable
  - harder
in the next term.

Modeling notes:
- Uses only historical information available at prediction time.
- Uses a chronological train/test split (time-aware; no leakage).
- Filters to official SFU catalog course codes by default.
- Applies minimum review/term thresholds for reliability.
"""

from __future__ import annotations

import argparse
import csv
import json
import pickle
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import numpy as np
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
except ModuleNotFoundError as exc:
    raise SystemExit(
        f"Missing dependency: {exc.name}\n"
        "Install backend dependencies with:\n"
        "  python3 -m pip install -r backend/requirements.txt"
    ) from exc


LABELS = ("easier", "stable", "harder")


@dataclass
class TermAggregate:
    department: str
    course_code: str
    term_index: int
    term_label: str
    season: str
    season_id: int
    n_reviews: int
    avg_difficulty: float
    avg_helpful: float | None
    avg_clarity: float | None
    avg_prof_rating: float | None
    avg_prof_difficulty: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root",
        default="backend/data/professor_reviews_by_department",
        help="Root folder containing per-department professor review files",
    )
    parser.add_argument(
        "--catalog-csv",
        default="backend/data/sfu_courses_2025_2026.csv",
        help="Official catalog CSV used to filter valid SFU course codes",
    )
    parser.add_argument(
        "--min-total-reviews",
        type=int,
        default=30,
        help="Minimum total reviews per course across all terms",
    )
    parser.add_argument(
        "--min-terms",
        type=int,
        default=4,
        help="Minimum number of observed terms per course",
    )
    parser.add_argument(
        "--min-reviews-per-term",
        type=int,
        default=2,
        help="Minimum reviews required in current and target terms",
    )
    parser.add_argument(
        "--delta-threshold",
        type=float,
        default=0.35,
        help="Difficulty change threshold for easier/harder labels",
    )
    parser.add_argument(
        "--history-window",
        type=int,
        default=3,
        help="Number of recent terms used for features",
    )
    parser.add_argument(
        "--test-fraction",
        type=float,
        default=0.2,
        help="Fraction of latest terms reserved for test set",
    )
    parser.add_argument(
        "--model-out",
        default="backend/models/difficulty_risk/model.pkl",
        help="Output path for trained model artifact",
    )
    parser.add_argument(
        "--report-out",
        default="backend/models/difficulty_risk/training_report.json",
        help="Output path for training metrics/config report",
    )
    parser.add_argument(
        "--forecast-out",
        default="backend/models/difficulty_risk/latest_forecasts.csv",
        help="Output CSV with latest per-course risk forecasts",
    )
    return parser.parse_args()


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def to_float(value: Any) -> float | None:
    text = clean_text(value)
    if not text or text.lower() in {"none", "nan", "n/a", "-1"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_course_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean_text(value).upper())


def is_likely_course_code(value: str) -> bool:
    # Ex: CMPT120, STAT203, EDUC388
    return bool(re.fullmatch(r"[A-Z]{2,}\d{2,4}[A-Z]?", value))


def parse_rating_date(value: str) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    # Common format: "2025-05-15 18:09:42 +0000 UTC"
    if text.endswith(" UTC"):
        text = text[:-4]
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def term_from_date(dt: datetime) -> tuple[int, str, str]:
    year = dt.year
    month = dt.month
    if 1 <= month <= 4:
        season_id, season = 1, "spring"
    elif 5 <= month <= 8:
        season_id, season = 2, "summer"
    else:
        season_id, season = 3, "fall"
    term_index = year * 10 + season_id
    term_label = f"{year}-{season}"
    return term_index, term_label, season


def parse_professor_file(path: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
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
        if not lines[i].startswith("--- Rating #"):
            i += 1
            continue

        i += 1
        rating: dict[str, str] = {}
        while i < len(lines) and not lines[i].startswith("--- Rating #"):
            current = lines[i]
            if current.startswith("Comment:"):
                i += 1
                comment_lines: list[str] = []
                while i < len(lines) and not lines[i].startswith("--- Rating #"):
                    comment_lines.append(lines[i])
                    i += 1
                rating["Comment"] = clean_text(" ".join(comment_lines))
                continue
            if ":" in current:
                key, value = current.split(":", 1)
                rating[key.strip()] = value.strip()
            i += 1
        ratings.append(rating)

    return metadata, ratings


def load_catalog_codes(catalog_csv: Path) -> set[str]:
    if not catalog_csv.exists():
        return set()

    codes: set[str] = set()
    with catalog_csv.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            raw_code = normalize_course_code(row.get("code", ""))
            if raw_code:
                codes.add(raw_code)
            subj = clean_text(row.get("subject", "")).upper()
            num = clean_text(row.get("number", "")).upper()
            combined = normalize_course_code(f"{subj}{num}")
            if combined:
                codes.add(combined)
    return codes


def build_term_aggregates(data_root: Path, catalog_codes: set[str]) -> list[TermAggregate]:
    bucket: dict[tuple[str, str, int], dict[str, Any]] = defaultdict(
        lambda: {
            "term_label": "",
            "season": "",
            "n_reviews": 0,
            "difficulty_sum": 0.0,
            "helpful_sum": 0.0,
            "helpful_n": 0,
            "clarity_sum": 0.0,
            "clarity_n": 0,
            "prof_rating_sum": 0.0,
            "prof_rating_n": 0,
            "prof_difficulty_sum": 0.0,
            "prof_difficulty_n": 0,
        }
    )

    files = sorted(data_root.glob("*/*.txt"))
    for path in files:
        metadata, ratings = parse_professor_file(path)
        department = clean_text(metadata.get("Department (CSV)", path.parent.name)) or path.parent.name
        prof_avg_rating = to_float(metadata.get("Avg Rating"))
        prof_avg_difficulty = to_float(metadata.get("Avg Difficulty"))

        for rating in ratings:
            difficulty = to_float(rating.get("Difficulty Rating"))
            if difficulty is None:
                continue

            course_code = normalize_course_code(rating.get("Class", ""))
            if not is_likely_course_code(course_code):
                continue
            if catalog_codes and course_code not in catalog_codes:
                continue

            dt = parse_rating_date(rating.get("Date", ""))
            if not dt:
                continue
            term_index, term_label, season = term_from_date(dt)
            season_id = term_index % 10

            key = (department, course_code, term_index)
            agg = bucket[key]
            agg["term_label"] = term_label
            agg["season"] = season
            agg["season_id"] = season_id
            agg["n_reviews"] += 1
            agg["difficulty_sum"] += difficulty

            helpful = to_float(rating.get("Helpful Rating"))
            if helpful is not None:
                agg["helpful_sum"] += helpful
                agg["helpful_n"] += 1

            clarity = to_float(rating.get("Clarity Rating"))
            if clarity is not None:
                agg["clarity_sum"] += clarity
                agg["clarity_n"] += 1

            if prof_avg_rating is not None:
                agg["prof_rating_sum"] += prof_avg_rating
                agg["prof_rating_n"] += 1
            if prof_avg_difficulty is not None:
                agg["prof_difficulty_sum"] += prof_avg_difficulty
                agg["prof_difficulty_n"] += 1

    out: list[TermAggregate] = []
    for (department, course_code, term_index), agg in bucket.items():
        n = agg["n_reviews"]
        if n <= 0:
            continue
        out.append(
            TermAggregate(
                department=department,
                course_code=course_code,
                term_index=term_index,
                term_label=agg["term_label"],
                season=agg["season"],
                season_id=int(agg["season_id"]),
                n_reviews=n,
                avg_difficulty=agg["difficulty_sum"] / n,
                avg_helpful=(agg["helpful_sum"] / agg["helpful_n"]) if agg["helpful_n"] else None,
                avg_clarity=(agg["clarity_sum"] / agg["clarity_n"]) if agg["clarity_n"] else None,
                avg_prof_rating=(agg["prof_rating_sum"] / agg["prof_rating_n"])
                if agg["prof_rating_n"]
                else None,
                avg_prof_difficulty=(agg["prof_difficulty_sum"] / agg["prof_difficulty_n"])
                if agg["prof_difficulty_n"]
                else None,
            )
        )

    return out


def safe_mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def safe_std(values: list[float]) -> float:
    return float(np.std(values)) if len(values) >= 2 else 0.0


def safe_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    return float(np.polyfit(x, y, 1)[0])


def label_from_delta(delta: float, threshold: float) -> str:
    if delta >= threshold:
        return "harder"
    if delta <= -threshold:
        return "easier"
    return "stable"


def build_samples(
    term_rows: list[TermAggregate],
    min_total_reviews: int,
    min_terms: int,
    min_reviews_per_term: int,
    delta_threshold: float,
    history_window: int,
) -> tuple[pd.DataFrame, dict[tuple[str, str], list[TermAggregate]]]:
    by_course: dict[tuple[str, str], list[TermAggregate]] = defaultdict(list)
    for row in term_rows:
        by_course[(row.department, row.course_code)].append(row)

    samples: list[dict[str, Any]] = []
    eligible_series: dict[tuple[str, str], list[TermAggregate]] = {}

    for key, series in by_course.items():
        series = sorted(series, key=lambda r: r.term_index)
        total_reviews = sum(r.n_reviews for r in series)

        if total_reviews < min_total_reviews:
            continue
        if len(series) < min_terms:
            continue

        eligible_series[key] = series

        for i in range(history_window - 1, len(series) - 1):
            current = series[i]
            target = series[i + 1]
            if current.n_reviews < min_reviews_per_term or target.n_reviews < min_reviews_per_term:
                continue

            start = i - history_window + 1
            hist = series[start : i + 1]
            diffs = [h.avg_difficulty for h in hist]
            helpfuls = [h.avg_helpful for h in hist if h.avg_helpful is not None]
            clarities = [h.avg_clarity for h in hist if h.avg_clarity is not None]
            counts = [h.n_reviews for h in hist]

            delta_next = target.avg_difficulty - current.avg_difficulty
            label = label_from_delta(delta_next, delta_threshold)

            samples.append(
                {
                    "department": current.department,
                    "course_code": current.course_code,
                    "season": current.season,
                    "season_id": current.season_id,
                    "term_index": current.term_index,
                    "target_term_index": target.term_index,
                    "current_difficulty": current.avg_difficulty,
                    "prev_delta": current.avg_difficulty - hist[-2].avg_difficulty if len(hist) >= 2 else 0.0,
                    "abs_prev_delta": abs(current.avg_difficulty - hist[-2].avg_difficulty) if len(hist) >= 2 else 0.0,
                    "rolling_mean_3": safe_mean(diffs),
                    "rolling_std_3": safe_std(diffs),
                    "rolling_slope_3": safe_slope(diffs),
                    "mean_reversion_gap": current.avg_difficulty - safe_mean(diffs),
                    "reviews_current": float(current.n_reviews),
                    "reviews_hist_sum": float(sum(counts)),
                    "reviews_trend_3": safe_slope([float(c) for c in counts]),
                    "helpful_hist_mean": safe_mean(helpfuls),
                    "clarity_hist_mean": safe_mean(clarities),
                    "prof_avg_rating": float(current.avg_prof_rating or 0.0),
                    "prof_avg_difficulty": float(current.avg_prof_difficulty or 0.0),
                    "delta_next": float(delta_next),
                    "label": label,
                }
            )

    df = pd.DataFrame(samples)
    return df, eligible_series


def time_split(df: pd.DataFrame, test_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    unique_terms = sorted(df["target_term_index"].unique().tolist())
    if len(unique_terms) < 4:
        raise SystemExit("Not enough distinct target terms for a time-aware split.")

    split_idx = max(1, int(round(len(unique_terms) * (1.0 - test_fraction))))
    split_idx = min(split_idx, len(unique_terms) - 1)
    cutoff = unique_terms[split_idx - 1]

    train_df = df[df["target_term_index"] <= cutoff].copy()
    test_df = df[df["target_term_index"] > cutoff].copy()
    if train_df.empty or test_df.empty:
        raise SystemExit("Time split produced empty train/test partition.")
    return train_df, test_df


def time_validation_split(train_df: pd.DataFrame, val_fraction: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    unique_terms = sorted(train_df["target_term_index"].unique().tolist())
    if len(unique_terms) < 4:
        raise SystemExit("Not enough train terms for validation split.")
    split_idx = max(1, int(round(len(unique_terms) * (1.0 - val_fraction))))
    split_idx = min(split_idx, len(unique_terms) - 1)
    cutoff = unique_terms[split_idx - 1]
    fit_df = train_df[train_df["target_term_index"] <= cutoff].copy()
    val_df = train_df[train_df["target_term_index"] > cutoff].copy()
    if fit_df.empty or val_df.empty:
        raise SystemExit("Validation split produced empty fit/validation partition.")
    return fit_df, val_df


def candidate_model_specs() -> dict[str, Any]:
    return {
        "logreg_balanced": LogisticRegression(
            max_iter=4000,
            class_weight="balanced",
            solver="lbfgs",
            C=1.0,
        ),
        "logreg_balanced_low_c": LogisticRegression(
            max_iter=4000,
            class_weight="balanced",
            solver="lbfgs",
            C=0.5,
        ),
        "rf_balanced": RandomForestClassifier(
            n_estimators=500,
            max_depth=14,
            min_samples_leaf=3,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        ),
        "extra_trees_balanced": ExtraTreesClassifier(
            n_estimators=700,
            max_depth=16,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        ),
    }


def fit_pipeline(
    estimator: Any,
    fit_df: pd.DataFrame,
    feature_cols_num: list[str],
    feature_cols_cat: list[str],
) -> Pipeline:
    pre = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), feature_cols_num),
            ("cat", OneHotEncoder(handle_unknown="ignore"), feature_cols_cat),
        ]
    )
    pipe = Pipeline([("preprocess", pre), ("clf", estimator)])
    pipe.fit(fit_df[feature_cols_num + feature_cols_cat], fit_df["label"])
    return pipe


def evaluate_model(
    model: Pipeline,
    eval_df: pd.DataFrame,
    feature_cols_num: list[str],
    feature_cols_cat: list[str],
) -> dict[str, Any]:
    x_eval = eval_df[feature_cols_num + feature_cols_cat]
    y_true = eval_df["label"].to_numpy()
    y_pred = model.predict(x_eval)

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "classification_report": classification_report(
            y_true,
            y_pred,
            labels=list(LABELS),
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=list(LABELS)).tolist(),
        "labels": list(LABELS),
    }


def pick_best_model(
    train_df: pd.DataFrame,
    feature_cols_num: list[str],
    feature_cols_cat: list[str],
) -> tuple[str, Pipeline, dict[str, Any], list[dict[str, Any]]]:
    fit_df, val_df = time_validation_split(train_df, val_fraction=0.2)
    candidates = candidate_model_specs()

    best_name = ""
    best_model: Pipeline | None = None
    best_metrics: dict[str, Any] | None = None
    leaderboard: list[dict[str, Any]] = []

    for name, estimator in candidates.items():
        model = fit_pipeline(estimator, fit_df, feature_cols_num, feature_cols_cat)
        metrics = evaluate_model(model, val_df, feature_cols_num, feature_cols_cat)
        stable_f1 = metrics["classification_report"].get("stable", {}).get("f1-score", 0.0)
        score = metrics["balanced_accuracy"] + (0.05 * stable_f1)
        leaderboard.append(
            {
                "model_name": name,
                "balanced_accuracy": metrics["balanced_accuracy"],
                "accuracy": metrics["accuracy"],
                "stable_f1": stable_f1,
                "selection_score": score,
            }
        )

        if best_metrics is None or score > (
            best_metrics["balanced_accuracy"]
            + 0.05 * best_metrics["classification_report"].get("stable", {}).get("f1-score", 0.0)
        ):
            best_name = name
            best_model = model
            best_metrics = metrics

    if best_model is None or best_metrics is None:
        raise SystemExit("Model selection failed: no candidates were trained.")

    # Refit the selected estimator on the full train set.
    selected_estimator = candidate_model_specs()[best_name]
    final_model = fit_pipeline(selected_estimator, train_df, feature_cols_num, feature_cols_cat)
    leaderboard.sort(key=lambda row: row["selection_score"], reverse=True)
    return best_name, final_model, best_metrics, leaderboard


def forecast_latest(
    model: Pipeline,
    series_map: dict[tuple[str, str], list[TermAggregate]],
    feature_cols_num: list[str],
    feature_cols_cat: list[str],
    history_window: int,
    min_reviews_per_term: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for (department, course_code), series in sorted(series_map.items()):
        series = sorted(series, key=lambda r: r.term_index)
        if len(series) < history_window:
            continue

        current = series[-1]
        if current.n_reviews < min_reviews_per_term:
            continue

        hist = series[-history_window:]
        diffs = [h.avg_difficulty for h in hist]
        helpfuls = [h.avg_helpful for h in hist if h.avg_helpful is not None]
        clarities = [h.avg_clarity for h in hist if h.avg_clarity is not None]
        counts = [h.n_reviews for h in hist]

        feat_row = {
            "department": department,
            "course_code": course_code,
            "season": current.season,
            "season_id": current.season_id,
            "term_index": current.term_index,
            "target_term_index": current.term_index + 1,
            "current_difficulty": current.avg_difficulty,
            "prev_delta": current.avg_difficulty - hist[-2].avg_difficulty if len(hist) >= 2 else 0.0,
            "abs_prev_delta": abs(current.avg_difficulty - hist[-2].avg_difficulty) if len(hist) >= 2 else 0.0,
            "rolling_mean_3": safe_mean(diffs),
            "rolling_std_3": safe_std(diffs),
            "rolling_slope_3": safe_slope(diffs),
            "mean_reversion_gap": current.avg_difficulty - safe_mean(diffs),
            "reviews_current": float(current.n_reviews),
            "reviews_hist_sum": float(sum(counts)),
            "reviews_trend_3": safe_slope([float(c) for c in counts]),
            "helpful_hist_mean": safe_mean(helpfuls),
            "clarity_hist_mean": safe_mean(clarities),
            "prof_avg_rating": float(current.avg_prof_rating or 0.0),
            "prof_avg_difficulty": float(current.avg_prof_difficulty or 0.0),
            "current_term": current.term_label,
        }

        x = pd.DataFrame([feat_row])[feature_cols_num + feature_cols_cat]
        probs = model.predict_proba(x)[0]
        classes = model.classes_
        proba_map = {cls: float(prob) for cls, prob in zip(classes, probs)}

        predicted = model.predict(x)[0]
        rows.append(
            {
                "department": department,
                "course_code": course_code,
                "current_term": current.term_label,
                "current_avg_difficulty": round(current.avg_difficulty, 3),
                "current_reviews": int(current.n_reviews),
                "risk_label": predicted,
                "risk_confidence": round(proba_map.get(predicted, 0.0), 4),
                "prob_easier": round(proba_map.get("easier", 0.0), 4),
                "prob_stable": round(proba_map.get("stable", 0.0), 4),
                "prob_harder": round(proba_map.get("harder", 0.0), 4),
                "harder_minus_easier": round(
                    proba_map.get("harder", 0.0) - proba_map.get("easier", 0.0), 4
                ),
            }
        )

    forecast_df = pd.DataFrame(rows)
    if not forecast_df.empty:
        forecast_df = forecast_df.sort_values(
            by=["prob_harder", "risk_confidence", "current_reviews"],
            ascending=[False, False, False],
        )
    return forecast_df


def main() -> int:
    args = parse_args()
    data_root = Path(args.data_root).expanduser().resolve()
    catalog_csv = Path(args.catalog_csv).expanduser().resolve()
    model_out = Path(args.model_out).expanduser().resolve()
    report_out = Path(args.report_out).expanduser().resolve()
    forecast_out = Path(args.forecast_out).expanduser().resolve()

    if not data_root.exists():
        raise SystemExit(f"Data root not found: {data_root}")

    catalog_codes = load_catalog_codes(catalog_csv)
    term_rows = build_term_aggregates(data_root, catalog_codes=catalog_codes)
    if not term_rows:
        raise SystemExit("No term-level rows found from input data.")

    dataset, series_map = build_samples(
        term_rows=term_rows,
        min_total_reviews=args.min_total_reviews,
        min_terms=args.min_terms,
        min_reviews_per_term=args.min_reviews_per_term,
        delta_threshold=args.delta_threshold,
        history_window=args.history_window,
    )
    if dataset.empty:
        raise SystemExit("No eligible training samples after thresholding/filtering.")

    train_df, test_df = time_split(dataset, test_fraction=args.test_fraction)

    feature_cols_num = [
        "season_id",
        "current_difficulty",
        "prev_delta",
        "abs_prev_delta",
        "rolling_mean_3",
        "rolling_std_3",
        "rolling_slope_3",
        "mean_reversion_gap",
        "reviews_current",
        "reviews_hist_sum",
        "reviews_trend_3",
        "helpful_hist_mean",
        "clarity_hist_mean",
        "prof_avg_rating",
        "prof_avg_difficulty",
    ]
    feature_cols_cat = ["season"]

    selected_model_name, model, selection_metrics, selection_leaderboard = pick_best_model(
        train_df, feature_cols_num, feature_cols_cat
    )
    metrics = evaluate_model(model, test_df, feature_cols_num, feature_cols_cat)

    model_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    forecast_out.parent.mkdir(parents=True, exist_ok=True)

    artifact = {
        "model": model,
        "feature_cols_num": feature_cols_num,
        "feature_cols_cat": feature_cols_cat,
        "labels": list(LABELS),
        "config": {
            "min_total_reviews": args.min_total_reviews,
            "min_terms": args.min_terms,
            "min_reviews_per_term": args.min_reviews_per_term,
            "delta_threshold": args.delta_threshold,
            "history_window": args.history_window,
            "test_fraction": args.test_fraction,
        },
    }
    with model_out.open("wb") as fh:
        pickle.dump(artifact, fh)

    report = {
        "dataset": {
            "num_term_rows": len(term_rows),
            "num_samples_total": int(len(dataset)),
            "num_samples_train": int(len(train_df)),
            "num_samples_test": int(len(test_df)),
            "label_distribution_total": dataset["label"].value_counts().to_dict(),
            "label_distribution_train": train_df["label"].value_counts().to_dict(),
            "label_distribution_test": test_df["label"].value_counts().to_dict(),
            "unique_courses_eligible": len(series_map),
            "catalog_filter_enabled": bool(catalog_codes),
            "catalog_codes_count": len(catalog_codes),
        },
        "metrics": metrics,
        "model_selection": {
            "selected_model": selected_model_name,
            "validation_metrics_selected_model": selection_metrics,
            "leaderboard": selection_leaderboard,
        },
        "config": artifact["config"],
        "paths": {
            "data_root": str(data_root),
            "catalog_csv": str(catalog_csv),
            "model_out": str(model_out),
            "forecast_out": str(forecast_out),
        },
    }
    report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    forecasts = forecast_latest(
        model=model,
        series_map=series_map,
        feature_cols_num=feature_cols_num,
        feature_cols_cat=feature_cols_cat,
        history_window=args.history_window,
        min_reviews_per_term=args.min_reviews_per_term,
    )
    forecasts.to_csv(forecast_out, index=False)

    print(f"Training samples: {len(dataset)}")
    print(f"Train/Test: {len(train_df)}/{len(test_df)}")
    print(
        "Metrics: "
        f"accuracy={metrics['accuracy']:.3f}, "
        f"balanced_accuracy={metrics['balanced_accuracy']:.3f}"
    )
    print(
        "Selected model: "
        f"{selected_model_name} "
        f"(val_bal_acc={selection_metrics['balanced_accuracy']:.3f}, "
        f"val_acc={selection_metrics['accuracy']:.3f})"
    )
    print(f"Saved model: {model_out}")
    print(f"Saved report: {report_out}")
    print(f"Saved forecasts: {forecast_out} ({len(forecasts)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
