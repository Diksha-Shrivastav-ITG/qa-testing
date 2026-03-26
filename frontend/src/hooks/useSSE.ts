import { useState, useEffect, useRef } from "react";

interface SSEProgress {
  step: string;
  page?: string;
  breakpoint?: number;
  progress: number;
  message: string;
}

interface UseSSEResult {
  progress: SSEProgress | null;
  isComplete: boolean;
  error: string | null;
}

const TERMINAL_STEPS = ["completed", "failed", "cancelled"];
const MAX_RECONNECTS = 5;
const RECONNECT_DELAY_MS = 3000;

export const useSSE = (runId: number | null): UseSSEResult => {
  const [progress, setProgress] = useState<SSEProgress | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reconnectCount = useRef(0);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (runId === null) return;

    let cancelled = false;

    const connect = () => {
      if (cancelled) return;

      const token = localStorage.getItem("token");
      const url = `http://localhost:8000/api/runs/${runId}/stream${token ? `?token=${encodeURIComponent(token)}` : ""}`;

      const es = new EventSource(url);
      esRef.current = es;

      es.onmessage = (event) => {
        try {
          const data: SSEProgress = JSON.parse(event.data);
          setProgress(data);
          reconnectCount.current = 0; // reset on successful message
          if (TERMINAL_STEPS.includes(data.step)) {
            setIsComplete(true);
            es.close();
          }
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        es.close();
        if (cancelled) return;

        // Auto-reconnect unless we've hit the limit or already complete
        if (reconnectCount.current < MAX_RECONNECTS && !isComplete) {
          reconnectCount.current++;
          setTimeout(connect, RECONNECT_DELAY_MS);
        } else {
          setError("Connection lost. Refresh to check status.");
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      esRef.current?.close();
    };
  }, [runId]); // eslint-disable-line react-hooks/exhaustive-deps

  return { progress, isComplete, error };
};

export default useSSE;
