"""Locust example: soak profile (long-running, low load).

Run:  locust -f tests/templates/soak/locust-example.py \
        --headless -u 5 -r 1 --run-time 4h \
        --host http://localhost:3000

Soak focuses on stability over time, not peak throughput.
Watch for: memory growth, connection exhaustion, queue backlog,
latency drift, error rate creep.
"""
from locust import HttpUser, task, between


class SoakUser(HttpUser):
    wait_time = between(2.0, 5.0)

    @task
    def health_check(self):
        with self.client.get("/api/health", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"unexpected status {r.status_code}")
