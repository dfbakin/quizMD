import { useState, useEffect, useCallback, useRef } from 'react';

interface TimerProps {
  deadlineAt: string;
  serverNow: string;
  onExpire: () => void;
}

export default function Timer({ deadlineAt, serverNow, onExpire }: TimerProps) {
  const offsetMsRef = useRef(0);
  const didExpireRef = useRef(false);

  const calcRemaining = useCallback(() => {
    const end = new Date(deadlineAt).getTime();
    return Math.max(0, Math.floor((end - (Date.now() + offsetMsRef.current)) / 1000));
  }, [deadlineAt]);

  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    offsetMsRef.current = new Date(serverNow).getTime() - Date.now();
    didExpireRef.current = false;
    const tick = () => {
      const r = calcRemaining();
      setRemaining(r);
      if (r <= 0 && !didExpireRef.current) {
        didExpireRef.current = true;
        onExpire();
      }
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [calcRemaining, onExpire, serverNow]);

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
