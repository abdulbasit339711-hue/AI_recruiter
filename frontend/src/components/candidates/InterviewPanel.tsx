"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import toast from "react-hot-toast";
import { Loader2, Send, ClipboardCheck, FileText, Upload, Inbox } from "lucide-react";

import {
  api,
  getInterviewAudioUrl,
  getInterviewVideoUrl,
  getCandidateReportUrl,
  type InterviewResult,
  type TurnEvaluation,
  type VisionReport,
  type CommunicationAnalysis,
} from "@/lib/api";
import { FadeIn, Stagger, StaggerItem } from "@/components/ui/motion";

/**
 * Renders a candidate's AI-interview results (status, goals, assessment,
 * transcript) plus a send/resend-invite action. Shared by the admin candidate
 * modal and the standalone /admin/candidates/[id]/interview page.
 */
export function InterviewPanel({ candidateId }: { candidateId: number }) {
  const [result, setResult] = useState<InterviewResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const resumeInputRef = useRef<HTMLInputElement | null>(null);

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

  async function onResumeSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file later
    if (!file) return;
    setUploading(true);
    try {
      await api.replaceCandidateResume(candidateId, file);
      toast.success("Résumé attached — re-scoring queued");
    } catch (err) {
      const msg = (err as { message?: string })?.message || "Upload failed";
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4" aria-busy="true">
        <div className="flex items-center justify-between">
          <div className="h-4 w-28 animate-pulse rounded bg-foreground/[0.07]" />
          <div className="flex gap-2">
            <div className="h-8 w-28 animate-pulse rounded-lg bg-foreground/[0.05]" />
            <div className="h-8 w-24 animate-pulse rounded-lg bg-foreground/[0.05]" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-xl bg-foreground/[0.04]" />
          ))}
        </div>
        <div className="h-32 animate-pulse rounded-xl bg-foreground/[0.03]" />
        <div className="h-48 animate-pulse rounded-xl bg-foreground/[0.03]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-heading">AI interview</h3>
        <div className="flex items-center gap-2">
          {/* Attach / replace the candidate's résumé and re-score (works even if they had none). */}
          <input
            ref={resumeInputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={onResumeSelected}
          />
          <button
            onClick={() => resumeInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-white/5 disabled:opacity-60"
          >
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Replace résumé
          </button>
          {/* One-click report (résumé score + interview assessment + transcript). */}
          {result?.has_interview && (
            <a
              href={getCandidateReportUrl(candidateId, "pdf")}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-white/5"
            >
              <FileText className="h-4 w-4" /> Report
            </a>
          )}
          <button
            onClick={sendInvite}
            disabled={sending}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-60"
          >
            {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            {result?.has_interview ? "Resend invite" : "Send invite"}
          </button>
        </div>
      </div>

      {!result?.has_interview ? (
        <FadeIn>
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border p-10 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-foreground/[0.05] text-muted-foreground">
              <Inbox className="h-6 w-6" strokeWidth={1.75} />
            </span>
            <p className="text-sm font-medium text-heading">No interview yet</p>
            <p className="max-w-xs text-xs text-muted-foreground">
              Send the invite — the candidate receives a time-limited link by email and their
              results will appear here.
            </p>
            <button
              onClick={sendInvite}
              disabled={sending}
              className="mt-1 inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-60"
            >
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Send invite
            </button>
          </div>
        </FadeIn>
      ) : (
        <Stagger className="space-y-6" gap={0.06}>
          <StaggerItem>
            <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Status" value={result.session?.status ?? "—"} />
              <Stat label="Role" value={result.session?.role_type ?? "—"} />
              <Stat
                label="Goals completed"
                value={`${result.session?.completed_goals ?? 0}/${result.session?.total_goals ?? 0}`}
                mono
              />
              <Stat
                label="Avg progress"
                value={`${Math.round((Number(result.session?.average_progress) || 0) * 100)}%`}
                mono
              />
            </section>
          </StaggerItem>

          {result.session?.overall_assessment && (
            <StaggerItem>
              <FinalAssessment raw={result.session.overall_assessment} />
            </StaggerItem>
          )}

          {result.metrics && (
            <StaggerItem>
            <section className="rounded-xl glass-tile p-4">
              <h4 className="mb-3 text-sm font-semibold">Usage &amp; cost (tokens)</h4>
              <div className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">Interview</div>
              <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
                <Stat label="STT (est.)" value={result.metrics.interview.stt_tokens.toLocaleString()} mono />
                <Stat label="LLM in" value={result.metrics.interview.llm_input_tokens.toLocaleString()} mono />
                <Stat label="LLM out" value={result.metrics.interview.llm_output_tokens.toLocaleString()} mono />
                <Stat label="TTS (est.)" value={result.metrics.interview.tts_tokens.toLocaleString()} mono />
                <Stat label="Total" value={result.metrics.interview.total_tokens.toLocaleString()} mono />
              </div>
              <div className="mt-3 mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">Resume scoring</div>
              <div className="grid grid-cols-3 gap-3">
                <Stat label="LLM in" value={result.metrics.scoring.prompt_tokens.toLocaleString()} mono />
                <Stat label="LLM out" value={result.metrics.scoring.completion_tokens.toLocaleString()} mono />
                <Stat label="Scoring cost" value={`$${result.metrics.scoring.cost_usd.toFixed(4)}`} mono />
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                Interview LLM cost: ${result.metrics.interview.cost_usd.toFixed(4)} · STT/TTS token
                counts are character-based estimates.
              </p>
            </section>
            </StaggerItem>
          )}

          {result.has_video && (
            <StaggerItem>
              <VideoSection
                candidateId={candidateId}
                hasAnnotated={!!result.has_annotated_video}
                onRefresh={load}
              />
            </StaggerItem>
          )}

          {result.has_audio && (
            <StaggerItem>
              <section className="rounded-xl glass-tile p-4">
                <h4 className="mb-3 text-sm font-semibold text-heading">
                  {result.has_video ? "Audio track" : "Interview recording"}
                </h4>
                <audio controls preload="none" className="w-full" src={getInterviewAudioUrl(candidateId)}>
                  Your browser does not support audio playback.
                </audio>
                <div className="mt-2 text-right">
                  <a href={getInterviewAudioUrl(candidateId)} download className="text-[11px] font-medium text-primary hover:underline">
                    Download audio
                  </a>
                </div>
              </section>
            </StaggerItem>
          )}

          {result.vision && (
            <StaggerItem>
              <VisionSection vision={result.vision} />
            </StaggerItem>
          )}

          {(result.transcript?.length ?? 0) > 0 && (
            <StaggerItem>
              <CommunicationSection
                candidateId={candidateId}
                autoLoad={!!result.has_communication}
              />
            </StaggerItem>
          )}

          <StaggerItem>
            <section className="rounded-xl glass-tile p-4">
              <h4 className="mb-3 text-sm font-semibold text-heading">Goals · questions &amp; answers</h4>
              <ul className="space-y-3">
                {(result.goals ?? []).map((g) => (
                  <GoalRow key={g.title} goal={g} />
                ))}
                {(result.goals ?? []).length === 0 && (
                  <li className="text-xs text-muted-foreground">No goals recorded.</li>
                )}
              </ul>
            </section>
          </StaggerItem>

          <StaggerItem>
            <section className="rounded-xl glass-tile p-4">
              <h4 className="mb-3 text-sm font-semibold text-heading">Transcript</h4>
              <div className="max-h-[420px] space-y-3 overflow-y-auto pr-2">
                {(result.transcript ?? []).map((t, i) => (
                  <div key={i} className={`flex flex-col ${t.speaker === "agent" ? "items-start" : "items-end"}`}>
                    <div
                      className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                        t.speaker === "agent" ? "bg-foreground/10 text-foreground" : "bg-primary text-white"
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
                  <p className="text-xs text-muted-foreground">No transcript recorded.</p>
                )}
              </div>
            </section>
          </StaggerItem>
        </Stagger>
      )}
    </div>
  );
}

/** Interview video playback with a raw / annotated (YOLO boxes) toggle. */
function VideoSection({
  candidateId, hasAnnotated, onRefresh,
}: {
  candidateId: number; hasAnnotated: boolean; onRefresh: () => void;
}) {
  const [annotated, setAnnotated] = useState(false);
  const [busy, setBusy] = useState(false);

  async function generate() {
    setBusy(true);
    try {
      const res = await api.annotateInterviewVideo(candidateId);
      if (res.already) {
        toast.success("Annotated video ready");
        setAnnotated(true);
        onRefresh();
      } else {
        toast.success("Annotating video… this runs in the background. Refresh in a moment.");
      }
    } catch {
      toast.error("Couldn't start annotation");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl glass-tile p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-heading">Interview video</h4>
        <div className="flex items-center gap-2">
          {hasAnnotated && (
            <div className="flex rounded-lg border border-border p-0.5 text-xs">
              <button
                onClick={() => setAnnotated(false)}
                className={`rounded-md px-2 py-1 ${!annotated ? "bg-primary text-white" : "text-muted-foreground"}`}
              >
                Raw
              </button>
              <button
                onClick={() => setAnnotated(true)}
                className={`rounded-md px-2 py-1 ${annotated ? "bg-primary text-white" : "text-muted-foreground"}`}
              >
                Annotated
              </button>
            </div>
          )}
          {!hasAnnotated && (
            <button
              onClick={generate}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs text-foreground hover:bg-foreground/5 disabled:opacity-50"
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              Generate annotated
            </button>
          )}
        </div>
      </div>
      <video
        key={annotated ? "annotated" : "raw"}
        controls
        playsInline
        preload="metadata"
        className="w-full rounded-lg bg-black"
        src={getInterviewVideoUrl(candidateId, annotated)}
      >
        Your browser does not support video playback.
      </video>
      <div className="mt-2 flex items-center justify-between gap-2">
        <p className="text-[11px] text-muted-foreground">
          {annotated
            ? "Annotated: YOLO detection boxes (candidate / phone / objects) drawn per frame — advisory only."
            : "Raw candidate video as recorded during the interview."}
        </p>
        <a
          href={getInterviewVideoUrl(candidateId, annotated)}
          download
          className="shrink-0 text-[11px] font-medium text-primary hover:underline"
        >
          Download {annotated ? "annotated" : "video"}
        </a>
      </div>
    </section>
  );
}

const FLAG_LABELS: Record<string, string> = {
  candidate_absent: "Candidate absent",
  phone_visible: "Phone visible",
  multiple_people: "Multiple people",
};

/** Advisory video-evaluation report: presence, engagement, integrity, delivery. */
function VisionSection({ vision }: { vision: VisionReport }) {
  const agg = vision.aggregate ?? {};
  const flags = agg.integrity_flags ?? [];
  const present = Math.round((agg.present_ratio ?? 0) * 100);
  const engagement = agg.avg_engagement ?? 0; // 0–3 scale
  const engagementPct = Math.round((engagement / 3) * 100);
  const obs = (vision.observations ?? []).filter((o) => o.summary || o.delivery_notes);

  return (
    <section className="rounded-xl glass-tile p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-heading">Video evaluation</h4>
        <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
          {vision.backend ?? "vision"} · advisory
        </span>
      </div>

      {/* Video-level narrative summary (synthesized across all frames) */}
      {vision.overall_summary && (
        <p className="mb-3 rounded-lg bg-foreground/[0.04] p-3 text-sm leading-relaxed text-foreground">
          {vision.overall_summary}
        </p>
      )}

      {/* Headline metrics */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Presence" value={`${present}%`} mono />
        <Stat label="Engagement" value={`${engagementPct}%`} mono />
        <Stat label="Max people" value={String(agg.max_people_count ?? 0)} mono />
        <Stat label="Frames" value={`${agg.frames_analyzed ?? 0} / ${agg.frames_detected ?? 0}`} mono />
      </div>

      {/* Integrity flags */}
      <div className="mt-3">
        <div className="mb-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">Integrity</div>
        {flags.length === 0 ? (
          <span className="inline-flex items-center rounded-full bg-strong/15 px-2.5 py-1 text-xs text-strong">
            No integrity flags
          </span>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {flags.map((f) => (
              <span key={f} className="inline-flex items-center rounded-full bg-weak/15 px-2.5 py-1 text-xs text-weak">
                {FLAG_LABELS[f] ?? f}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Timed observations */}
      {obs.length > 0 && (
        <details className="mt-3" open>
          <summary className="cursor-pointer text-[11px] uppercase tracking-wide text-muted-foreground">
            Per-frame notes ({obs.length})
          </summary>
          <ul className="mt-2 space-y-2">
            {obs.map((o, i) => (
              <li key={i} className="rounded-lg bg-foreground/[0.03] p-2.5 text-xs">
                <div className="mb-0.5 flex items-center gap-2 text-muted-foreground">
                  <span className="font-mono tabular-nums">{Math.round(o.t ?? 0)}s</span>
                  {typeof o.engagement === "number" && <span>· engagement {o.engagement}/3</span>}
                  {o.looking_away && <span className="text-promising">· looking away</span>}
                  {o.present === false && <span className="text-weak">· absent</span>}
                </div>
                {o.summary && <p className="text-foreground">{o.summary}</p>}
                {o.delivery_notes && <p className="mt-0.5 text-muted-foreground">Delivery: {o.delivery_notes}</p>}
                {(o.gestures || o.posture || o.facial_expression || o.eye_contact) && (
                  <p className="mt-0.5 text-muted-foreground">
                    {[
                      o.posture && `posture: ${o.posture}`,
                      o.gestures && `gestures: ${o.gestures}`,
                      o.facial_expression && `expression: ${o.facial_expression}`,
                      o.eye_contact && `eye contact: ${o.eye_contact}`,
                    ].filter(Boolean).join(" · ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

/** Talking style / fluency / fillers — LLM analysis over the transcript. */
function CommunicationSection({ candidateId, autoLoad }: { candidateId: number; autoLoad: boolean }) {
  const [data, setData] = useState<CommunicationAnalysis | null>(null);
  const [busy, setBusy] = useState(false);

  const run = useCallback(async (refresh = false) => {
    setBusy(true);
    try {
      setData(await api.getCommunicationAnalysis(candidateId, refresh));
    } catch {
      toast.error("Couldn't analyze communication");
    } finally {
      setBusy(false);
    }
  }, [candidateId]);

  useEffect(() => {
    if (autoLoad) run(false);
  }, [autoLoad, run]);

  const a = data?.analysis ?? null;
  const f = data?.fillers;
  const rows: [string, string | undefined][] = a
    ? [
        ["Talking style", a.talking_style],
        ["Fluency", a.fluency],
        ["Pace", a.pace],
        ["Clarity", a.clarity],
        ["Confidence", a.confidence],
        ["Conciseness", a.conciseness],
        ["Language & phrasing", a.language_phrasing],
        ["Accent", a.accent_note],
      ]
    : [];

  return (
    <section className="rounded-xl glass-tile p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-heading">Communication &amp; delivery</h4>
        <button
          onClick={() => run(true)}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs text-foreground hover:bg-foreground/5 disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
          {data ? "Re-analyze" : "Analyze"}
        </button>
      </div>

      {!data && !busy && (
        <p className="text-xs text-muted-foreground">
          Analyze talking style, fluency, pace, clarity, filler usage, and phrasing from the transcript.
        </p>
      )}
      {busy && !data && (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Analyzing transcript…
        </p>
      )}

      {f && (
        <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
          <Stat label="Filler words" value={String(f.filler_count)} mono />
          <Stat label="Filler rate" value={`${f.filler_rate_pct}%`} mono />
          <Stat label="Words spoken" value={String(f.total_words)} mono />
        </div>
      )}

      {f && Object.keys(f.by_filler ?? {}).length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {Object.entries(f.by_filler).map(([w, c]) => (
            <span key={w} className="rounded-full bg-foreground/[0.06] px-2 py-0.5 text-[11px] text-muted-foreground">
              “{w}” ×{c}
            </span>
          ))}
        </div>
      )}

      {a?.error && <p className="text-xs text-weak">{a.error}</p>}

      {rows.filter(([, v]) => v).length > 0 && (
        <dl className="space-y-2">
          {rows.filter(([, v]) => v).map(([label, v]) => (
            <div key={label} className="grid grid-cols-[120px_1fr] gap-2 text-sm">
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
              <dd className="text-foreground">{v}</dd>
            </div>
          ))}
        </dl>
      )}

      {a?.accent_note && (
        <p className="mt-3 text-[11px] text-faint">
          Note: this is a text analysis of the transcript — true accent classification requires audio modelling.
        </p>
      )}
    </section>
  );
}

function Stat({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0 rounded-xl glass-tile p-3">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div
        className={`mt-1 truncate text-sm font-semibold text-heading ${mono ? "font-mono tabular-nums" : ""}`}
        title={value}
      >
        {value}
      </div>
    </div>
  );
}

/** One goal with its progress, planned questions, and the candidate's answer evidence. */
function GoalRow({ goal }: { goal: NonNullable<InterviewResult["goals"]>[number] }) {
  const pct = Math.min(100, Math.round((Number(goal.progress_score) || 0) * 100));
  const questions = goal.questions ?? [];
  const evidence = goal.evidence ?? [];
  const hasDetail = questions.length > 0 || evidence.length > 0;
  return (
    <li>
      <div className="mb-1 flex justify-between gap-2 text-xs">
        <span className="min-w-0 truncate text-foreground" title={goal.title}>{goal.title}</span>
        <span className="shrink-0 text-muted-foreground">
          {goal.completion_status} · <span className="font-mono font-semibold tabular-nums text-heading">{pct}%</span>
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-foreground/10">
        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
      {hasDetail && (
        <details className="mt-2">
          <summary className="cursor-pointer text-[11px] text-muted-foreground">Questions &amp; answers</summary>
          {questions.length > 0 && (
            <div className="mt-2">
              <div className="text-[11px] uppercase tracking-wide text-faint">Questions</div>
              <ul className="ml-4 mt-1 list-disc text-xs text-foreground">
                {questions.map((q, i) => <li key={i}>{q}</li>)}
              </ul>
            </div>
          )}
          {evidence.length > 0 && (
            <div className="mt-2">
              <div className="text-[11px] uppercase tracking-wide text-faint">Candidate answers</div>
              <ul className="mt-1 space-y-1">
                {evidence.map((e, i) => (
                  <li
                    key={i}
                    className="rounded-md glass-tile px-2 py-1 text-xs italic text-foreground"
                  >
                    “{e.text}”
                  </li>
                ))}
              </ul>
            </div>
          )}
        </details>
      )}
    </li>
  );
}

/** Compact per-answer evaluation shown under a candidate message. */
function TurnEvalBadge({ ev }: { ev: TurnEvaluation }) {
  const score = typeof ev.score === "number" ? ev.score : null;
  const color =
    score == null ? "text-muted-foreground" : score >= 7 ? "text-strong" : score >= 4 ? "text-promising" : "text-weak";
  const strength = ev.strengths?.[0];
  const weakness = ev.weaknesses?.[0];
  return (
    <div className="mt-1 max-w-[80%] text-right text-[11px] text-muted-foreground">
      {score != null && <span className={`font-mono font-semibold tabular-nums ${color}`}>{score}/10</span>}
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
    <section className="rounded-xl glass-tile p-4">
      <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-heading">
        <ClipboardCheck className="h-4 w-4 text-primary" /> Final evaluation
      </h4>
      {children}
    </section>
  );

  if (!parsed) {
    return (
      <Section>
        <p className="text-sm text-foreground">{raw}</p>
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
  const recBg = /strong_hire|^hire/i.test(String(overall.hiring_recommendation))
    ? "var(--strong)"
    : /no_hire/i.test(String(overall.hiring_recommendation))
    ? "var(--weak)"
    : "color-mix(in srgb, var(--muted-foreground) 55%, transparent)";

  return (
    <Section>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {rec && (
          <span
            className="rounded-full px-2 py-0.5 text-xs font-semibold text-white"
            style={{ background: recBg }}
          >
            {rec}
          </span>
        )}
        {!Number.isNaN(perf) && (
          <span className="text-xs text-foreground">
            Performance: <span className="font-mono font-semibold tabular-nums">{Math.round(perf * 100)}%</span>
          </span>
        )}
        {!Number.isNaN(coverage) && (
          <span className="text-xs text-foreground">
            Goal coverage: <span className="font-mono font-semibold tabular-nums">{Math.round(coverage * 100)}%</span>
          </span>
        )}
      </div>
      {strengths.length > 0 && (
        <div className="mb-2">
          <div className="text-[11px] uppercase tracking-wide text-strong">Strengths</div>
          <ul className="ml-4 list-disc text-sm text-foreground">
            {strengths.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      )}
      {improvements.length > 0 && (
        <div className="mb-2">
          <div className="text-[11px] uppercase tracking-wide text-promising">Areas for improvement</div>
          <ul className="ml-4 list-disc text-sm text-foreground">
            {improvements.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      )}
      {goals.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-muted-foreground">Per-goal assessment ({goals.length})</summary>
          <ul className="mt-2 space-y-2">
            {goals.map((g, i) => (
              <li key={i} className="rounded-lg border border-border p-2 text-sm">
                <div className="flex justify-between gap-2">
                  <span className="font-medium text-heading">{String(g.goal_title ?? "Goal")}</span>
                  <span className="shrink-0 text-muted-foreground">
                    <span className="font-mono font-semibold tabular-nums text-heading">
                      {Math.round(Number(g.final_score ?? 0) * 100)}%
                    </span>{" "}
                    · {String(g.completion_status ?? "")}
                  </span>
                </div>
                {Array.isArray(g.key_quotes) && (g.key_quotes as string[]).length > 0 && (
                  <p className="mt-1 text-xs italic text-muted-foreground">“{(g.key_quotes as string[])[0]}”</p>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Section>
  );
}
