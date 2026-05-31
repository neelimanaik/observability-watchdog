"""
Seed script — generates realistic demo events so the dashboard has data immediately.
Run once after starting the app: python seed.py
"""
import random
import httpx
from datetime import datetime, timezone, timedelta

BASE = "http://localhost:8000"

SOURCES = ["api-gateway", "auth-service", "payment-service", "ml-pipeline", "db-proxy"]
MESSAGES = {
    "info":     ["Request processed", "Cache hit", "Job completed", "Health check OK"],
    "warn":     ["High latency detected", "Retry attempt #2", "Cache miss rate elevated", "Queue depth rising"],
    "error":    ["Upstream timeout", "DB connection failed", "Invalid payload rejected", "Rate limit exceeded"],
    "critical": ["Service unreachable", "Data loss detected", "OOM killed", "Circuit breaker OPEN"],
}

def seed(n: int = 300):
    now = datetime.now(timezone.utc)
    with httpx.Client(base_url=BASE) as client:
        for i in range(n):
            level = random.choices(
                ["info", "warn", "error", "critical"],
                weights=[60, 20, 15, 5],
            )[0]
            source = random.choice(SOURCES)
            # spread events over last 24h, with more weight on recent
            age_seconds = random.expovariate(1 / 3600)  # mean 1h ago
            ts = now - timedelta(seconds=min(age_seconds, 86400))
            payload = {
                "source": source,
                "level": level,
                "message": random.choice(MESSAGES[level]),
                "value": round(random.uniform(0, 1000), 2) if level in ("warn", "error") else None,
                "tags": {"env": random.choice(["prod", "staging"]), "region": random.choice(["us-east", "eu-west"])},
                "timestamp": ts.isoformat(),
            }
            r = client.post("/events/", json=payload)
            if r.status_code != 201:
                print(f"  [!] Failed: {r.text}")
            elif i % 50 == 0:
                print(f"  ... {i}/{n} events seeded")
    print(f"Done — {n} events seeded.")

if __name__ == "__main__":
    seed()
