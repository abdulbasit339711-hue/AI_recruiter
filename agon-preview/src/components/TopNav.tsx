import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Briefcase, Users, LayoutDashboard, Bell } from 'lucide-react';

const navItems = [
  { to: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/admin/jobs', label: 'Jobs', icon: Briefcase },
  { to: '/admin/candidates', label: 'Candidates', icon: Users },
];

export function TopNav() {
  const location = useLocation();
  return (
    <motion.header
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="sticky top-0 z-40 border-b border-white/[0.06] bg-canvas/80 backdrop-blur-xl"
    >
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="relative h-9 w-9">
            <svg viewBox="0 0 36 36" className="h-9 w-9">
              <circle cx="18" cy="18" r="14" fill="none" stroke="#1C99BF" strokeWidth="2.5" opacity="0.25" />
              <motion.circle
                cx="18" cy="18" r="14" fill="none" stroke="#1C99BF" strokeWidth="2.5" strokeLinecap="round"
                strokeDasharray="44 88" transform="rotate(-90 18 18)"
                initial={{ strokeDashoffset: 88 }}
                animate={{ strokeDashoffset: 0 }}
                transition={{ duration: 1.2, ease: 'easeOut' }}
                style={{ filter: 'drop-shadow(0 0 4px rgba(28,153,191,0.6))' }}
              />
            </svg>
          </div>
          <div className="leading-none">
            <span className="font-mono text-lg font-bold tracking-tight text-teal">OZI</span>
            <span className="ml-1 text-xs font-medium text-muted">Recruiter</span>
          </div>
        </div>

        {/* Nav links */}
        <nav className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => {
            const active = location.pathname.startsWith(item.to);
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={`relative flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  active ? 'text-teal' : 'text-muted hover:text-heading'
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
                {active && (
                  <motion.div
                    layoutId="nav-active"
                    className="absolute inset-0 -z-10 rounded-lg bg-teal/10"
                  />
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-3">
          <button className="relative rounded-lg p-2 text-muted transition-colors hover:text-heading">
            <Bell className="h-5 w-5" />
            <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-teal" style={{ boxShadow: '0 0 8px #1C99BF' }} />
          </button>
          <div className="flex items-center gap-2.5 rounded-full border border-white/[0.08] bg-card/60 py-1 pl-1 pr-3">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-teal to-teal-hover text-xs font-bold text-canvas">
              AK
            </div>
            <div className="hidden leading-none sm:block">
              <div className="text-xs font-semibold text-heading">Admin Kim</div>
              <div className="text-[10px] text-faint">Recruiter</div>
            </div>
          </div>
        </div>
      </div>
      {/* Mobile nav */}
      <nav className="flex items-center gap-1 border-t border-white/[0.04] px-2 py-1 md:hidden">
        {navItems.map((item) => {
          const active = location.pathname.startsWith(item.to);
          const Icon = item.icon;
          return (
            <NavLink key={item.to} to={item.to} className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-medium ${active ? 'text-teal' : 'text-muted'}`}>
              <Icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </motion.header>
  );
}
