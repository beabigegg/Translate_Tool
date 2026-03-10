import { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { fetchHealth } from '../api/system.js';

export function useHealthCheck(intervalMs = 30000) {
  const [isOnline, setIsOnline] = useState(true);
  const wasOffline = useRef(false);

  useEffect(() => {
    async function check() {
      try {
        await fetchHealth();
        if (wasOffline.current) {
          toast.success('Ollama 服務已恢復連線');
          wasOffline.current = false;
        }
        setIsOnline(true);
      } catch {
        if (!wasOffline.current) {
          toast.warning('Ollama 服務未回應，請確認已啟動', { duration: Infinity });
          wasOffline.current = true;
        }
        setIsOnline(false);
      }
    }
    check();
    const id = setInterval(check, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return { isOnline };
}
