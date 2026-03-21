import { useState, useEffect, useCallback } from 'react';

interface TimerProps {
  startedAt: string;
  timeLimitMinutes: number;
  onExpire: () => void;
}

export default function Timer({ startedAt, timeLimitMinutes, onExpire }: TimerProps) {
  const calcRemaining = useCallback(() => {
    const start = new Date(startedAt).getTime();
    const end = start + timeLimitMinutes * 60 * 1000;
    return Math.max(0, Math.floor((end - Date.now()) / 1000));
  }, [startedAt, timeLimitMinutes]);

  const [remaining, setRemaining] = useState(calcRemaining);

  useEffect(() => {
    const interval = setInterval(() => {
      const r = calcRemaining();
      setRemaining(r);
      if (r <= 0) {
        clearInterval(interval);
        onExpire();
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [calcRemaining, onExpire]);

  const mins = Math.floor(remaining / 60);
  const secs = remaining % 60;
  const isWarning = remaining <= 300 && remaining > 0;
  const isExpired = remaining <= 0;

  return (
    <div
      className={`font-mono text-lg font-bold px-4 py-2 rounded-lg ${
        isExpired
          ? 'bg-red-600 text-white'
          : isWarning
            ? 'bg-amber-500 text-white animate-pulse'
            : 'bg-blue-600 text-white'
      }`}
    >
      {isExpired
        ? 'Время вышло'
        : `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`}
    </div>
  );
}
