import { useState, useEffect, useRef, useCallback } from 'react';
import { toast } from 'sonner';
import { fetchHealth, getProviderHealth } from '../api/system.js';

export function useHealthCheck(intervalMs = 30000) {
  const [isOnline, setIsOnline] = useState(true);
  const [providerHealth, setProviderHealth] = useState([]);
  const [providerHealthLoading, setProviderHealthLoading] = useState(false);
  const wasOffline = useRef(false);

  async function checkSystem() {
    try {
      await fetchHealth();
      if (wasOffline.current) {
        toast.success('服務已恢復連線');
        wasOffline.current = false;
      }
      setIsOnline(true);
    } catch {
      if (!wasOffline.current) {
        toast.warning('服務未回應，請確認已啟動', { duration: Infinity });
        wasOffline.current = true;
      }
      setIsOnline(false);
    }
  }

  const checkProviders = useCallback(async (deepseekApiKey = null) => {
    setProviderHealthLoading(true);
    try {
      const results = await getProviderHealth(deepseekApiKey);
      setProviderHealth(Array.isArray(results) ? results : []);
    } catch {
      setProviderHealth([]);
    } finally {
      setProviderHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSystem();
    const id = setInterval(checkSystem, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return { isOnline, providerHealth, providerHealthLoading, checkProviders };
}
