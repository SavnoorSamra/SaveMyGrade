from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(__file__).resolve().parent / "data" / "professor_reviews_by_department"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(ROOT_DIR / ".env")

SCRIPT_PATH = Path(__file__).resolve().parent / "scripts" / "generate_recommendations.py"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5050"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() in {"1", "true", "yes"}


@app.get("/api/health")
def health() -> tuple[dict, int]:
    return {
        "status": "ok",
        "google_api_key_configured": bool(GOOGLE_API_KEY),
        "gemini_api_key_configured": bool(GEMINI_API_KEY),
        "any_gemini_key_configured": bool(GOOGLE_API_KEY or GEMINI_API_KEY),
    }, 200


def parse_professor_from_filename(path: Path) -> dict[str, str]:
    parts = path.stem.split("_")
    if len(parts) < 3:
        return {"name": path.stem.replace("_", " "), "legacy_id": ""}
    legacy_id = parts[-1]
    last_name = parts[0].replace("_", " ").strip()
    first_name = " ".join(p for p in parts[1:-1] if p).replace("_", " ").strip()
    full_name = " ".join(p for p in [first_name, last_name] if p).strip()
    return {"name": full_name, "legacy_id": legacy_id}


@app.get("/api/filters")
def filters():
    if not DATA_ROOT.exists():
        return jsonify({"departments": [], "professors": []}), 200

    department_filter = (request.args.get("department") or "").strip().lower()
    departments = sorted([p.name for p in DATA_ROOT.iterdir() if p.is_dir()], key=str.lower)

    professors: list[dict[str, str]] = []
    if department_filter:
        for dept in departments:
            if dept.lower() != department_filter:
                continue
            dept_path = DATA_ROOT / dept
            for txt_path in sorted(dept_path.glob("*.txt")):
                info = parse_professor_from_filename(txt_path)
                if not info["name"]:
                    continue
                professors.append(
                    {
                        "name": info["name"],
                        "legacy_id": info["legacy_id"],
                        "department": dept,
                    }
                )

    professors.sort(key=lambda p: (p["name"].lower(), p["department"].lower()))
    return jsonify({"departments": departments, "professors": professors}), 200


@app.post("/api/recommendations")
def recommendations():
    payload = request.get_json(silent=True) or {}

    try:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Recommendation script timed out"}), 504
    except subprocess.CalledProcessError as exc:
        return (
            jsonify(
                {
                    "error": "Recommendation script failed",
                    "stderr": (exc.stderr or "").strip(),
                }
            ),
            500,
        )

    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return (
            jsonify(
                {
                    "error": "Recommendation script returned invalid JSON",
                    "stdout": completed.stdout.strip(),
                }
            ),
            500,
        )

    return jsonify(data), 200


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
