"""
scripts/generate_logs.py — continuous realistic log event generator.

Usage:
    # Stream realistic traffic to localhost:8000 (Ctrl-C to stop)
    python scripts/generate_logs.py

    # Send a spike of 20 consecutive errors on payment-service then exit
    python scripts/generate_logs.py --spike

    # Target a different host
    python scripts/generate_logs.py --host http://localhost:9000

Options:
    --spike          Send 20 rapid error events to trigger anomaly detection, then exit.
    --host URL       Base URL of the watchdog API (default: http://localhost:8000).
    --interval SECS  Seconds between normal events (default: 0.5).
    --source SVC     Fix the source service name (default: random from built-in list).
"""
import argparse
import random
import time
from datetime import datetime, timezone

import httpx

SOURCES = [
    "api-gateway",
    "auth-service",
    "payment-service",
    "ml-pipeline",
    "db-proxy",
]

MESSAGES = {
    "info": [
        "Request processed successfully",
        "Cache hit — serving from memory",
        "Background job completed",
        "Health check OK",
        "User session refreshed",
        "Batch processed: 512 records",
    ],
    "warn": [
        "High latency detected: 850ms",
        "Retry attempt #2 on upstream",
        "Cache miss rate elevated: 34%",
        "Queue depth rising: 1200 items",
        "Memory usage at 78%",
        "Slow query detected: 2.1s",
    ],
    "error": [
        "Upstream timeout after 30s",
        "DB connection pool exhausted",
        "Invalid payload rejected",
        "Rate limit exceeded",
        "Redis ECONNREFUSED on retry #3",
        "SSL handshake failed",
        "Transaction rollback: deadlock",
    ],
    "critical": [
        "Service unreachable — circuit breaker OPEN",
        "Data loss detected — write failed",
        "OOM killed — process restarted",
        "Null pointer in payment processor",
        "Model checksum mismatch on load",
    ],
}

# Realistic traffic weights: mostly info/warn, occasional errors, rare criticals
LEVEL_WEIGHTS = {"info": 60, "warn": 22, "error": 14, "critical": 4}


def post_event(client: httpx.Client, source: str, level: str, message: str) -> bool:
    payload = {
        "source": source,
        "level": level,
        "message": message,
        "value": round(random.uniform(10, 999), 2) if level in ("warn", "error") else None,
        "tags": {
            "env": random.choice(["prod", "staging"]),
            "region": random.choice(["us-east", "eu-west", "ap-south"]),
            "generated": "true",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        r = client.post("/events/", json=payload, timeout=5)
        return r.status_code == 201
    except Exception as exc:
        print(f"  [!] Request failed: {exc}")
        return False


def run_spike(base_url: str, source: str = "payment-service") -> None:
    print(f"Sending spike: 20 consecutive ERROR events to '{source}'...")
    with httpx.Client(base_url=base_url) as client:
        for i in range(20):
            msg = MESSAGES["error"][i % len(MESSAGES["error"])]
            ok = post_event(client, source, "error", msg)
            status = "201" if ok else "ERR"
            print(f"  [{i+1:02d}] {status} — {msg}")
            time.sleep(0.05)
    print("Spike sent. Wait ~60s for the anomaly detector to fire.")


def run_continuous(base_url: str, source_override: str | None, interval: float) -> None:
    print(f"Streaming events to {base_url} — Ctrl-C to stop  (interval={interval}s)")
    levels = list(LEVEL_WEIGHTS.keys())
    weights = list(LEVEL_WEIGHTS.values())
    sent = 0
    with httpx.Client(base_url=base_url) as client:
        while True:
            source = source_override or random.choice(SOURCES)
            level = random.choices(levels, weights=weights)[0]
            message = random.choice(MESSAGES[level])
            ok = post_event(client, source, level, message)
            sent += 1
            if sent % 20 == 0:
                print(f"  ... {sent} events sent")
            if not ok:
                time.sleep(2)
            else:
                time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Watchdog log event generator")
    parser.add_argument("--spike", action="store_true", help="Send a spike burst then exit")
    parser.add_argument("--host", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between normal events")
    parser.add_argument("--source", default=None, help="Fix source service name")
    args = parser.parse_args()

    if args.spike:
        run_spike(args.host, args.source or "payment-service")
    else:
        try:
            run_continuous(args.host, args.source, args.interval)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
