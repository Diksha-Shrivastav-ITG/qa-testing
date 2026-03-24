import { useState, useEffect } from "react";

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

const TERMINAL_STEPS = ["completed", "failed"];

export const useSSE = (runId: number | null): UseSSEResult => {
  const [progress, setProgress] = useState<SSEProgress | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (runId === null) return;

    const token = localStorage.getItem("token");
    const url = `http://localhost:8000/api/runs/${runId}/stream${token ? `?token=${encodeURIComponent(token)}` : ""}`;

    const es = new EventSource(url);

    es.onmessage = (event) => {
      try {
        const data: SSEProgress = JSON.parse(event.data);
        setProgress(data);
        if (TERMINAL_STEPS.includes(data.step)) {
          setIsComplete(true);
          es.close();
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      setError("Connection to run stream failed.");
      es.close();
    };

    return () => {
      es.close();
    };
  }, [runId]);

  return { progress, isComplete, error };
};

export default useSSE;
