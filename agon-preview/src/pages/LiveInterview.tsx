import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Waveform } from '../components/Waveform';
import { useCandidates } from '../lib/store';

type Phase = 'idle' | 'waiting' | 'connected' | 'speaking';

export function LiveInterview() {
  const { token } = useParams();
  const candidates = useCandidates();
  // Derive a candidate from token (mock: last 3 chars index)
  const idx = token ? Math.abs(parseInt(token.slice(-3), 36) || 0) % candidates.length : 0;
  const candidate = candidates[idx] ?? candidates[0];

  const [phase, setPhase] = useState<Phase>('idle');
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (phase !== 'speaking') return;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [phase]);

  // Simulate phase transitions after joining
  useEffect(() => {
    if (phase === 'waiting') {
      const t = setTimeout(() => setPhase('connected'), 2500);
      return () => clearTimeout(t);
    }
    if (phase === 'connected') {
      const t = setTimeout(() => setPhase('speaking'), 2000);
      return () => clearTimeout(t);
    }
  }, [phase]);

  const fmtTime = (s: number) => {
    const m = Math.floor(s / 60).toString().padStart(2, '0');
    const sec = (s % 60).toString().padStart(2, '0');
    return `${m}:${sec}`;
  };

  const phaseConfig = {
    idle: { text: 'Ready to begin', color: '#556070' },
    waiting: { text: 'Waiting for connection…', color: '#F5B544' },
    connected: { text: 'Connected — preparing', color: '#3DAFCC' },
    speaking: { text: 'Speaking', color: '#1C99BF' },
  };

  const cfg = phaseConfig[phase];

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-canvas px-4 py-8">
      {/* Subtle background glow */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-1/2 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full" style={{ background: 'radial-gradient(circle, rgba(28,153,191,0.08) 0%, transparent 70%)' }} />
      </div>

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="relative z-10 flex w-full max-w-md flex-col items-center">
        {/* OZI logo small */}
        <div className="mb-10 flex items-center gap-2">
          <svg viewBox="0 0 36 36" className="h-7 w-7">
            <circle cx="18" cy="18" r="14" fill="none" stroke="#1C99BF" strokeWidth="2.5" opacity="0.25" />
            <circle cx="18" cy="18" r="14" fill="none" stroke="#1C99BF" strokeWidth="2.5" strokeLinecap="round" strokeDasharray="44 88" transform="rotate(-90 18 18)" style={{ filter: 'drop-shadow(0 0 4px rgba(28,153,191,0.6))' }} />
          </svg>
          <span className="font-mono text-sm font-bold tracking-tight text-teal">OZI Recruiter</span>
        </div>

        {/* Candidate header */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full text-lg font-bold text-canvas" style={{ background: candidate.avatarColor }}>
            {candidate.name.split(' ').map((n) => n[0]).join('').slice(0, 2)}
          </div>
          <h1 className="text-lg font-semibold text-muted">{candidate.name}</h1>
          <p className="mt-0.5 text-sm text-faint">{candidate.jobTitle}</p>
        </div>

        {/* Status indicator with pulse ring */}
        <div className="relative mb-8 flex h-40 w-40 items-center justify-center">
          <AnimatePresence>
            {phase === 'speaking' && (
              <motion.div
                initial={{ scale: 1, opacity: 0.5 }}
                animate={{ scale: 2.4, opacity: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 1.8, repeat: Infinity, ease: 'easeOut' }}
                className="absolute inset-0 rounded-full border-2 border-teal"
              />
            )}
            {phase === 'speaking' && (
              <motion.div
                initial={{ scale: 1, opacity: 0.4 }}
                animate={{ scale: 1.8, opacity: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 1.8, repeat: Infinity, ease: 'easeOut', delay: 0.6 }}
                className="absolute inset-0 rounded-full border-2 border-teal/50"
              />
            )}
          </AnimatePresence>
          <div
            className="relative flex h-32 w-32 items-center justify-center rounded-full border"
            style={{
              background: phase === 'speaking' ? 'rgba(28,153,191,0.08)' : 'rgba(8,34,52,0.6)',
              borderColor: `${cfg.color}40`,
              backdropFilter: 'blur(16px)',
              boxShadow: phase === 'speaking' ? '0 0 40px rgba(28,153,191,0.25)' : 'none',
              transition: 'all 0.5s ease',
            }}
          >
            <div className="text-center">
              <div className="text-xs uppercase tracking-wider" style={{ color: cfg.color }}>{cfg.text}</div>
              {phase === 'speaking' && (
                <div className="tnum mt-1 font-mono text-2xl font-bold text-heading">{fmtTime(seconds)}</div>
              )}
            </div>
          </div>
        </div>

        {/* Waveform */}
        <div className="mb-8 w-full max-w-sm">
          <Waveform active={phase === 'speaking'} bars={32} />
        </div>

        {/* Action button */}
        <AnimatePresence mode="wait">
          {phase === 'idle' && (
            <motion.button
              key="join"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              onClick={() => setPhase('waiting')}
              className="rounded-xl bg-teal px-8 py-3 text-sm font-semibold text-canvas transition-all hover:bg-teal-hover hover:shadow-[0_0_32px_rgba(28,153,191,0.4)]"
            >
              Join Interview
            </motion.button>
          )}
          {phase === 'speaking' && (
            <motion.button
              key="end"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              onClick={() => { setPhase('idle'); setSeconds(0); }}
              className="rounded-xl border border-rose/40 bg-rose/10 px-8 py-3 text-sm font-semibold text-rose transition-all hover:bg-rose/20"
            >
              End Interview
            </motion.button>
          )}
        </AnimatePresence>

        {/* Helper text */}
        {phase === 'idle' && (
          <p className="mt-6 max-w-xs text-center text-xs text-faint">OZI will guide you through a structured interview. Your responses are analyzed in real time.</p>
        )}
        {phase === 'waiting' && (
          <p className="mt-6 max-w-xs text-center text-xs text-faint">Establishing secure connection with the AI interviewer…</p>
        )}
        {phase === 'connected' && (
          <p className="mt-6 max-w-xs text-center text-xs text-faint">Connection established. The interview will begin shortly.</p>
        )}
      </motion.div>
    </div>
  );
}
