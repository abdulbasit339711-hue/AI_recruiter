"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import toast from "react-hot-toast";
import { Loader2, Send, ClipboardCheck } from "lucide-react";

import { api, getInterviewAudioUrl, type InterviewResult, type TurnEvaluation } from "@/lib/api";

/**
 * Renders a candidate's AI-interview results (status, goals, assessment,
 * transcript) plus a send/resend-invite action. Shared by the admin candidate
 * modal and the standalone /admin/candidates/[id]/interview page.
 */
export function InterviewPanel({ candidateId }: { candidateId: number }) {
  const [result, setResult] = useState<InterviewResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setResult(await api.getInterviewResult(candidateId));
    } catch {
      setResult({ has_interview: false });
    } finally {
      setLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    if (!Number.isNaN(candidateId) && candidateId > 0) load();
  }, [candidateId, load]);

  async function sendInvite() {
    setSending(true);
    try {
      const res = await api.triggerInterviewInvite(candidateId);
      toast.success("Interview invite sent");
      console.info("interview link:", res.link);
    } catch (e) {
      toast.error("Failed to send invite");
      console.error(e);
    } finally {
      setSending(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-slate-400">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading interview…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-primary">AI Interview</h3>
        <button
          onClick={sendInvite}
          disabled={sending}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-60"
        >
          {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          {result?.has_interview ? "Resend invite" : "Send invite"}
        </button>
      </div>

      {!result?.has_interview ? (
        <div className="rounded-xl border border-dashed border-white/15 p-10 text-center text-sm text-slate-400">
          No interview yet. Send the invite — the candidate receives a time-limited link by email.
        </div>
      ) : (
        <>
          <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Status" value={result.session?.status ?? "—"} />
            <Stat label="Role" value={result.session?.role_type ?? "—"} />
            <Stat
              label="Goals completed"
              value={`${result.session?.completed_goals ?? 0}/${result.session?.total_goals ?? 0}`}
            />
            <Stat
              label="Avg progress"
              value={`${Math.round((Number(result.session?.average_progress) || 0) * 100)}%`}
            />
          </section>

          {result.session?.overall_assessment && (
            <FinalAssessment raw={result.session.overall_assessment} />
          )}

          {result.metrics && (
            <section className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <h4 className="mb-3 text-sm font-semibold">Usage &amp; cost (tokens)</h4>
              <div className="mb-1 text-[11px] uppercase tracking-wide text-slate-400">Interview</div>
              <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
                <Stat label="STT (est.)" value={result.metrics.interview.stt_tokens.toLocaleString()} />
                <Stat label="LLM in" value={result.metrics.interview.llm_input_tokens.toLocaleString()} />
                <Stat label="LLM out" value={result.metrics.interview.llm_output_tokens.toLocaleString()} />
                <Stat label="TTS (est.)" value={result.metrics.interview.tts_tokens.toLocaleString()} />
                <Stat label="Total" value={result.metrics.interview.total_tokens.toLocaleString()} />
              </div>
              <div className="mt-3 mb-1 text-[11px] uppercase tracking-wide text-slate-400">Resume scoring</div>
              <div className="grid grid-cols-3 gap-3">
                <Stat label="LLM in" value={result.metrics.scoring.prompt_tokens.toLocaleString()} />
                <Stat label="LLM out" value={result.metrics.scoring.completion_tokens.toLocaleString()} />
                <Stat label="Scoring cost" value={`$${result.metrics.scoring.cost_usd.toFixed(4)}`} />
              </div>
              <p className="mt-3 text-xs text-slate-400">
                Interview LLM cost: ${result.metrics.interview.cost_usd.toFixed(4)} · STT/TTS token
                counts are character-based estimates.
              </p>
            </section>
          )}

          {result.has_audio && (
            <section className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <h4 className="mb-3 text-sm font-semibold">Interview recording</h4>
              <audio controls preload="none" className="w-full" src={getInterviewAudioUrl(candidateId)}>
                Your browser does not support audio playback.
              </audio>
            </section>
          )}

          <section className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
            <h4 className="mb-3 text-sm font-semibold">Goal scores</h4>
            <ul className="space-y-3">
              {(result.goals ?? []).map((g) => (
                <li key={g.title}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span>{g.title}</span>
                    <span className="text-slate-400">
                      {g.completion_status} · {Math.round((Number(g.progress_score) || 0) * 100)}%
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-blue-500"
                      style={{ width: `${Math.min(100, Math.round((Number(g.progress_score) || 0) * 100))}%` }}
                    />
                  </div>
                </li>
              ))}
              {(result.goals ?? []).length === 0 && (
                <li className="text-xs text-slate-400">No goals recorded.</li>
              )}
            </ul>
          </section>

          <section className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
            <h4 className="mb-3 text-sm font-semibold">Transcript</h4>
            <div className="max-h-[420px] space-y-3 overflow-y-auto pr-2">
              {(result.transcript ?? []).map((t, i) => (
                <div key={i} className={`flex flex-col ${t.speaker === "agent" ? "items-start" : "items-end"}`}>
                  <div
                    className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                      t.speaker === "agent" ? "bg-slate-800 text-slate-200" : "bg-blue-600 text-white"
                    }`}
                  >
                    {t.text}
                  </div>
                  {t.speaker !== "agent" && t.evaluation && (
                    <TurnEvalBadge ev={t.evaluation} />
                  )}
                </div>
              ))}
              {(result.transcript ?? []).length === 0 && (
                <p className="text-xs text-slate-400">No transcript recorded.</p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-sm font-semibold">{value}</div>
    </div>
  );
}

/** Compact per-answer evaluation shown under a candidate message. */
function TurnEvalBadge({ ev }: { ev: TurnEvaluation }) {
  const score = typeof ev.score === "number" ? ev.score : null;
  const color =
    score == null ? "text-slate-400" : score >= 7 ? "text-emerald-400" : score >= 4 ? "text-amber-400" : "text-rose-400";
  const strength = ev.strengths?.[0];
  const weakness = ev.weaknesses?.[0];
  return (
    <div className="mt-1 max-w-[80%] text-right text-[11px] text-slate-400">
      {score != null && <span className={`font-semibold ${color}`}>{score}/10</span>}
      {ev.depth && <span> · {ev.depth}</span>}
      {strength && <span> · 👍 {strength}</span>}
      {weakness && <span> · 👎 {weakness}</span>}
    </div>
  );
}

/** Renders the final transcript evaluation. The value is JSON from the voice agent; older
 *  sessions may hold plain text, in which case we show it verbatim. */
function FinalAssessment({ raw }: { raw: string }) {
  let parsed: Record<string, unknown> | null = null;
  try {
    const p = JSON.parse(raw);
    if (p && typeof p === "object") parsed = p as Record<string, unknown>;
  } catch {
    parsed = null;
  }

  const Section = ({ children }: { children: ReactNode }) => (
    <section className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <ClipboardCheck className="h-4 w-4" /> Final evaluation
      </h4>
      {children}
    </section>
  );

  if (!parsed) {
    return (
      <Section>
        <p className="text-sm text-slate-300">{raw}</p>
      </Section>
    );
  }

  const overall = (parsed.overall_assessment ?? {}) as Record<string, unknown>;
  const rec = String(overall.hiring_recommendation ?? "").replace(/_/g, " ");
  const perf = Number(overall.candidate_performance);
  const coverage = Number(overall.goal_coverage_rate);
  const strengths = (overall.strengths as string[]) ?? [];
  const improvements = (overall.areas_for_improvement as string[]) ?? [];
  const goals = (parsed.goal_assessments as Record<string, unknown>[]) ?? [];
  const recColor = /strong_hire|^hire/i.test(String(overall.hiring_recommendation))
    ? "bg-emerald-600"
    : /no_hire/i.test(String(overall.hiring_recommendation))
    ? "bg-rose-600"
    : "bg-slate-600";

  return (
    <Section>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {rec && (
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold text-white ${recColor}`}>
            {rec}
          </span>
        )}
        {!Number.isNaN(perf) && (
          <span className="text-xs text-slate-300">Performance: {Math.round(perf * 100)}%</span>
        )}
        {!Number.isNaN(coverage) && (
          <span className="text-xs text-slate-300">Goal coverage: {Math.round(coverage * 100)}%</span>
        )}
      </div>
      {strengths.length > 0 && (
        <div className="mb-2">
          <div className="text-[11px] uppercase tracking-wide text-emerald-400">Strengths</div>
          <ul className="ml-4 list-disc text-sm text-slate-300">
            {strengths.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      )}
      {improvements.length > 0 && (
        <div className="mb-2">
          <div className="text-[11px] uppercase tracking-wide text-amber-400">Areas for improvement</div>
          <ul className="ml-4 list-disc text-sm text-slate-300">
            {improvements.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      )}
      {goals.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-slate-400">Per-goal assessment ({goals.length})</summary>
          <ul className="mt-2 space-y-2">
            {goals.map((g, i) => (
              <li key={i} className="rounded-lg border border-white/10 p-2 text-sm">
                <div className="flex justify-between">
                  <span className="font-medium">{String(g.goal_title ?? "Goal")}</span>
                  <span className="text-slate-400">
                    {Math.round(Number(g.final_score ?? 0) * 100)}% · {String(g.completion_status ?? "")}
                  </span>
                </div>
                {Array.isArray(g.key_quotes) && (g.key_quotes as string[]).length > 0 && (
                  <p className="mt-1 text-xs italic text-slate-400">“{(g.key_quotes as string[])[0]}”</p>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Section>
  );
}
