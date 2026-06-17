"""Locust example: stress profile.

Run:  locust -f tests/templates/stress/locust-example.py \
        --headless -u 50 -r 5 --run-time 3m \
        --host http://localhost:3000
"""
from locust import HttpUser, task, between


class StressUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(3)
    def health_check(self):
        with self.client.get("/api/health", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"unexpected status {r.status_code}")

    @task(1)
    def list_items(self):
        self.client.get("/api/items")
