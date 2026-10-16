import os
import subprocess
import sys
import time
from collections import defaultdict

from flask import Flask, jsonify, request

from rag import RAG

app = Flask(__name__)

INGEST_API_KEY = os.environ.get("INGEST_API_KEY", "")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "https://azure-ai-rag.techcloudup.com")
MIN_INTERVAL_SECONDS = float(os.environ.get("RATE_LIMIT_INTERVAL", "5"))
DAILY_CAP = int(os.environ.get("RATE_LIMIT_DAILY_CAP", "100"))

rag = RAG()


class RateLimiter:
    def __init__(self, min_interval, daily_cap):
        self.min_interval = min_interval
        self.daily_cap = daily_cap
        self.last_request = defaultdict(float)
        self.daily_count = 0
        self.day = time.strftime("%Y-%m-%d")

    def check(self, ip):
        today = time.strftime("%Y-%m-%d")
        if today != self.day:
            self.day = today
            self.daily_count = 0
            self.last_request.clear()
        if self.daily_count >= self.daily_cap:
            return False
        now = time.time()
        if now - self.last_request[ip] < self.min_interval:
            return False
        self.last_request[ip] = now
        self.daily_count += 1
        return True


limiter = RateLimiter(MIN_INTERVAL_SECONDS, DAILY_CAP)


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if origin in [o.strip() for o in CORS_ORIGINS.split(",")]:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/ask", methods=["POST", "OPTIONS"])
def ask():
    if request.method == "OPTIONS":
        return "", 204
    ip = request.remote_addr or "unknown"
    if not limiter.check(ip):
        return jsonify({"error": "rate limit exceeded"}), 429

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    start = time.time()
    result = rag.generate(question)
    result["latency_ms"] = int((time.time() - start) * 1000)
    result["model"] = rag.chat_deployment
    return jsonify(result)


@app.route("/ingest", methods=["POST", "OPTIONS"])
def ingest():
    if request.method == "OPTIONS":
        return "", 204
    if not INGEST_API_KEY or request.headers.get("X-API-Key") != INGEST_API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    script = os.path.join(os.path.dirname(__file__), "ingest.py")
    proc = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode == 0:
        return jsonify({"status": "ok"})
    return jsonify({"error": proc.stderr[-500:]}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
