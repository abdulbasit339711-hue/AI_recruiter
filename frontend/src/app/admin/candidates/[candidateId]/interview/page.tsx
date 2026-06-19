"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  Clock,
  Mic,
  Target,
  Activity,
  BarChart3,
  ListChecks,
  MessageSquare,
  Check,
  TrendingUp,
  Brain,
  Video,
  ShieldAlert,
  ChevronDown,
} from "lucide-react";
import { getInterviewVideoUrl } from "@/lib/api";
import type { InterviewResult } from "@/lib/api";
import { GlassCard } from "@/components/ui/GlassCard";
import { RadialGauge, CountUp } from "@/components/ui/charts";
import { useCandidate } from "@/hooks/useCandidate";
import { useInterviewResult } from "@/hooks/useInterviewResult";

// ── helpers ────────────────────────────────────────────────────────────────────
function scoreColor(s: number): string {
  return s >= 70 ? "#34C28A" : s >= 40 ? "#F5B544" : "#F25C7C";
}

function initials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

function parseAssessment(
  raw: string | null | undefined
): Record<string, unknown> | null {
  if (!raw) return null;
  try {
    const p = JSON.parse(raw);
    if (p && typeof p === "object") return p as Record<string, unknown>;
  } catch {
    /* ignore */
  }
  return null;
}

const TIER_MAX = { tier1: 30, tier2: 40, tier3: 30 } as const;

type TabKey = "overview" | "assessment" | "transcript";

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  {
    key: "overview",
    label: "Overview",
    icon: <BarChart3 className="h-4 w-4" />,
  },
  {
    key: "assessment",
    label: "Assessment",
    icon: <ListChecks className="h-4 w-4" />,
  },
  {
    key: "transcript",
    label: "Transcript",
    icon: <MessageSquare className="h-4 w-4" />,
  },
];

