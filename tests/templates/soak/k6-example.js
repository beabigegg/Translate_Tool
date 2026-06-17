import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 5,                  // low constant load
  duration: '4h',          // long-running
  thresholds: {
    http_req_duration: ['p(95)<800'],  // looser threshold for soak
    http_req_failed:   ['rate<0.005'],  // tighter error rate over long run
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';

export default function () {
  const res = http.get(`${BASE_URL}/api/health`);
  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(2);  // slower cadence; we are looking for leaks, not throughput
}
