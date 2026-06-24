interface WaveformProps {
  bars?: number;
  active: boolean;
  className?: string;
}

export function Waveform({ bars = 28, active, className = '' }: WaveformProps) {
  return (
    <div className={`flex items-center justify-center gap-1 ${className}`} style={{ height: 60 }}>
      {Array.from({ length: bars }).map((_, i) => {
        const delay = (i % 7) * 0.12;
        const baseHeight = 20 + ((i * 13) % 40);
        return (
          <div
            key={i}
            className={`w-1 rounded-full ${active ? 'wave-bar' : ''}`}
            style={{
              height: active ? `${baseHeight}px` : '8px',
              background: active ? '#1C99BF' : 'rgba(28,153,191,0.2)',
              animationDelay: `${delay}s`,
              boxShadow: active ? '0 0 8px rgba(28,153,191,0.6)' : 'none',
              transition: 'height 0.3s, background 0.3s',
            }}
          />
        );
      })}
    </div>
  );
}
