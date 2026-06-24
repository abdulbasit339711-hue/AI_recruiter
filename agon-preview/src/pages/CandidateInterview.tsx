import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { TopNav } from '../components/TopNav';
import { GlassCard } from '../components/GlassCard';
import { RadialGauge } from '../components/RadialGauge';
import { BarChart } from '../components/BarChart';
import { GoalTile } from '../components/GoalTile';
import { TabBar } from '../components/TabBar';
import { DecisionBanner } from '../components/DecisionBanner';
import { CountUp } from '../components/CountUp';
import { ArrowLeft, Clock, Mic, Target, Activity, Check, TrendingUp, MessageSquare, BarChart3, ListChecks } from 'lucide-react';
import { useCandidates } from '../lib/store';
import { tierFromScore } from '../lib/types';

const tierColors = { strong: '#34C28A', promising: '#F5B544', weak: '#F25C7C' };

export function CandidateInterview() {
  const { id } = useParams();
  const candidates = useCandidates();
  const candidate = candidates.find((c) => c.id === id);
  const [tab, setTab] = useState('overview');

  if (!candidate) {
    return (
      <div className="min-h-screen bg-canvas">
        <TopNav />
        <div className="mx-auto max-w-[1400px] px-4 py-20 text-center">
          <h1 className="text-2xl font-bold text-heading">Candidate not found</h1>
          <Link to="/admin/candidates" className="mt-4 inline-block text-teal hover:text-teal-hover">← Back to candidates</Link>
        </div>
      </div>
    );
  }

  const tier = tierFromScore(candidate.score);
  const decisionColor = tierColors[tier];
  const decisionLabel = candidate.decision === 'HIRE' ? 'HIRE' : candidate.decision === 'CONSIDER' ? 'CONSIDER' : 'REJECT';

  const tabs = [
    { key: 'overview', label: 'Overview', icon: <BarChart3 className="h-4 w-4" /> },
    { key: 'assessment', label: 'Assessment', icon: <ListChecks className="h-4 w-4" /> },
    { key: 'transcript', label: 'Transcript', icon: <MessageSquare className="h-4 w-4" /> },
  ];

  const assessmentItems = candidate.interview.assessmentScores;

  return (
    <div className="min-h-screen bg-canvas">
      <TopNav />
      <main className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
        {/* Back link */}
        <Link to="/admin/candidates" className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-teal">
          <ArrowLeft className="h-4 w-4" /> All candidates
        </Link>

        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="mb-5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full text-sm font-bold text-canvas" style={{ background: candidate.avatarColor }}>
              {candidate.name.split(' ').map((n) => n[0]).join('').slice(0, 2)}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-heading">{candidate.name}</h1>
              <p className="text-sm text-muted">{candidate.jobTitle} · Applied {candidate.appliedDate}</p>
            </div>
          </div>
          <span
            className="inline-flex items-center rounded-full px-5 py-2 text-sm font-bold uppercase tracking-wider"
            style={{ background: `${decisionColor}26`, color: decisionColor, border: `1px solid ${decisionColor}59`, boxShadow: `0 0 20px ${decisionColor}30` }}
          >
            {decisionLabel}
          </span>
        </motion.div>

        {/* Hero Summary */}
        <GlassCard className="mb-4 p-6" delay={0.05}>
          <div className="flex flex-col items-center gap-6 lg:flex-row lg:gap-8">
            <div className="shrink-0">
              <RadialGauge value={candidate.score} size={90} strokeWidth={8} label="AI Score" />
            </div>
            <div className="grid flex-1 grid-cols-1 gap-4 sm:grid-cols-3 w-full">
              <BarChart compact items={[
                { label: 'Profile Match', value: candidate.summary.profileMatch },
                { label: 'Semantic Match', value: candidate.summary.semanticMatch },
                { label: 'LLM Score', value: candidate.summary.llmScore },
              ]} />
              <div className="flex flex-col justify-center rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <span className="text-xs uppercase tracking-wider text-muted">Final AI Match</span>
                <div className="mt-2 flex items-baseline gap-1">
                  <span className="tnum font-mono text-4xl font-bold" style={{ color: decisionColor }}>
                    <CountUp value={candidate.summary.aiMatch} duration={1.5} />
                  </span>
                  <span className="text-sm text-faint">/100</span>
                </div>
                <span className="mt-1 text-xs" style={{ color: decisionColor }}>{tier === 'strong' ? 'Strong fit — recommend hire' : tier === 'promising' ? 'Promising — consider next round' : 'Weak fit — not recommended'}</span>
              </div>
            </div>
          </div>
        </GlassCard>

        {/* Fixed Strip */}
        <GlassCard className="mb-4 p-4" delay={0.1}>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              { icon: <Clock className="h-4 w-4" />, label: 'Duration', value: candidate.interview.duration, color: '#1C99BF' },
              { icon: <Mic className="h-4 w-4" />, label: 'Talk Ratio', value: `${candidate.interview.talkRatio}%`, color: '#3DAFCC' },
              { icon: <Target className="h-4 w-4" />, label: 'Goals Covered', value: `${candidate.interview.goalsCovered}/${candidate.interview.totalGoals}`, color: '#F5B544' },
              { icon: <Activity className="h-4 w-4" />, label: 'Engagement Avg', value: `${candidate.interview.engagementAvg}/10`, color: '#34C28A' },
            ].map((stat) => (
              <div key={stat.label} className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg" style={{ background: `${stat.color}1a`, color: stat.color }}>
                  {stat.icon}
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-muted">{stat.label}</div>
                  <div className="tnum font-mono text-sm font-semibold text-heading">{stat.value}</div>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* Decision Banner */}
        <div className="mb-4">
          <DecisionBanner
            decision={candidate.decision}
            score={candidate.score}
            rationale={`${candidate.name} demonstrated ${tier === 'strong' ? 'strong command' : tier === 'promising' ? 'adequate command' : 'insufficient command'} across ${candidate.interview.goalsCovered} of ${candidate.interview.totalGoals} assessed goals. The AI model evaluated ${candidate.interview.assessmentScores.length} competency dimensions with a weighted semantic and LLM analysis, producing a composite match score of ${candidate.summary.aiMatch}. Key strengths include ${candidate.interview.strengths[0].split('—')[0].trim()}. Development areas were noted in ${candidate.interview.developmentAreas.length} categories.`}
            delay={0.12}
          />
        </div>

        {/* Tabbed Panel */}
        <GlassCard className="overflow-hidden" delay={0.15}>
          <TabBar tabs={tabs} active={tab} onChange={setTab} className="px-2" />
          <div className="p-6">
            <AnimatePresence mode="wait">
              {tab === 'overview' && (
                <motion.div key="overview" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.3 }} className="grid gap-6 lg:grid-cols-2">
                  {/* Left col */}
                  <div className="space-y-6">
                    <div>
                      <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-emerald"><Check className="h-4 w-4" /> Strengths</h4>
                      <div className="space-y-2.5">
                        {candidate.interview.strengths.map((s, i) => (
                          <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.08 }} className="flex gap-2.5 rounded-lg border border-emerald/15 bg-emerald/[0.06] p-3">
                            <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald" />
                            <p className="text-xs leading-relaxed text-muted">{s}</p>
                          </motion.div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber"><TrendingUp className="h-4 w-4" /> Development Areas</h4>
                      <div className="space-y-2.5">
                        {candidate.interview.developmentAreas.map((s, i) => (
                          <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.08 }} className="flex gap-2.5 rounded-lg border border-amber/15 bg-amber/[0.06] p-3">
                            <TrendingUp className="mt-0.5 h-4 w-4 shrink-0 rotate-45 text-amber" />
                            <p className="text-xs leading-relaxed text-muted">{s}</p>
                          </motion.div>
                        ))}
                      </div>
                    </div>
                    {/* Talk ratio dual bar */}
                    <div>
                      <h4 className="mb-3 text-sm font-semibold text-heading">Talk Ratio Breakdown</h4>
                      <div className="flex h-4 w-full overflow-hidden rounded-full">
                        <motion.div initial={{ width: 0 }} animate={{ width: `${candidate.interview.botTalkRatio}%` }} transition={{ duration: 1 }} className="h-full bg-faint/40" />
                        <motion.div initial={{ width: 0 }} animate={{ width: `${candidate.interview.candidateTalkRatio}%` }} transition={{ duration: 1, delay: 0.2 }} className="h-full bg-teal" style={{ boxShadow: '0 0 12px rgba(28,153,191,0.4)' }} />
                      </div>
                      <div className="mt-2 flex justify-between text-xs">
                        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-faint/40" /> <span className="text-muted">Bot {candidate.interview.botTalkRatio}%</span></span>
                        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-teal" /> <span className="text-teal">Candidate {candidate.interview.candidateTalkRatio}%</span></span>
                      </div>
                    </div>
                  </div>

                  {/* Right col */}
                  <div className="space-y-6">
                    <div>
                      <h4 className="mb-3 text-sm font-semibold text-heading">Engagement Timeline</h4>
                      <div className="flex items-end gap-1.5" style={{ height: 120 }}>
                        {candidate.interview.engagementTimeline.map((v, i) => {
                          const pct = (v / 10) * 100;
                          const color = v >= 8 ? '#34C28A' : v >= 6 ? '#F5B544' : '#F25C7C';
                          return (
                            <div key={i} className="flex flex-1 flex-col items-center gap-1">
                              <div className="relative w-full flex-1 rounded-md bg-white/[0.03]" style={{ minHeight: 80 }}>
                                <motion.div
                                  initial={{ height: 0 }}
                                  animate={{ height: `${pct}%` }}
                                  transition={{ duration: 0.6, delay: i * 0.04 }}
                                  className="absolute bottom-0 left-0 right-0 rounded-md"
                                  style={{ background: color, boxShadow: `0 0 8px ${color}40` }}
                                />
                              </div>
                              <span className="text-[8px] text-faint">{i + 1}</span>
                            </div>
                          );
                        })}
                      </div>
                      <div className="mt-2 flex items-center justify-between text-[10px] text-faint">
                        <span>Session start</span><span>Session end</span>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      {candidate.interview.miniStats.map((stat) => (
                        <div key={stat.label} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-center">
                          <div className="text-[10px] uppercase tracking-wider text-muted">{stat.label}</div>
                          <div className="tnum mt-1.5 font-mono text-lg font-bold text-teal">{stat.value}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}

              {tab === 'assessment' && (
                <motion.div key="assessment" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.3 }}>
                  <h4 className="mb-3 text-sm font-semibold text-heading">Competency Scores</h4>
                  <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-7">
                    {assessmentItems.map((item, i) => {
                      const t = tierFromScore(item.score);
                      const color = tierColors[t];
                      return (
                        <motion.div key={item.label} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.05 }} className="rounded-xl border p-3 text-center" style={{ background: `${color}12`, borderColor: `${color}26` }}>
                          <div className="tnum font-mono text-xl font-bold" style={{ color }}>{item.score}</div>
                          <div className="mt-1 text-[10px] leading-tight text-muted">{item.label}</div>
                        </motion.div>
                      );
                    })}
                  </div>

                  <h4 className="mb-3 text-sm font-semibold text-heading">Goal Coverage</h4>
                  <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                    {candidate.interview.goals.map((goal, i) => (
                      <GoalTile key={i} title={goal.title} coverage={goal.coverage} outcome={goal.outcome} />
                    ))}
                  </div>
                </motion.div>
              )}

              {tab === 'transcript' && (
                <motion.div key="transcript" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.3 }} className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-heading">Interview Transcript</h4>
                    <span className="text-xs text-faint">{candidate.interview.duration} total</span>
                  </div>
                  <div className="space-y-3">
                    {candidate.interview.transcript.map((msg, i) => (
                      <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} className={`flex ${msg.speaker === 'candidate' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${msg.speaker === 'candidate' ? 'bg-teal/15 text-heading' : 'bg-white/[0.04] text-muted'}`} style={msg.speaker === 'candidate' ? { border: '1px solid rgba(28,153,191,0.2)' } : { border: '1px solid rgba(255,255,255,0.05)' }}>
                          <div className="mb-1 flex items-center gap-2">
                            <span className={`text-[10px] font-semibold uppercase tracking-wider ${msg.speaker === 'candidate' ? 'text-teal' : 'text-faint'}`}>
                              {msg.speaker === 'candidate' ? candidate.name.split(' ')[0] : 'OZI Bot'}
                            </span>
                            <span className="tnum text-[10px] text-faint">{msg.time}</span>
                          </div>
                          <p className="text-sm leading-relaxed">{msg.text}</p>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </GlassCard>
      </main>
    </div>
  );
}
