import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { TopNav } from '../components/TopNav';
import { GlassCard } from '../components/GlassCard';
import { ScoreBadge } from '../components/ScoreBadge';
import { StatusPill } from '../components/StatusPill';
import { Search, Upload, ChevronDown, Eye, Pencil, Archive, UserX, Filter } from 'lucide-react';
import { useCandidates, useJobs, storeActions } from '../lib/store';
import { Modal } from '../components/Modal';
import type { CandidateStatus } from '../lib/types';

export function CandidatesList() {
  const candidates = useCandidates();
  const jobs = useJobs();
  const [search, setSearch] = useState('');
  const [jobFilter, setJobFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState<string | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const filtered = useMemo(() => {
    return candidates.filter((c) => {
      const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase()) || c.jobTitle.toLowerCase().includes(search.toLowerCase());
      const matchesJob = jobFilter === 'all' || c.jobId === jobFilter;
      const matchesStatus = statusFilter === 'all' || c.status === statusFilter;
      return matchesSearch && matchesJob && matchesStatus;
    });
  }, [candidates, search, jobFilter, statusFilter]);

  const confirmArchive = () => {
    if (archiveTarget) {
      storeActions.updateCandidateStatus(archiveTarget, 'Archived');
      setArchiveTarget(null);
    }
  };

  const statusOptions: CandidateStatus[] = ['Pending Review', 'Shortlisted', 'In Interview', 'Hired', 'Rejected', 'Archived'];

  return (
    <div className="min-h-screen bg-canvas">
      <TopNav />
      <main className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-heading">Candidates</h1>
            <p className="mt-1 text-sm text-muted">{candidates.length} total · {filtered.length} matching filters</p>
          </div>
          <button
            onClick={() => setUploadOpen(true)}
            className="flex items-center gap-2 rounded-xl bg-teal px-4 py-2.5 text-sm font-semibold text-canvas transition-all hover:bg-teal-hover hover:shadow-[0_0_24px_rgba(28,153,191,0.4)]"
          >
            <Upload className="h-4 w-4" />
            Upload Resume
          </button>
        </motion.div>

        {/* Controls */}
        <GlassCard className="mb-4 p-4" delay={0.05}>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by name or job title…"
                className="w-full rounded-xl border border-white/[0.06] bg-white/[0.02] py-2.5 pl-10 pr-4 text-sm text-heading placeholder:text-faint focus:border-teal/40 focus:outline-none focus:ring-1 focus:ring-teal/20"
              />
            </div>

            {/* Job filter */}
            <div className="relative">
              <button
                onClick={() => setDropdownOpen((o) => !o)}
                className="flex w-full items-center justify-between gap-2 rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-sm text-heading lg:w-52"
              >
                <Filter className="h-4 w-4 text-faint" />
                <span className="flex-1 text-left">{jobFilter === 'all' ? 'All Jobs' : jobs.find((j) => j.id === jobFilter)?.title ?? 'All Jobs'}</span>
                <ChevronDown className={`h-4 w-4 text-faint transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
              </button>
              <AnimatePresence>
                {dropdownOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    className="absolute z-20 mt-2 w-full overflow-hidden rounded-xl border border-white/[0.08] bg-elevated py-1 shadow-xl lg:w-52"
                  >
                    <button onClick={() => { setJobFilter('all'); setDropdownOpen(false); }} className="w-full px-4 py-2 text-left text-sm text-muted hover:bg-white/[0.04] hover:text-heading">All Jobs</button>
                    {jobs.map((j) => (
                      <button key={j.id} onClick={() => { setJobFilter(j.id); setDropdownOpen(false); }} className="w-full px-4 py-2 text-left text-sm text-muted hover:bg-white/[0.04] hover:text-heading">{j.title}</button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Status filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-sm text-heading focus:border-teal/40 focus:outline-none"
            >
              <option value="all" className="bg-elevated">All Statuses</option>
              {statusOptions.map((s) => <option key={s} value={s} className="bg-elevated">{s}</option>)}
            </select>
          </div>
        </GlassCard>

        {/* Table / Empty state */}
        {filtered.length === 0 ? (
          <GlassCard className="flex flex-col items-center justify-center py-20 text-center" delay={0.1}>
            <UserX className="mb-4 h-14 w-14 text-faint" />
            <h3 className="text-lg font-semibold text-heading">No candidates found</h3>
            <p className="mt-1 max-w-sm text-sm text-muted">No candidates match your current search and filter combination. Try adjusting your filters or clearing the search.</p>
            <button onClick={() => { setSearch(''); setJobFilter('all'); setStatusFilter('all'); }} className="mt-5 rounded-xl border border-white/[0.08] bg-white/[0.02] px-4 py-2 text-sm font-medium text-heading transition-colors hover:border-teal/30 hover:text-teal">
              Clear filters
            </button>
          </GlassCard>
        ) : (
          <GlassCard className="overflow-hidden" delay={0.1}>
            {/* Header row */}
            <div className="hidden grid-cols-12 gap-4 border-b border-white/[0.06] px-5 py-3.5 text-xs font-medium uppercase tracking-wider text-faint md:grid">
              <div className="col-span-4">Candidate</div>
              <div className="col-span-3">Role</div>
              <div className="col-span-1">Score</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-2 text-right">Actions</div>
            </div>
            {/* Rows */}
            <div className="divide-y divide-white/[0.04]">
              {filtered.map((c, i) => (
                <motion.div
                  key={c.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.3, delay: i * 0.03 }}
                  className="grid grid-cols-1 items-center gap-3 px-5 py-3.5 transition-colors hover:bg-white/[0.02] md:grid-cols-12 md:gap-4"
                >
                  <div className="col-span-4 flex items-center gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold text-canvas" style={{ background: c.avatarColor }}>
                      {c.name.split(' ').map((n) => n[0]).join('').slice(0, 2)}
                    </div>
                    <div className="min-w-0">
                      <Link to={`/admin/candidates/${c.id}/interview`} className="truncate text-sm font-semibold text-heading hover:text-teal">{c.name}</Link>
                      <p className="text-[11px] text-faint">Applied {c.appliedDate}</p>
                    </div>
                  </div>
                  <div className="col-span-3 truncate text-sm text-muted">{c.jobTitle}</div>
                  <div className="col-span-1"><ScoreBadge score={c.score} size="sm" /></div>
                  <div className="col-span-2"><StatusPill status={c.status} /></div>
                  <div className="col-span-2 flex items-center justify-end gap-1">
                    <Link to={`/admin/candidates/${c.id}/interview`} className="rounded-lg p-2 text-muted transition-colors hover:bg-teal/10 hover:text-teal" title="View interview">
                      <Eye className="h-4 w-4" />
                    </Link>
                    <button className="rounded-lg p-2 text-muted transition-colors hover:bg-amber/10 hover:text-amber" title="Edit">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button onClick={() => setArchiveTarget(c.id)} className="rounded-lg p-2 text-muted transition-colors hover:bg-rose/10 hover:text-rose" title="Archive">
                      <Archive className="h-4 w-4" />
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          </GlassCard>
        )}
      </main>

      {/* Upload modal */}
      <Modal open={uploadOpen} onClose={() => setUploadOpen(false)} title="Upload Resume" footer={
        <>
          <button onClick={() => setUploadOpen(false)} className="rounded-xl border border-white/[0.08] px-4 py-2 text-sm font-medium text-muted transition-colors hover:text-heading">Cancel</button>
          <button onClick={() => setUploadOpen(false)} className="rounded-xl bg-teal px-4 py-2 text-sm font-semibold text-canvas hover:bg-teal-hover">Parse with AI</button>
        </>
      }>
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-white/[0.08] py-12 text-center">
          <Upload className="mb-3 h-10 w-10 text-faint" />
          <p className="text-sm font-medium text-heading">Drop resume PDF here</p>
          <p className="mt-1 text-xs text-muted">or click to browse — OZI will parse and pre-score automatically</p>
        </div>
      </Modal>

      {/* Archive confirm */}
      <Modal open={!!archiveTarget} onClose={() => setArchiveTarget(null)} title="Archive Candidate" maxWidth="max-w-md" footer={
        <>
          <button onClick={() => setArchiveTarget(null)} className="rounded-xl border border-white/[0.08] px-4 py-2 text-sm font-medium text-muted hover:text-heading">Keep</button>
          <button onClick={confirmArchive} className="rounded-xl bg-rose px-4 py-2 text-sm font-semibold text-canvas hover:brightness-110">Archive</button>
        </>
      }>
        <p className="text-sm text-muted">This candidate will be moved to the archived state. They will no longer appear in active lists but can be restored later. Are you sure?</p>
      </Modal>
    </div>
  );
}
