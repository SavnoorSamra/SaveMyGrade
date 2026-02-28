from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent


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
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5050"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() in {"1", "true", "yes"}


@app.get("/api/health")
def health() -> tuple[dict, int]:
    return {"status": "ok", "google_api_key_configured": bool(GOOGLE_API_KEY)}, 200


@app.post("/api/recommendations")
def recommendations():
    payload = request.get_json(silent=True) or {}

    if not payload.get("query"):
        return jsonify({"error": "'query' is required"}), 400

    try:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True,
            timeout=20,
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
