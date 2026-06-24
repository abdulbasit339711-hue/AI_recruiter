import { useState } from 'react';
import { motion } from 'framer-motion';
import { TopNav } from '../components/TopNav';
import { GlassCard } from '../components/GlassCard';
import { Modal } from '../components/Modal';
import { useJobs, storeActions } from '../lib/store';
import { Plus, Archive, Briefcase, Users, ChevronRight, X } from 'lucide-react';
import type { Job } from '../lib/types';

const distColors = ['#F25C7C', '#F5B544', '#F5B544', '#34C28A', '#34C28A'];

export function JobManagement() {
  const jobs = useJobs();
  const [createOpen, setCreateOpen] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState<Job | null>(null);
  const [form, setForm] = useState({ title: '', department: '', description: '', llmPrompt: '' });

  const handleCreate = () => {
    if (!form.title || !form.department) return;
 const newJob: Job = {
      id: `job-${Date.now()}`,
      title: form.title,
      department: form.department,
      description: form.description || 'No description provided.',
      llmPrompt: form.llmPrompt || 'Evaluate candidates on core competencies relevant to the role.',
      candidateCount: 0,
      status: 'Active',
      scoreDistribution: [0, 0, 0, 0, 0],
      avgScore: 0,
      createdAt: new Date().toISOString().slice(0, 10),
    };
    storeActions.addJob(newJob);
    setForm({ title: '', department: '', description: '', llmPrompt: '' });
    setCreateOpen(false);
  };

  const confirmArchive = () => {
    if (archiveTarget) {
      storeActions.archiveJob(archiveTarget.id);
      setArchiveTarget(null);
    }
  };

  return (
    <div className="min-h-screen bg-canvas">
      <TopNav />
      <main className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-heading">Job Management</h1>
            <p className="mt-1 text-sm text-muted">{jobs.filter((j) => j.status === 'Active').length} active roles · {jobs.filter((j) => j.status === 'Archived').length} archived</p>
          </div>
          <button onClick={() => setCreateOpen(true)} className="flex items-center gap-2 rounded-xl bg-teal px-4 py-2.5 text-sm font-semibold text-canvas transition-all hover:bg-teal-hover hover:shadow-[0_0_24px_rgba(28,153,191,0.4)]">
            <Plus className="h-4 w-4" />
            Create Job
          </button>
        </motion.div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {jobs.map((job, i) => (
            <GlassCard key={job.id} hover delay={i * 0.05} className="flex flex-col p-5">
              <div className="mb-3 flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal/10 text-teal">
                    <Briefcase className="h-5 w-5" />
                  </div>
                  <span
                    className="inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide"
                    style={job.status === 'Active'
                      ? { background: 'rgba(28,153,191,0.15)', color: '#1C99BF', border: '1px solid rgba(28,153,191,0.3)' }
                      : { background: 'rgba(85,96,112,0.15)', color: '#556070', border: '1px solid rgba(85,96,112,0.3)' }
                    }
                  >
                    {job.status}
                  </span>
                </div>
              </div>

              <h3 className="text-base font-semibold text-heading">{job.title}</h3>
              <p className="mt-0.5 text-xs text-muted">{job.department}</p>
              <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-faint">{job.description}</p>

              <div className="mt-4 flex items-center gap-4 text-xs text-muted">
                <span className="flex items-center gap-1.5"><Users className="h-3.5 w-3.5" /> {job.candidateCount} candidates</span>
                <span className="tnum font-mono text-muted">Avg <span className="text-heading">{job.avgScore}</span></span>
              </div>

              {/* Mini score distribution bar */}
              <div className="mt-4">
                <div className="mb-1.5 text-[10px] uppercase tracking-wider text-faint">Score Distribution</div>
                {job.candidateCount > 0 ? (
                  <div className="flex h-2 w-full overflow-hidden rounded-full bg-white/[0.03]">
                    {job.scoreDistribution.map((count, idx) => {
                      const total = job.scoreDistribution.reduce((a, b) => a + b, 0) || 1;
                      const width = (count / total) * 100;
                      return width > 0 ? (
                        <div key={idx} className="h-full" style={{ width: `${width}%`, background: distColors[idx] }} />
                      ) : null;
                    })}
                  </div>
                ) : (
                  <div className="h-2 w-full rounded-full bg-white/[0.03]" />
                )}
                <div className="mt-1 flex justify-between text-[9px] text-faint">
                  <span>0</span><span>50</span><span>100</span>
                </div>
              </div>

              <div className="mt-4 flex items-center gap-2 border-t border-white/[0.05] pt-4">
                <button className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.02] py-2 text-xs font-medium text-heading transition-colors hover:border-teal/30 hover:text-teal">
                  View candidates <ChevronRight className="h-3 w-3" />
                </button>
                {job.status === 'Active' && (
                  <button onClick={() => setArchiveTarget(job)} className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-2 text-muted transition-colors hover:border-rose/30 hover:text-rose" title="Archive job">
                    <Archive className="h-4 w-4" />
                  </button>
                )}
              </div>
            </GlassCard>
          ))}
        </div>
      </main>

      {/* Create Job modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create New Job" maxWidth="max-w-xl" footer={
        <>
          <button onClick={() => setCreateOpen(false)} className="rounded-xl border border-white/[0.08] px-4 py-2 text-sm font-medium text-muted transition-colors hover:text-heading">Cancel</button>
          <button onClick={handleCreate} disabled={!form.title || !form.department} className="rounded-xl bg-teal px-4 py-2 text-sm font-semibold text-canvas transition-all hover:bg-teal-hover disabled:cursor-not-allowed disabled:opacity-40">Create Job</button>
        </>
      }>
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted">Job Title</label>
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Senior Frontend Engineer" className="w-full rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-sm text-heading placeholder:text-faint focus:border-teal/40 focus:outline-none" />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted">Department</label>
            <input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} placeholder="e.g. Engineering" className="w-full rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-sm text-heading placeholder:text-faint focus:border-teal/40 focus:outline-none" />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted">Description</label>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} placeholder="Describe the role and responsibilities…" className="w-full resize-none rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-sm text-heading placeholder:text-faint focus:border-teal/40 focus:outline-none" />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted">LLM Evaluation Prompt</label>
            <textarea value={form.llmPrompt} onChange={(e) => setForm({ ...form, llmPrompt: e.target.value })} rows={4} placeholder="Define how the AI should evaluate candidates for this role…" className="w-full resize-none rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 font-mono text-xs text-heading placeholder:text-faint focus:border-teal/40 focus:outline-none" />
          </div>
        </div>
      </Modal>

      {/* Archive confirm */}
      <Modal open={!!archiveTarget} onClose={() => setArchiveTarget(null)} title="Archive Job" maxWidth="max-w-md" footer={
        <>
          <button onClick={() => setArchiveTarget(null)} className="rounded-xl border border-white/[0.08] px-4 py-2 text-sm font-medium text-muted hover:text-heading">Keep Active</button>
          <button onClick={confirmArchive} className="rounded-xl bg-rose px-4 py-2 text-sm font-semibold text-canvas hover:brightness-110">Archive Job</button>
        </>
      }>
        <p className="text-sm text-muted">You are about to archive <span className="font-semibold text-heading">{archiveTarget?.title}</span>. The job will be soft-deleted from active views. Existing candidates and their interview data will be preserved. You can restore archived jobs at any time.</p>
      </Modal>
    </div>
  );
}
