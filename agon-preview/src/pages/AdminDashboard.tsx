import { motion } from 'framer-motion';
import { TopNav } from '../components/TopNav';
import { GlassCard } from '../components/GlassCard';
import { Stat } from '../components/Stat';
import { Histogram } from '../components/Histogram';
import { Funnel } from '../components/Funnel';
import { DonutChart } from '../components/DonutChart';
import { RadialGauge } from '../components/RadialGauge';
import { ScoreBadge } from '../components/ScoreBadge';
import { StatusPill } from '../components/StatusPill';
import { Briefcase, Users, Gauge, Clock, ArrowRight, Trophy } from 'lucide-react';
import { useCandidates, useJobs } from '../lib/store';
import { Link } from 'react-router-dom';
import type { CandidateStatus } from '../lib/types';

export function AdminDashboard() {
  const candidates = useCandidates();
  const jobs = useJobs();

  const totalJobs = jobs.length;
  const totalCandidates = candidates.length;
  const avgScore = Math.round(candidates.reduce((s, c) => s + c.score, 0) / candidates.length);
  const pending = candidates.filter((c) => c.status === 'Pending Review').length;

  // Histogram buckets
  const buckets = [
    { label: '0-20', count: candidates.filter((c) => c.score <= 20).length },
    { label: '21-40', count: candidates.filter((c) => c.score > 20 && c.score <= 40).length },
    { label: '41-60', count: candidates.filter((c) => c.score > 40 && c.score <= 60).length },
    { label: '61-80', count: candidates.filter((c) => c.score > 60 && c.score <= 80).length },
    { label: '81-100', count: candidates.filter((c) => c.score > 80).length },
  ];

  // Funnel
  const processed = candidates.filter((c) => c.status !== 'Pending Review').length;
  const shortlisted = candidates.filter((c) => c.status === 'Shortlisted' || c.status === 'Hired').length;

  // Status donut
  const statusCounts: Record<CandidateStatus, number> = {
    'Pending Review': 0, Shortlisted: 0, 'In Interview': 0, Hired: 0, Rejected: 0, Archived: 0,
  };
  candidates.forEach((c) => { statusCounts[c.status]++; });
  const donutData = [
    { label: 'Shortlisted', value: statusCounts.Shortlisted, color: '#1C99BF' },
    { label: 'In Interview', value: statusCounts['In Interview'], color: '#3DAFCC' },
    { label: 'Pending Review', value: statusCounts['Pending Review'], color: '#F5B544' },
    { label: 'Hired', value: statusCounts.Hired, color: '#34C28A' },
    { label: 'Rejected', value: statusCounts.Rejected, color: '#F25C7C' },
  ].filter((d) => d.value > 0);

  // Top talent
  const topTalent = [...candidates].sort((a, b) => b.score - a.score).slice(0, 4);

  return (
    <div className="min-h-screen bg-canvas">
      <TopNav />
      <main className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
        {/* Page title */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="mb-6">
          <h1 className="text-2xl font-bold text-heading">Recruitment Overview</h1>
          <p className="mt-1 text-sm text-muted">Real-time AI screening pipeline across all open roles.</p>
        </motion.div>

        {/* KPI Strip */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Total Jobs" value={totalJobs} accentColor="#1C99BF" icon={<Briefcase className="h-4 w-4" />} delay={0} />
          <Stat label="Total Candidates" value={totalCandidates} accentColor="#3DAFCC" icon={<Users className="h-4 w-4" />} delay={0.08} />
          <Stat label="Avg Score" value={avgScore} suffix="/100" accentColor="#34C28A" icon={<Gauge className="h-4 w-4" />} delay={0.16} />
          <Stat label="Pending Review" value={pending} accentColor="#F5B544" icon={<Clock className="h-4 w-4" />} delay={0.24} />
        </div>

        {/* Mid section: Histogram + Funnel */}
        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          <GlassCard className="lg:col-span-2 p-6" delay={0.1}>
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-heading">Score Distribution</h3>
                <p className="text-xs text-muted">Candidate scores bucketed across 5 tiers</p>
              </div>
              <div className="hidden gap-3 sm:flex">
                {[{ c: '#F25C7C', l: 'Weak' }, { c: '#F5B544', l: 'Promising' }, { c: '#34C28A', l: 'Strong' }].map((t) => (
                  <div key={t.l} className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full" style={{ background: t.c }} />
                    <span className="text-[10px] text-faint">{t.l}</span>
                  </div>
                ))}
              </div>
            </div>
            <Histogram buckets={buckets} className="h-44" />
          </GlassCard>

          <GlassCard className="p-6" delay={0.18}>
            <h3 className="mb-1 font-semibold text-heading">Recruitment Funnel</h3>
            <p className="mb-5 text-xs text-muted">Pipeline conversion across stages</p>
            <Funnel stages={[
              { label: 'Total Applied', value: totalCandidates, color: '#3DAFCC' },
              { label: 'Processed by AI', value: processed, color: '#1C99BF' },
              { label: 'Shortlisted', value: shortlisted, color: '#34C28A' },
            ]} />
            <div className="mt-5 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted">Conversion Rate</span>
                <span className="tnum font-mono font-semibold text-emerald">
                  {totalCandidates > 0 ? Math.round((shortlisted / totalCandidates) * 100) : 0}%
                </span>
              </div>
            </div>
          </GlassCard>
        </div>

        {/* Bottom section: Donut + Top Talent */}
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <GlassCard className="p-6" delay={0.1}>
            <h3 className="mb-4 font-semibold text-heading">Status Breakdown</h3>
            <DonutChart data={donutData} centerLabel="Candidates" centerValue={totalCandidates} />
          </GlassCard>

          <GlassCard className="lg:col-span-2 p-6" delay={0.18}>
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Trophy className="h-4 w-4 text-amber" />
                <h3 className="font-semibold text-heading">Top Talent Spotlight</h3>
              </div>
              <Link to="/admin/candidates" className="flex items-center gap-1 text-xs font-medium text-teal hover:text-teal-hover">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {topTalent.map((c, i) => (
                <Link
                  key={c.id}
                  to={`/admin/candidates/${c.id}/interview`}
                  className="glass glass-hover flex items-center gap-4 rounded-xl p-4"
                >
                  <RadialGauge value={c.score} size={72} strokeWidth={7} showValue />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-bold text-canvas" style={{ background: c.avatarColor }}>
                        {c.name.split(' ').map((n) => n[0]).join('').slice(0, 2)}
                      </div>
                      <span className="truncate text-sm font-semibold text-heading">{c.name}</span>
                    </div>
                    <p className="mt-1 truncate text-xs text-muted">{c.jobTitle}</p>
                    <div className="mt-2"><StatusPill status={c.status} /></div>
                  </div>
                </Link>
              ))}
            </div>
          </GlassCard>
        </div>
      </main>
    </div>
  );
}
