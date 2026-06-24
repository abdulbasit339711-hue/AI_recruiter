import { motion } from 'framer-motion';

interface TabBarProps {
  tabs: { key: string; label: string; icon?: React.ReactNode }[];
  active: string;
  onChange: (key: string) => void;
  className?: string;
}

export function TabBar({ tabs, active, onChange, className = '' }: TabBarProps) {
  return (
    <div className={`flex items-center gap-1 border-b border-white/[0.06] ${className}`}>
      {tabs.map((tab) => {
        const isActive = tab.key === active;
        return (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            className={`relative flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
              isActive ? 'text-teal' : 'text-muted hover:text-heading'
            }`}
          >
            {tab.icon}
            {tab.label}
            {isActive && (
              <motion.div
                layoutId="tab-underline"
                className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full"
                style={{ background: '#1C99BF', boxShadow: '0 0 12px rgba(28,153,191,0.6)' }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