// ── Page ───────────────────────────────────────────────────────────────────────
export default function CandidateInterviewPage() {
  const { candidateId } = useParams<{ candidateId: string }>();
  const id = Number(candidateId);
  const { data: candidate, isLoading } = useCandidate(id);
  const { data: interviewResult } = useInterviewResult(id);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  // ── Parse assessment ─────────────────────────────────────────────────────────
  const assessment = parseAssessment(
    interviewResult?.session?.overall_assessment
  );
  const fr = (assessment?.final_ai_recommendation ?? {}) as Record<
    string,
    unknown
  >;
  const ov = (assessment?.overall_assessment ?? {}) as Record<string, unknown>;

  const rawDecision = String(
    fr.decision ?? ov.hiring_recommendation ?? ""
  )
    .replace(/_/g, " ")
    .trim();
  const decision = rawDecision.toUpperCase();
  const rationale = String(fr.decision_rationale ?? ov.rationale ?? "");

  const overallScore =
    fr.overall_candidate_score != null
      ? Number(fr.overall_candidate_score)
      : ov.overall_candidate_score != null
      ? Number(ov.overall_candidate_score)
      : null;

  const jobMatch =
    fr.job_match_percentage != null
      ? Number(fr.job_match_percentage)
      : ov.job_match_percentage != null
      ? Number(ov.job_match_percentage)
      : null;

  // Decision color
  const dl = decision.toLowerCase();
  const decisionColor = dl.includes("hire")
    ? "#34C28A"
    : dl.includes("reject")
    ? "#F25C7C"
    : dl
    ? "#F5B544"
    : "#9CA3B0";

  // ── Scores ───────────────────────────────────────────────────────────────────
  const total =
    Number(candidate?.hr_score_override ?? candidate?.total_score) || 0;
  const color = scoreColor(total);

  const tiers = [
    {
      label: "Profile Match",
      value: Number(candidate?.tier1) || 0,
      max: TIER_MAX.tier1,
    },
    {
      label: "Semantic Match",
      value: Number(candidate?.tier2) || 0,
      max: TIER_MAX.tier2,
    },
    {
      label: "LLM Eval",
      value: Number(candidate?.tier3) || 0,
      max: TIER_MAX.tier3,
    },
  ];

  // ── Interview data ───────────────────────────────────────────────────────────
  const speaking = interviewResult?.speaking;
  const session = interviewResult?.session;
  // transcript: { speaker, text, sequence_number, evaluation? }[]
  const transcript = interviewResult?.transcript;
  // vision observations array lives at vision.observations
  const visionObs = interviewResult?.vision?.observations;

  // KPI values
  const duration =
    speaking?.duration_seconds != null
      ? fmtTime(Number(speaking.duration_seconds))
      : "—";

  const talkRatio =
    speaking?.candidate_talk_ratio_pct != null
      ? `${Math.round(Number(speaking.candidate_talk_ratio_pct))}%`
      : "—";

  const goals =
    session?.completed_goals != null
      ? `${session.completed_goals}/${session.total_goals ?? "?"}`
      : "—";

  const avgEngagement =
    visionObs && visionObs.length > 0
      ? (
          visionObs.reduce((s, v) => s + (v.engagement ?? 0), 0) /
          visionObs.length
        ).toFixed(1)
      : "—";

  // Strengths + dev areas
  const strengths =
    (fr.strengths as string[] | undefined) ??
    (ov.strengths as string[] | undefined) ??
    [];
  const devAreas =
    (fr.development_areas as string[] | undefined) ??
    (ov.development_areas as string[] | undefined) ??
    [];

  // Talk ratio bars
  const candRatio =
    speaking?.candidate_talk_ratio_pct != null
      ? Number(speaking.candidate_talk_ratio_pct)
      : 0;
  const botRatio = 100 - candRatio;

  // Candidate name
  const name = candidate?.name || candidate?.filename || "Candidate";

  // IQ score
  const iq = candidate?.iq_score;
  const hasIq = iq != null && !Number.isNaN(Number(iq));

  // Suppress unused variable warning — isLoading guards the hero card below
  void isLoading;

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      {/* Back link */}
      <Link
        href="/admin/candidates"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        All candidates
      </Link>

      {/* ── Header ── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="mb-5 flex flex-wrap items-center justify-between gap-4"
      >
        <div className="flex items-center gap-4">
          <div
            className="flex h-12 w-12 items-center justify-center rounded-full text-sm font-bold text-white shrink-0"
            style={{
              background: "linear-gradient(135deg, #1C99BF, #3DAFCC)",
            }}
          >
            {initials(name)}
          </div>
          <div>
            <h1 className="text-2xl font-bold text-heading">{name}</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Interview results
              {candidate?.created_at && (
                <>
                  {" "}
                  ·{" "}
                  {new Date(candidate.created_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </>
              )}
            </p>
          </div>
        </div>
        {decision && (
          <span
            className="rounded-lg px-4 py-1.5 text-sm font-bold tracking-widest"
            style={{
              background: `${decisionColor}26`,
              color: decisionColor,
              border: `1px solid ${decisionColor}59`,
              boxShadow: `0 0 20px ${decisionColor}30`,
            }}
          >
            {decision}
          </span>
        )}
      </motion.div>

      {/* ── Hero summary card ── */}
      <GlassCard className="mb-4 p-6">
        <div className="flex flex-col items-center gap-6 lg:flex-row lg:gap-8">
          {/* Radial gauge */}
          <div className="shrink-0">
            <RadialGauge
              value={Math.round(total)}
              max={100}
              size={90}
              stroke={8}
              color={color}
              label="score"
              sublabel="/ 100"
            />
          </div>

          {/* Tier bars */}
          <div className="flex-1 min-w-0 w-full">
            <div className="flex flex-col gap-3">
              {tiers.map((t) => {
                const pct = t.max ? (t.value / t.max) * 100 : 0;
                const tc = scoreColor(pct);
                return (
                  <div key={t.label}>
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">
                        {t.label}
                      </span>
                      <span
                        className="font-mono text-xs font-semibold tabular-nums"
                        style={{ color: tc }}
                      >
                        {Math.round(t.value)}/{t.max}
                      </span>
                    </div>
                    <div
                      className="h-2 w-full overflow-hidden rounded-full"
                      style={{ background: "rgba(255,255,255,0.04)" }}
                    >
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
                        className="h-full rounded-full"
                        style={{
                          background: `linear-gradient(90deg, ${tc}, ${tc}cc)`,
                          boxShadow: `0 0 12px ${tc}40`,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
              {hasIq && (
                <div className="flex items-center gap-2 pt-0.5">
                  <Brain className="h-3 w-3 text-primary shrink-0" />
                  <span className="text-xs text-muted-foreground">
                    IQ Screen
                  </span>
                  <span className="ml-auto font-mono text-xs font-semibold tabular-nums text-primary">
                    <CountUp value={Number(iq)} suffix="%" />
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Final score + AI metrics */}
          <div className="shrink-0 flex flex-col gap-3">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 text-center min-w-[100px]">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                Final Score
              </p>
              <p
                className="font-mono text-4xl font-bold tabular-nums leading-none"
                style={{ color }}
              >
                <CountUp value={total} />
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">/100</p>
            </div>
            {(overallScore != null || jobMatch != null) && (
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 text-center">
                {overallScore != null && (
                  <div className="mb-1">
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      AI Score
                    </p>
                    <p
                      className="font-mono text-xl font-bold tabular-nums"
                      style={{ color: decisionColor }}
                    >
                      {overallScore}
                    </p>
                  </div>
                )}
                {jobMatch != null && (
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      Job Match
                    </p>
                    <p
                      className="font-mono text-xl font-bold tabular-nums"
                      style={{ color: decisionColor }}
                    >
                      {jobMatch}%
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </GlassCard>

      {/* ── KPI strip ── */}
      <GlassCard className="mb-4 p-4">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            {
              label: "Duration",
              value: duration,
              color: "#1C99BF",
              icon: <Clock className="h-4 w-4" />,
            },
            {
              label: "Talk Ratio",
              value: talkRatio,
              color: "#3DAFCC",
              icon: <Mic className="h-4 w-4" />,
            },
            {
              label: "Goals",
              value: goals,
              color: "#F5B544",
              icon: <Target className="h-4 w-4" />,
            },
            {
              label: "Engagement",
              value: avgEngagement !== "—" ? `${avgEngagement}/10` : "—",
              color: "#34C28A",
              icon: <Activity className="h-4 w-4" />,
            },
          ].map((kpi) => (
            <div key={kpi.label} className="flex items-center gap-3">
              <div
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                style={{ background: `${kpi.color}1a`, color: kpi.color }}
              >
                {kpi.icon}
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  {kpi.label}
                </p>
                <p className="font-mono text-sm font-semibold text-heading tabular-nums">
                  {kpi.value}
                </p>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* ── Decision / rationale banner ── */}
      {rationale && (
        <motion.div
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="mb-4 overflow-hidden rounded-2xl"
          style={{
            background: "rgba(8,34,52,0.7)",
            backdropFilter: "blur(16px)",
            border: "1px solid rgba(255,255,255,0.08)",
            borderLeft: `6px solid ${decisionColor}`,
          }}
        >
          <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
            <div className="flex items-center gap-3 shrink-0">
              {overallScore != null && (
                <span
                  className="inline-flex items-center rounded-lg px-3 py-1.5 font-mono text-lg font-bold tabular-nums"
                  style={{
                    background: `${decisionColor}26`,
                    color: decisionColor,
                    border: `1px solid ${decisionColor}59`,
                  }}
                >
                  {overallScore}
                </span>
              )}
              {decision && (
                <span
                  className="inline-flex items-center rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider"
                  style={{
                    background: `${decisionColor}26`,
                    color: decisionColor,
                    border: `1px solid ${decisionColor}59`,
                  }}
                >
                  {decision}
                </span>
              )}
            </div>
            <p className="min-w-0 flex-1 text-sm leading-relaxed text-muted-foreground">
              <span className="font-semibold text-heading">AI Rationale — </span>
              {rationale}
            </p>
          </div>
        </motion.div>
      )}

      {/* ── Tabbed panel ── */}
      <GlassCard className="overflow-hidden">
        {/* Tab bar */}
        <div className="flex items-center gap-1 border-b border-white/[0.06] px-2">
          {TABS.map((tab) => {
            const isActive = tab.key === activeTab;
            const count =
              tab.key === "transcript" && transcript?.length
                ? ` (${transcript.length})`
                : "";
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className="relative flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors"
                style={{ color: isActive ? "#1C99BF" : "#9CA3B0" }}
              >
                {tab.icon}
                {tab.label}
                {count}
                {isActive && (
                  <motion.div
                    layoutId="tab-underline"
                    className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full"
                    style={{
                      background: "#1C99BF",
                      boxShadow: "0 0 12px rgba(28,153,191,0.6)",
                    }}
                  />
                )}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        <AnimatePresence mode="wait">
          {/* ── Overview tab ── */}
          {activeTab === "overview" && (
            <motion.div
              key="overview"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25 }}
              className="grid gap-6 p-6 lg:grid-cols-2"
            >
              {/* Left col: strengths, dev areas, talk ratio */}
              <div className="space-y-5">
                {strengths.length > 0 && (
                  <div>
                    <h3 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-heading">
                      <Check className="h-4 w-4" style={{ color: "#34C28A" }} />
                      Strengths
                    </h3>
                    <div className="space-y-2.5">
                      {strengths.map((s, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-2.5 rounded-lg p-3"
                          style={{
                            border: "1px solid rgba(52,194,138,0.15)",
                            background: "rgba(52,194,138,0.06)",
                          }}
                        >
                          <Check
                            className="mt-0.5 h-3.5 w-3.5 shrink-0"
                            style={{ color: "#34C28A" }}
                          />
                          <p className="text-xs text-muted-foreground leading-relaxed">
                            {s}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {devAreas.length > 0 && (
                  <div>
                    <h3 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-heading">
                      <TrendingUp
                        className="h-4 w-4"
                        style={{ color: "#F5B544" }}
                      />
                      Development Areas
                    </h3>
                    <div className="space-y-2.5">
                      {devAreas.map((d, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-2.5 rounded-lg p-3"
                          style={{
                            border: "1px solid rgba(245,181,68,0.15)",
                            background: "rgba(245,181,68,0.06)",
                          }}
                        >
                          <TrendingUp
                            className="mt-0.5 h-3.5 w-3.5 shrink-0"
                            style={{ color: "#F5B544" }}
                          />
                          <p className="text-xs text-muted-foreground leading-relaxed">
                            {d}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Talk ratio bar */}
                {candRatio > 0 && (
                  <div>
                    <h3 className="mb-2.5 text-sm font-semibold text-heading">
                      Talk Ratio
                    </h3>
                    <div
                      className="h-4 w-full overflow-hidden rounded-full"
                      style={{ background: "rgba(255,255,255,0.04)" }}
                    >
                      <div className="flex h-full">
                        <div
                          style={{
                            width: `${botRatio}%`,
                            background: "rgba(255,255,255,0.1)",
                          }}
                        />
                        <div
                          style={{
                            width: `${candRatio}%`,
                            background:
                              "linear-gradient(90deg, #1C99BF, #3DAFCC)",
                            boxShadow: "0 0 12px rgba(28,153,191,0.5)",
                          }}
                        />
                      </div>
                    </div>
                    <div className="mt-1.5 flex justify-between text-[10px] text-muted-foreground">
                      <span>Bot {Math.round(botRatio)}%</span>
                      <span style={{ color: "#1C99BF" }}>
                        Candidate {Math.round(candRatio)}%
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Right col: engagement timeline + mini stats */}
              <div className="space-y-5">
                {visionObs && visionObs.length > 0 && (
                  <div>
                    <h3 className="mb-2.5 text-sm font-semibold text-heading">
                      Engagement Timeline
                    </h3>
                    <div className="flex h-[120px] items-end gap-1.5">
                      {visionObs.map((obs, i) => {
                        const eng = obs.engagement ?? 0;
                        const ec =
                          eng >= 8
                            ? "#34C28A"
                            : eng >= 6
                            ? "#F5B544"
                            : "#F25C7C";
                        const h = Math.round((eng / 10) * 100);
                        return (
                          <div
                            key={i}
                            className="relative flex-1 rounded-md"
                            style={{
                              background: "rgba(255,255,255,0.03)",
                              minHeight: 8,
                            }}
                          >
                            <motion.div
                              initial={{ height: 0 }}
                              animate={{ height: `${h}%` }}
                              transition={{
                                duration: 0.8,
                                delay: i * 0.05,
                              }}
                              className="absolute bottom-0 left-0 right-0 rounded-md"
                              style={{ background: ec, opacity: 0.8 }}
                            />
                          </div>
                        );
                      })}
                    </div>
                    <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
                      <span>Start</span>
                      <span>End</span>
                    </div>
                  </div>
                )}

                {/* Speaking mini-stats */}
                {speaking && (
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      {
                        label: "Words",
                        value: speaking.candidate_words ?? 0,
                      },
                      {
                        label: "Turns",
                        value: speaking.candidate_turns ?? 0,
                      },
                      {
                        label: "WPM",
                        value: Math.round(
                          speaking.approx_words_per_min ?? 0
                        ),
                      },
                    ].map((s) => (
                      <div
                        key={s.label}
                        className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-center"
                      >
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                          {s.label}
                        </p>
                        <p className="mt-1 font-mono text-lg font-bold text-heading tabular-nums">
                          {s.value}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Goals breakdown */}
                {interviewResult?.goals && interviewResult.goals.length > 0 && (
                  <div>
                    <h3 className="mb-2.5 text-sm font-semibold text-heading">
                      Interview Goals
                    </h3>
                    <div className="space-y-2">
                      {interviewResult.goals.map((g, i) => {
                        const pct = Math.round(g.progress_score * 10);
                        const gc = scoreColor(pct);
                        return (
                          <div key={i}>
                            <div className="mb-1 flex items-center justify-between">
                              <span className="text-xs text-muted-foreground truncate max-w-[70%]">
                                {g.title}
                              </span>
                              <span
                                className="font-mono text-[10px] tabular-nums"
                                style={{ color: gc }}
                              >
                                {g.completion_status}
                              </span>
                            </div>
                            <div
                              className="h-1.5 w-full overflow-hidden rounded-full"
                              style={{
                                background: "rgba(255,255,255,0.04)",
                              }}
                            >
                              <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${pct}%` }}
                                transition={{ duration: 0.8, delay: i * 0.06 }}
                                className="h-full rounded-full"
                                style={{ background: gc }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* ── Assessment tab ── */}
          {activeTab === "assessment" && (
            <motion.div
              key="assessment"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25 }}
              className="p-6"
            >
              <AssessmentView
                assessment={assessment}
                decisionColor={decisionColor}
                interviewResult={interviewResult}
                candidateId={id}
              />
            </motion.div>
          )}

          {/* ── Transcript tab ── */}
          {activeTab === "transcript" && (
            <motion.div
              key="transcript"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25 }}
              className="max-h-[600px] overflow-y-auto p-6"
            >
              {transcript && transcript.length > 0 ? (
                <div className="space-y-3">
                  {transcript.map((msg, i) => {
                    // speaker field: "candidate" / "interviewer" / "user" / "assistant"
                    const spk = (msg.speaker ?? "").toLowerCase();
                    const isCandidate =
                      spk === "candidate" || spk === "user";
                    return (
                      <div
                        key={i}
                        className={`flex ${
                          isCandidate ? "justify-end" : "justify-start"
                        }`}
                      >
                        <div className="max-w-[80%]">
                          <p
                            className="mb-1 text-[10px] uppercase tracking-wider"
                            style={{
                              color: isCandidate ? "#1C99BF" : "#556070",
                            }}
                          >
                            {isCandidate ? "Candidate" : "OZI"}
                          </p>
                          <div
                            className="rounded-2xl px-4 py-3 text-sm leading-relaxed"
                            style={
                              isCandidate
                                ? {
                                    background: "rgba(28,153,191,0.15)",
                                    border:
                                      "1px solid rgba(28,153,191,0.2)",
                                    color: "#E8EDF5",
                                  }
                                : {
                                    background: "rgba(255,255,255,0.04)",
                                    border:
                                      "1px solid rgba(255,255,255,0.05)",
                                    color: "#9CA3B0",
                                  }
                            }
                          >
                            {msg.text}
                          </div>
                          {/* Per-turn evaluation score badge */}
                          {msg.evaluation?.score != null && (
                            <div className="mt-1 flex justify-end">
                              <span
                                className="rounded-full px-2 py-0.5 text-[10px] font-mono tabular-nums"
                                style={{
                                  background: `${scoreColor(
                                    msg.evaluation.score * 10
                                  )}26`,
                                  color: scoreColor(
                                    msg.evaluation.score * 10
                                  ),
                                }}
                              >
                                {msg.evaluation.score}/10
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
                  No transcript available
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </GlassCard>
    </div>
  );
}

// ── GoalTile ───────────────────────────────────────────────────────────────────
function GoalTile({ goal, index }: {
  goal: { title: string; completion_status: string; progress_score: number; confidence_level: number; questions?: string[]; evidence?: { text: string }[] };
  index: number;
}) {
  const [open, setOpen] = useState(false);
  const status = goal.completion_status?.toLowerCase();
  const color = status === "passed" || status === "completed" ? "#34C28A"
    : status === "partial" ? "#F5B544" : "#F25C7C";
  const pct = Math.round(goal.progress_score ?? 0);
  const size = 54, stroke = 5, r = (size - stroke) / 2, c = 2 * Math.PI * r;
  const offset = c * (1 - pct / 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="cursor-pointer rounded-2xl p-4 transition-all"
      style={{ background: "rgba(8,34,52,0.7)", border: "1px solid rgba(255,255,255,0.08)" }}
      onClick={() => setOpen(o => !o)}
    >
      <div className="flex items-start gap-3">
        {/* Mini ring gauge */}
        <div className="relative shrink-0" style={{ width: size, height: size }}>
          <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
            <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} />
            <motion.circle
              cx={size/2} cy={size/2} r={r} fill="none"
              stroke={color} strokeWidth={stroke} strokeLinecap="round"
              strokeDasharray={c}
              initial={{ strokeDashoffset: c }}
              animate={{ strokeDashoffset: offset }}
              transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-mono text-[11px] font-bold tabular-nums" style={{ color }}>{pct}%</span>
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-heading leading-snug">{goal.title}</p>
          <span
            className="mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{ background: `${color}26`, color, border: `1px solid ${color}40` }}
          >
            {goal.completion_status}
          </span>
        </div>
        <ChevronDown className={`mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </div>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-3 space-y-2 border-t border-white/[0.06] pt-3">
              {goal.evidence && goal.evidence.length > 0 && (
                <div>
                  <p className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Evidence</p>
                  {goal.evidence.slice(0, 3).map((e, i) => (
                    <p key={i} className="text-xs text-muted-foreground leading-relaxed">• {e.text}</p>
                  ))}
                </div>
              )}
              {goal.questions && goal.questions.length > 0 && (
                <div>
                  <p className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Questions Asked</p>
                  {goal.questions.map((q, i) => (
                    <p key={i} className="text-xs text-muted-foreground leading-relaxed">• {q}</p>
                  ))}
                </div>
              )}
              <p className="text-[10px] text-muted-foreground">
                Confidence: <span className="font-mono font-semibold" style={{ color }}>{Math.round((goal.confidence_level ?? 0) * 100)}%</span>
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── AssessmentView ─────────────────────────────────────────────────────────────
function AssessmentView({
  assessment,
  decisionColor,
  interviewResult,
  candidateId,
}: {
  assessment: Record<string, unknown> | null;
  decisionColor: string;
  interviewResult: InterviewResult | undefined;
  candidateId: number;
}) {
  const [showAnnotated, setShowAnnotated] = useState(false);
  void decisionColor;

  const goals = interviewResult?.goals ?? [];
  const vision = interviewResult?.vision;
  const hasVideo = interviewResult?.has_video;
  const hasAnnotated = interviewResult?.has_annotated_video;

  // Parse strengths/areas from assessment
  const fr = (assessment?.final_ai_recommendation ?? {}) as Record<string, unknown>;
  const ov = (assessment?.overall_assessment ?? {}) as Record<string, unknown>;
  const summary = String(fr.summary ?? ov.summary ?? assessment?.summary ?? "");
  const strengths = (fr.strengths ?? ov.strengths ?? assessment?.strengths ?? []) as string[];
  const devAreas = (fr.development_areas ?? ov.development_areas ?? assessment?.development_areas ?? []) as string[];

  return (
    <div className="space-y-6">

      {/* ── Video ── */}
      {hasVideo && (
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-heading">
              <Video className="h-4 w-4" style={{ color: "#1C99BF" }} />
              Interview Recording
            </h3>
            {hasAnnotated && (
              <button
                onClick={() => setShowAnnotated(a => !a)}
                className="rounded-lg px-3 py-1 text-xs font-medium transition-colors"
                style={showAnnotated
                  ? { background: "rgba(28,153,191,0.15)", color: "#1C99BF", border: "1px solid rgba(28,153,191,0.3)" }
                  : { background: "rgba(255,255,255,0.04)", color: "#9CA3B0", border: "1px solid rgba(255,255,255,0.08)" }
                }
              >
                {showAnnotated ? "Annotated" : "Original"} ↕
              </button>
            )}
          </div>
          <div className="overflow-hidden rounded-2xl border border-white/[0.08]">
            <video
              src={getInterviewVideoUrl(candidateId, !!(showAnnotated && hasAnnotated))}
              controls
              className="w-full max-h-[360px] bg-black"
            />
          </div>
        </div>
      )}

      {/* ── Vision / proctoring report ── */}
      {vision && (
        <div>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-heading">
            <ShieldAlert className="h-4 w-4" style={{ color: "#F5B544" }} />
            Proctoring & Presence
          </h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: "Avg Engagement", value: vision.aggregate?.avg_engagement?.toFixed(1) ?? "—", color: "#34C28A" },
              { label: "Present Ratio", value: vision.aggregate?.present_ratio != null ? `${Math.round(vision.aggregate.present_ratio * 100)}%` : "—", color: "#1C99BF" },
              { label: "Frames Analyzed", value: String(vision.aggregate?.frames_analyzed ?? "—"), color: "#9CA3B0" },
              { label: "Phone Seen", value: vision.aggregate?.phone_seen ? "Yes" : "No", color: vision.aggregate?.phone_seen ? "#F25C7C" : "#34C28A" },
            ].map((stat) => (
              <div key={stat.label} className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{stat.label}</p>
                <p className="mt-1 font-mono text-xl font-bold tabular-nums" style={{ color: stat.color }}>{stat.value}</p>
              </div>
            ))}
          </div>
          {vision.aggregate?.integrity_flags && vision.aggregate.integrity_flags.length > 0 && (
            <div className="mt-3 rounded-xl p-4" style={{ background: "rgba(242,92,124,0.06)", border: "1px solid rgba(242,92,124,0.2)" }}>
              <p className="mb-1 text-xs font-semibold" style={{ color: "#F25C7C" }}>Integrity Flags</p>
              {vision.aggregate.integrity_flags.map((f, i) => (
                <p key={i} className="text-xs text-muted-foreground">• {f}</p>
              ))}
            </div>
          )}
          {vision.overall_summary && (
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{vision.overall_summary}</p>
          )}
        </div>
      )}

      {/* ── Goals ── */}
      {goals.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-heading">Interview Goals</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {goals.map((goal, i) => (
              <GoalTile key={i} goal={goal} index={i} />
            ))}
          </div>
        </div>
      )}

      {/* ── Strengths + dev areas ── */}
      {(strengths.length > 0 || devAreas.length > 0) && (
        <div className="grid gap-4 sm:grid-cols-2">
          {strengths.length > 0 && (
            <div>
              <h3 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-heading">
                <Check className="h-4 w-4" style={{ color: "#34C28A" }} /> Strengths
              </h3>
              <div className="space-y-2">
                {strengths.map((s, i) => (
                  <div key={i} className="flex gap-2.5 rounded-lg p-3"
                    style={{ border: "1px solid rgba(52,194,138,0.15)", background: "rgba(52,194,138,0.06)" }}>
                    <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#34C28A" }} />
                    <p className="text-xs text-muted-foreground leading-relaxed">{s}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {devAreas.length > 0 && (
            <div>
              <h3 className="mb-2.5 flex items-center gap-2 text-sm font-semibold text-heading">
                <TrendingUp className="h-4 w-4" style={{ color: "#F5B544" }} /> Development Areas
              </h3>
              <div className="space-y-2">
                {devAreas.map((d, i) => (
                  <div key={i} className="flex gap-2.5 rounded-lg p-3"
                    style={{ border: "1px solid rgba(245,181,68,0.15)", background: "rgba(245,181,68,0.06)" }}>
                    <TrendingUp className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#F5B544" }} />
                    <p className="text-xs text-muted-foreground leading-relaxed">{d}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Summary ── */}
      {summary && (
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">AI Summary</p>
          <p className="text-sm leading-relaxed text-muted-foreground">{summary}</p>
        </div>
      )}

      {/* Empty state */}
      {!hasVideo && !vision && goals.length === 0 && !assessment && (
        <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
          No assessment data available
        </div>
      )}
    </div>
  );
}
