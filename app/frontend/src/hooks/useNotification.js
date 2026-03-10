import { toast } from 'sonner';
export function useNotification() {
  return {
    success: (msg, opts) => toast.success(msg, opts),
    error: (msg, opts) => toast.error(msg, { duration: Infinity, ...opts }),
    warning: (msg, opts) => toast.warning(msg, opts),
    info: (msg, opts) => toast.info(msg, opts),
  };
}
