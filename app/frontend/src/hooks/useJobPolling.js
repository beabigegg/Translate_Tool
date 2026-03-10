import { useEffect, useRef, useCallback } from 'react';
import { fetchJobStatus } from '../api/jobs.js';

export function useJobPolling(jobId, onUpdate, intervalMs = 2000) {
  const timer = useRef(null);

  const stop = useCallback(() => {
    if (timer.current) { clearInterval(timer.current); timer.current = null; }
  }, []);

  useEffect(() => {
    if (!jobId) return;
    async function poll() {
      try {
        const data = await fetchJobStatus(jobId);
        onUpdate(data);
        if (['completed', 'failed', 'cancelled'].includes(data.status)) stop();
      } catch (err) {
        console.error('Polling error:', err);
      }
    }
    poll();
    timer.current = setInterval(poll, intervalMs);
    return stop;
  }, [jobId]);

  return { stop };
}
