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
import { FadeIn } from "@/components/ui/motion";

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
  const [activeTab, setActiveTab] = useState<"overview" | "assessment" | "transcript">("overview");
  const resumeInputRef = useRef<HTMLInputElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Seek the interview video to a timestamp (evidence-linked vision observations).
  const seekTo = useCallback((seconds: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.scrollIntoView({ behavior: "smooth", block: "center" });
    v.currentTime = Math.max(0, seconds);
    v.play?.().catch(() => {});
  }, []);

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
    e.target.value = "";
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

  // Parse overall_assessment JSON once, used by Overview tab
  let parsedAssessment: Record<string, unknown> | null = null;
  if (result?.session?.overall_assessment) {
    try {
      const p = JSON.parse(result.session.overall_assessment);
      if (p && typeof p === "object") parsedAssessment = p as Record<string, unknown>;
    } catch {
      parsedAssessment = null;
    }
  }

  const fr = parsedAssessment
    ? ((parsedAssessment.final_ai_recommendation ?? {}) as Record<string, unknown>)
    : null;
  const ov = parsedAssessment
    ? ((parsedAssessment.overall_assessment ?? {}) as Record<string, unknown>)
    : null;
  const keyStrengths: string[] =
    (fr?.key_strengths as string[]) ?? (ov?.strengths as string[]) ?? [];
  const devAreas: string[] =
    (fr?.development_areas as string[]) ?? (ov?.areas_for_improvement as string[]) ?? [];

  // KPI strip values
  const speaking = result?.speaking;
  const session = result?.session;
  const visionObs = result?.vision?.observations ?? [];
  const avgEngagement =
    visionObs.length > 0
      ? (
          visionObs.reduce(
            (acc, o) => acc + (typeof o.engagement === "number" ? o.engagement : 0),
            0
          ) / visionObs.length
        ).toFixed(1)
      : null;

  const transcriptCount = result?.transcript?.length ?? 0;

  return (
    <div className="space-y-4">
      {/* ── Header row: title + action buttons ── */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-heading">AI interview</h3>
        <div className="flex items-center gap-2">
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
        <div className="space-y-4">
          {/* ── A. Always-visible KPI strip ── */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat
              label="Duration"
              value={speaking?.duration_seconds != null ? fmtTime(speaking.duration_seconds) : "—"}
              mono
            />
            <Stat
              label="Candidate talk"
              value={speaking?.candidate_talk_ratio_pct != null ? `${Math.round(speaking.candidate_talk_ratio_pct)}%` : "—"}
              mono
            />
            <Stat
              label="Goals covered"
              value={session ? `${session.completed_goals ?? 0}/${session.total_goals ?? 0}` : "—"}
              mono
            />
            <Stat
              label="Engagement"
              value={avgEngagement != null ? `${avgEngagement}/5` : "—"}
              mono
            />
          </div>

          {/* ── Phase Assessment card ── */}
          {(session?.phase1_score != null || session?.current_phase) && (
            <PhaseAssessmentCard
              phase1Score={session.phase1_score ?? null}
              currentPhase={session.current_phase ?? null}
              goalsCompleted={session.completed_goals ?? 0}
              totalGoals={session.total_goals ?? 0}
            />
          )}

          {/* ── B. Tab bar ── */}
          <div className="flex gap-0 border-b border-border">
            {(
              [
                { id: "overview", label: "Overview" },
                { id: "assessment", label: "Assessment" },
                { id: "transcript", label: `Transcript (${transcriptCount})` },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? "border-b-2 border-primary text-primary font-semibold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* ── C. Tab content ── */}

          {/* Overview tab */}
          {activeTab === "overview" && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {/* Left column */}
                <div className="space-y-4">
                  {/* Strengths + dev areas pills */}
                  {(keyStrengths.length > 0 || devAreas.length > 0) && (
                    <div className="rounded-xl glass-tile p-4 space-y-3">
                      {keyStrengths.length > 0 && (
                        <div>
                          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-strong">
                            Key Strengths
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {keyStrengths.map((s, i) => (
                              <span
                                key={i}
                                className="inline-flex items-center gap-1 rounded-full bg-strong/15 px-2.5 py-1 text-xs text-strong"
                              >
                                <span>✓</span> {s}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {devAreas.length > 0 && (
                        <div>
                          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-promising">
                            Development Areas
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {devAreas.map((s, i) => (
                              <span
                                key={i}
                                className="inline-flex items-center gap-1 rounded-full bg-promising/15 px-2.5 py-1 text-xs text-promising"
                              >
                                <span>↗</span> {s}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Speaking balance */}
                  {speaking && (speaking.candidate_words ?? 0) > 0 && (
                    <SpeakingSection s={speaking} />
                  )}
                </div>

                {/* Right column */}
                <div className="space-y-4">
                  {/* Vision engagement timeline */}
                  {result.vision && (
                    <VisionSection
                      vision={result.vision}
                      onSeek={result.has_video ? seekTo : undefined}
                    />
                  )}
                </div>
              </div>

              {/* Video player (collapsed) */}
              {result.has_video && (
                <details className="rounded-xl glass-tile overflow-hidden">
                  <summary className="cursor-pointer select-none px-4 py-3 text-sm font-semibold text-heading hover:bg-foreground/[0.03] transition-colors">
                    Interview video
                  </summary>
                  <div className="p-4 pt-0">
                    <VideoSection
                      candidateId={candidateId}
                      hasAnnotated={!!result.has_annotated_video}
                      onRefresh={load}
                      videoRef={videoRef}
                    />
                  </div>
                </details>
              )}

              {/* Audio player (collapsed) */}
              {result.has_audio && (
                <details className="rounded-xl glass-tile overflow-hidden">
                  <summary className="cursor-pointer select-none px-4 py-3 text-sm font-semibold text-heading hover:bg-foreground/[0.03] transition-colors">
                    {result.has_video ? "Audio track" : "Interview recording"}
                  </summary>
                  <div className="px-4 pb-4">
                    <audio
                      controls
                      preload="none"
                      className="w-full"
                      src={getInterviewAudioUrl(candidateId)}
                    >
                      Your browser does not support audio playback.
                    </audio>
                    <div className="mt-2 text-right">
                      <a
                        href={getInterviewAudioUrl(candidateId)}
                        download
                        className="text-[11px] font-medium text-primary hover:underline"
                      >
                        Download audio
                      </a>
                    </div>
                  </div>
                </details>
              )}

              {/* Cost details */}
              {result.metrics && (
                <details className="rounded-xl glass-tile overflow-hidden">
                  <summary className="cursor-pointer select-none px-4 py-3 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors">
                    Cost details — expand
                  </summary>
                  <div className="px-4 pb-4">
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
                  </div>
                </details>
              )}
            </div>
          )}

          {/* Assessment tab */}
          {activeTab === "assessment" && (
            <div className="space-y-4">
              {/* 14-dimension grid */}
              {result.session?.overall_assessment && (
                <FinalAssessment raw={result.session.overall_assessment} />
              )}

              {/* Goals grid */}
              <section className="rounded-xl glass-tile p-4">
                <h4 className="mb-3 text-sm font-semibold text-heading">Goals</h4>
                {(result.goals ?? []).length === 0 ? (
                  <p className="text-xs text-muted-foreground">No goals recorded.</p>
                ) : (
                  <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                    {(result.goals ?? []).map((g) => (
                      <GoalTile key={g.title} goal={g} />
                    ))}
                  </div>
                )}
              </section>

              {/* Communication analysis */}
              {(result.transcript?.length ?? 0) > 0 && (
                <CommunicationSection
                  candidateId={candidateId}
                  autoLoad={!!result.has_communication}
                />
              )}
            </div>
          )}

          {/* Transcript tab */}
          {activeTab === "transcript" && (
            <div className="space-y-4">
              {result.has_audio && (
                <section className="rounded-xl glass-tile p-4">
                  <h4 className="mb-3 text-sm font-semibold text-heading">
                    {result.has_video ? "Audio track" : "Interview recording"}
                  </h4>
                  <audio
                    controls
                    preload="none"
                    className="w-full"
                    src={getInterviewAudioUrl(candidateId)}
                  >
                    Your browser does not support audio playback.
                  </audio>
                  <div className="mt-2 text-right">
                    <a
                      href={getInterviewAudioUrl(candidateId)}
                      download
                      className="text-[11px] font-medium text-primary hover:underline"
                    >
                      Download audio
                    </a>
                  </div>
                </section>
              )}

              <section className="rounded-xl glass-tile p-4">
                <h4 className="mb-3 text-sm font-semibold text-heading">
                  Transcript
                  <span className="ml-2 text-[11px] text-muted-foreground font-normal">
                    {transcriptCount} messages
                  </span>
                </h4>
                <div className="max-h-[500px] space-y-3 overflow-y-auto pr-2">
                  {(result.transcript ?? []).map((t, i) => (
                    <div
                      key={i}
                      className={`flex flex-col ${t.speaker === "agent" ? "items-start" : "items-end"}`}
                    >
                      <div
                        className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                          t.speaker === "agent"
                            ? "bg-foreground/10 text-foreground"
                            : "bg-primary text-white"
                        }`}
                      >
                        {t.text}
                      </div>
                      {t.speaker !== "agent" && t.evaluation && (
                        <TurnEvalBadge ev={t.evaluation} />
                      )}
                    </div>
                  ))}
                  {transcriptCount === 0 && (
                    <p className="text-xs text-muted-foreground">No transcript recorded.</p>
                  )}
                </div>
              </section>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Interview video playback with a raw / annotated (YOLO boxes) toggle. */
function VideoSection({
  candidateId,
  hasAnnotated,
  onRefresh,
  videoRef,
}: {
  candidateId: number;
  hasAnnotated: boolean;
  onRefresh: () => void;
  videoRef?: React.RefObject<HTMLVideoElement | null>;
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
    <div>
      <div className="mb-3 flex items-center justify-between gap-2">
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
        ref={videoRef}
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
    </div>
  );
}

const FLAG_LABELS: Record<string, string> = {
  candidate_absent: "Candidate absent",
  phone_visible: "Phone visible",
  multiple_people: "Multiple people",
};

/** Advisory video-evaluation report: presence, engagement, integrity, delivery. */
function VisionSection({ vision, onSeek }: { vision: VisionReport; onSeek?: (t: number) => void }) {
  const agg = vision.aggregate ?? {};
  const flags = agg.integrity_flags ?? [];
  const present = Math.round((agg.present_ratio ?? 0) * 100);
  const engagementRaw = agg.avg_engagement ?? 0;
  const obs = (vision.observations ?? []).filter((o) => o.summary || o.delivery_notes);
  const quality = vision.data_quality;
  const insufficient = quality?.level === "insufficient";

  const qualityStyle =
    quality?.level === "good"
      ? { borderColor: "var(--strong)", background: "var(--strong-bg)", color: "var(--strong-text)" }
      : quality?.level === "limited"
      ? { borderColor: "var(--promising)", background: "var(--promising-bg)", color: "var(--promising-text)" }
      : { borderColor: "var(--weak)", background: "var(--weak-bg)", color: "var(--weak-text)" };

  const avgEngagementPerObs =
    obs.length > 0
      ? obs.reduce((acc, o) => acc + (typeof o.engagement === "number" ? o.engagement : 0), 0) /
        obs.length
      : null;

  function engagementColor(e: number): string {
    if (e >= 4) return "var(--strong)";
    if (e >= 2) return "var(--promising)";
    return "var(--weak)";
  }

  return (
    <section className="rounded-xl glass-tile p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-heading">Video evaluation</h4>
        <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
          {vision.backend ?? "vision"} · advisory
        </span>
      </div>

      {quality && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border p-2.5 text-xs" style={qualityStyle}>
          <span className="font-semibold uppercase tracking-wide">{quality.level}</span>
          <span>· {quality.note}</span>
        </div>
      )}

      {vision.overall_summary && !insufficient && (
        <p className="mb-3 rounded-lg bg-foreground/[0.04] p-3 text-sm leading-relaxed text-foreground">
          {vision.overall_summary}
        </p>
      )}

      {/* Engagement timeline */}
      {obs.length > 0 && (
        <div className="mb-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-[11px] font-medium text-muted-foreground">Engagement timeline</span>
            {avgEngagementPerObs != null && (
              <span className="text-[11px] text-faint">avg {avgEngagementPerObs.toFixed(1)}/5</span>
            )}
          </div>
          <div className="relative flex items-end gap-0">
            <div
              className="pointer-events-none absolute left-0 right-0 h-px bg-border"
              style={{ top: "50%", transform: "translateY(-100%)" }}
            />
            <div className="relative flex items-end gap-3 overflow-x-auto pb-1 pt-2">
              {obs.map((o, i) => {
                const eng = typeof o.engagement === "number" ? o.engagement : 2;
                const size = Math.min(48, eng * 8 + 8);
                const color = engagementColor(eng);
                return (
                  <div
                    key={i}
                    className="flex shrink-0 flex-col items-center gap-1"
                    title={`engagement ${eng}/5 · ${o.summary ?? ""}`}
                  >
                    <div
                      className="rounded-full transition-transform hover:scale-110"
                      style={{
                        width: size,
                        height: size,
                        background: color,
                        opacity: 0.85,
                        boxShadow: `0 0 0 2px color-mix(in srgb, ${color} 30%, transparent)`,
                      }}
                    />
                    <span className="text-[10px] text-faint tabular-nums">{fmtTime(o.t ?? 0)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* 3 key metrics */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <Stat label="Presence" value={`${present}%`} mono />
        <Stat
          label="Engagement"
          value={
            avgEngagementPerObs != null
              ? `${avgEngagementPerObs.toFixed(1)}/5`
              : `${Math.round((engagementRaw / 3) * 5 * 10) / 10}/5`
          }
          mono
        />
        <Stat label="Frames" value={String(agg.frames_analyzed ?? 0)} mono />
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

      {/* Per-frame notes (collapsed) */}
      {obs.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-[11px] uppercase tracking-wide text-muted-foreground">
            Per-frame notes ({obs.length})
          </summary>
          <ul className="mt-2 space-y-2">
            {obs.map((o, i) => (
              <li key={i} className="rounded-lg bg-foreground/[0.03] p-2.5 text-xs">
                <div className="mb-0.5 flex items-center gap-2 text-muted-foreground">
                  {onSeek ? (
                    <button
                      onClick={() => onSeek(o.t ?? 0)}
                      title="Jump to this moment in the video"
                      className="rounded bg-primary/10 px-1.5 py-0.5 font-mono tabular-nums text-primary hover:bg-primary/20"
                    >
                      ▶ {fmtTime(o.t ?? 0)}
                    </button>
                  ) : (
                    <span className="font-mono tabular-nums">{fmtTime(o.t ?? 0)}</span>
                  )}
                  {typeof o.engagement === "number" && <span>· engagement {o.engagement}/5</span>}
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
                    ]
                      .filter(Boolean)
                      .join(" · ")}
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

  const run = useCallback(
    async (refresh = false) => {
      setBusy(true);
      try {
        setData(await api.getCommunicationAnalysis(candidateId, refresh));
      } catch {
        toast.error("Couldn't analyze communication");
      } finally {
        setBusy(false);
      }
    },
    [candidateId]
  );

  useEffect(() => {
    if (autoLoad) run(false);
  }, [autoLoad, run]);

  const a = data?.analysis ?? null;
  const c = data?.content ?? null;
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
  const contentRows: [string, string | undefined][] = c
    ? [
        ["STAR structure", c.star_usage],
        ["Specificity", c.specificity],
        ["Ownership", c.ownership],
        ["Relevance", c.relevance],
      ]
    : [];

  return (
    <section className="rounded-xl glass-tile p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-heading">Answer content &amp; communication</h4>
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
          Analyze answer content (STAR structure, specificity, ownership, relevance, red flags) plus
          delivery (talking style, fluency, pace, fillers) from the transcript.
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
          {Object.entries(f.by_filler).map(([w, cnt]) => (
            <span
              key={w}
              className="rounded-full bg-foreground/[0.06] px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              &ldquo;{w}&rdquo; ×{cnt}
            </span>
          ))}
        </div>
      )}

      {a?.error && <p className="text-xs text-weak">{a.error}</p>}

      {(contentRows.some(([, v]) => v) ||
        (c?.red_flags?.length ?? 0) > 0 ||
        (c?.strengths?.length ?? 0) > 0) && (
        <div className="mb-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-heading">
            Content &amp; answer quality
          </p>
          <dl className="space-y-2">
            {contentRows
              .filter(([, v]) => v)
              .map(([label, v]) => (
                <div key={label} className="grid grid-cols-[120px_1fr] gap-2 text-sm">
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {label}
                  </dt>
                  <dd className="text-foreground">{v}</dd>
                </div>
              ))}
          </dl>
          {(c?.strengths?.length ?? 0) > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {c!.strengths!.map((s, i) => (
                <span
                  key={i}
                  className="inline-flex items-center rounded-full bg-strong/15 px-2.5 py-1 text-xs text-strong"
                >
                  ✓ {s}
                </span>
              ))}
            </div>
          )}
          {(c?.red_flags?.length ?? 0) > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {c!.red_flags!.map((s, i) => (
                <span
                  key={i}
                  className="inline-flex items-center rounded-full bg-weak/15 px-2.5 py-1 text-xs text-weak"
                >
                  ⚑ {s}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {rows.filter(([, v]) => v).length > 0 && (
        <>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-heading">
            Delivery &amp; communication
          </p>
          <dl className="space-y-2">
            {rows
              .filter(([, v]) => v)
              .map(([label, v]) => (
                <div key={label} className="grid grid-cols-[120px_1fr] gap-2 text-sm">
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {label}
                  </dt>
                  <dd className="text-foreground">{v}</dd>
                </div>
              ))}
          </dl>
        </>
      )}

      {a?.accent_note && (
        <p className="mt-3 text-[11px] text-faint">
          Note: this is a text analysis of the transcript — true accent classification requires audio
          modelling.
        </p>
      )}
    </section>
  );
}

function fmtTime(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

/** Objective speaking metrics: talk-time balance, pace, answer length. */
function SpeakingSection({ s }: { s: NonNullable<InterviewResult["speaking"]> }) {
  const candPct = Math.round(s.candidate_talk_ratio_pct);
  const botPct = 100 - candPct;
  const botWords = candPct > 0 ? Math.round((s.candidate_words * botPct) / candPct) : 0;

  return (
    <section className="rounded-xl glass-tile p-4">
      <h4 className="mb-3 text-sm font-semibold text-heading">Speaking balance &amp; pace</h4>

      <div
        className="overflow-hidden rounded-full h-3 flex"
        role="img"
        aria-label={`Candidate ${candPct}%, Interviewer ${botPct}%`}
      >
        <div
          className="h-full transition-all"
          style={{ width: `${candPct}%`, background: "var(--primary)" }}
        />
        <div
          className="h-full transition-all"
          style={{ width: `${botPct}%`, background: "var(--ozi-ink-300, #9CA3B0)" }}
        />
      </div>

      <div className="mt-2 flex items-start justify-between gap-2 text-[11px] text-muted-foreground">
        <div>
          <span className="font-semibold" style={{ color: "var(--primary)" }}>
            Candidate {candPct}%
          </span>
          <br />
          <span>
            {s.candidate_words.toLocaleString()} words · {s.candidate_turns} turns
          </span>
        </div>
        <div className="text-right">
          <span className="font-semibold text-muted-foreground">Interviewer {botPct}%</span>
          <br />
          <span>~{botWords.toLocaleString()} words</span>
        </div>
      </div>

      <p className="mt-1.5 text-[11px] text-faint">
        Talk-time is word-share, a rough proxy for who spoke more.
      </p>

      <div className="mt-3 grid grid-cols-3 gap-2">
        <Stat label="Talk ratio" value={`${candPct}%`} mono />
        <Stat label="Candidate words" value={String(s.candidate_words)} mono />
        <Stat label="Avg / answer" value={String(s.avg_words_per_answer)} mono />
      </div>

      {s.approx_words_per_min != null && (
        <p className="mt-2 text-[11px] text-faint">
          Pace is words ÷ total interview time (includes pauses &amp; the interviewer&apos;s turns),
          so it reads lower than true speaking rate — use it for relative comparison, not an absolute.
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

/** Two-phase interview progress indicator showing Phase 1 behavioral + Phase 2 technical. */
function PhaseAssessmentCard({
  phase1Score,
  currentPhase,
  goalsCompleted,
  totalGoals,
}: {
  phase1Score: number | null;
  currentPhase: string | null;
  goalsCompleted: number;
  totalGoals: number;
}) {
  const PHASE1_THRESHOLD = 60;

  const p1Color =
    phase1Score == null
      ? "var(--muted-foreground)"
      : phase1Score >= 75
      ? "var(--strong)"
      : phase1Score >= PHASE1_THRESHOLD
      ? "var(--promising)"
      : "var(--weak)";

  const p1HexColor =
    phase1Score == null
      ? "#9CA3B0"
      : phase1Score >= 75
      ? "#34C28A"
      : phase1Score >= PHASE1_THRESHOLD
      ? "#F5B544"
      : "#F25C7C";

  const p1Rgb = p1HexColor
    .slice(1)
    .match(/.{2}/g)!
    .map((h) => parseInt(h, 16))
    .join(",");

  const advancedToPhase2 =
    currentPhase === "technical" || currentPhase === "complete";
  const initialOnly = currentPhase === "initial_only";
  const didNotAdvance =
    initialOnly ||
    (phase1Score != null &&
      phase1Score < PHASE1_THRESHOLD &&
      currentPhase !== "technical" &&
      currentPhase !== "complete");

  return (
    <section className="rounded-xl glass-tile p-4">
      <h4 className="mb-3 text-sm font-semibold text-heading">Phase Assessment</h4>

      {/* Two phase step indicators */}
      <div className="flex items-stretch gap-2">
        {/* Phase 1 */}
        <div
          className="flex-1 rounded-xl p-3"
          style={{
            background: `rgba(${p1Rgb}, 0.10)`,
            border: `1px solid rgba(${p1Rgb}, 0.28)`,
          }}
        >
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            Phase 1
          </div>
          <div className="text-xs font-medium text-foreground mb-2">Behavioral</div>
          {phase1Score != null ? (
            <div
              className="font-mono text-2xl font-bold tabular-nums leading-none"
              style={{ color: p1Color }}
            >
              {Math.round(phase1Score)}
              <span className="text-sm font-normal text-muted-foreground">/100</span>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">In progress</div>
          )}
          {phase1Score != null && (
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-foreground/10">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${Math.round(phase1Score)}%`, background: p1Color }}
              />
            </div>
          )}
          {phase1Score != null && (
            <p className="mt-1.5 text-[10px]" style={{ color: p1Color }}>
              {phase1Score >= 75
                ? "Strong"
                : phase1Score >= PHASE1_THRESHOLD
                ? "Passed"
                : "Below threshold"}
            </p>
          )}
        </div>

        {/* Arrow connector */}
        <div className="flex items-center text-muted-foreground/50 text-lg select-none">
          →
        </div>

        {/* Phase 2 */}
        <div
          className="flex-1 rounded-xl p-3"
          style={
            advancedToPhase2
              ? {
                  background: "rgba(28,153,191,0.10)",
                  border: "1px solid rgba(28,153,191,0.28)",
                }
              : didNotAdvance
              ? {
                  background: "rgba(242,92,124,0.06)",
                  border: "1px solid rgba(242,92,124,0.18)",
                }
              : {
                  background: "var(--surface-card, rgba(255,255,255,0.03))",
                  border: "1px solid var(--surface-border, rgba(255,255,255,0.06))",
                }
          }
        >
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            Phase 2
          </div>
          <div className="text-xs font-medium text-foreground mb-2">Technical</div>
          {didNotAdvance ? (
            <div className="text-sm font-semibold" style={{ color: "var(--weak)" }}>
              Not reached
            </div>
          ) : advancedToPhase2 ? (
            <div
              className="text-sm font-semibold"
              style={{ color: currentPhase === "complete" ? "var(--strong)" : "#1C99BF" }}
            >
              {currentPhase === "complete"
                ? `${goalsCompleted}/${totalGoals} goals`
                : "In Progress"}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">Pending</div>
          )}
        </div>
      </div>

      {/* Explanation line */}
      {didNotAdvance && (
        <p className="mt-3 rounded-lg border border-weak/20 bg-weak/5 px-3 py-2 text-xs text-weak">
          Phase 1 only — candidate did not advance to the technical portion
          {phase1Score != null
            ? ` (score ${Math.round(phase1Score)}/100 was below the ${PHASE1_THRESHOLD}-point threshold).`
            : "."}
        </p>
      )}
      {advancedToPhase2 && currentPhase !== "complete" && (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Candidate advanced to Phase 2 technical questions.
        </p>
      )}
    </section>
  );
}

/** One goal with its progress, planned questions, and the candidate's answer evidence. */
function GoalRow({ goal }: { goal: NonNullable<InterviewResult["goals"]>[number] }) {
  const pct = Math.min(100, Math.round((Number(goal.progress_score) || 0) * 100));
  const questions = goal.questions ?? [];
  const evidence = goal.evidence ?? [];
  const hasDetail = questions.length > 0 || evidence.length > 0;

  const borderColor =
    pct > 66 ? "var(--strong)" : pct >= 33 ? "var(--promising)" : "var(--weak)";
  const barColor =
    pct > 66 ? "var(--strong)" : pct >= 33 ? "var(--promising)" : "var(--weak)";

  return (
    <li className="rounded-lg border-l-2 pl-3 py-0.5" style={{ borderLeftColor: borderColor }}>
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 truncate text-xs text-foreground" title={goal.title}>
          {goal.title}
        </span>
        <span
          className="shrink-0 font-mono text-xs font-semibold tabular-nums"
          style={{ color: barColor }}
        >
          {pct}%
        </span>
      </div>
      <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-foreground/10">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: barColor }}
        />
      </div>
      {goal.completion_status && (
        <p className="mt-1 text-[10px] text-muted-foreground">{goal.completion_status}</p>
      )}
      {hasDetail && (
        <details className="mt-2">
          <summary className="cursor-pointer text-[11px] text-muted-foreground">
            Questions &amp; answers
          </summary>
          {questions.length > 0 && (
            <div className="mt-2">
              <div className="text-[11px] uppercase tracking-wide text-faint">Questions</div>
              <ul className="ml-4 mt-1 list-disc text-xs text-foreground">
                {questions.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </div>
          )}
          {evidence.length > 0 && (
            <div className="mt-2">
              <div className="text-[11px] uppercase tracking-wide text-faint">Candidate answers</div>
              <ul className="mt-1 space-y-1">
                {evidence.map((e, i) => (
                  <li key={i} className="rounded-md glass-tile px-2 py-1 text-xs italic text-foreground">
                    &ldquo;{e.text}&rdquo;
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

/** Compact visual goal tile — mini ring + title, used in the 3-col goals grid. */
function GoalTile({ goal }: { goal: NonNullable<InterviewResult["goals"]>[number] }) {
  const pct = Math.min(100, Math.round((Number(goal.progress_score) || 0) * 100));
  const color = pct > 66 ? "var(--strong)" : pct >= 33 ? "var(--promising)" : "var(--weak)";
  const hexBg =
    pct > 66
      ? "rgba(52,194,138,0.10)"
      : pct >= 33
      ? "rgba(245,181,68,0.10)"
      : "rgba(242,92,124,0.10)";
  const size = 44,
    stroke = 5,
    r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const questions = goal.questions ?? [];
  const evidence = goal.evidence ?? [];
  const hasDetail = questions.length > 0 || evidence.length > 0;

  const tile = (
    <div
      className="rounded-xl p-2.5 flex flex-col items-center gap-1.5 text-center"
      style={{ background: hexBg, border: `1px solid ${color}33` }}
      title={goal.title}
    >
      <div
        className="relative inline-flex items-center justify-center"
        style={{ width: size, height: size }}
      >
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="color-mix(in srgb, var(--foreground) 10%, transparent)"
            strokeWidth={stroke}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={circ * (1 - pct / 100)}
            style={{ transition: "stroke-dashoffset 0.8s ease" }}
          />
        </svg>
        <span
          className="absolute font-mono text-[11px] font-bold tabular-nums"
          style={{ color }}
        >
          {pct}%
        </span>
      </div>
      <p className="line-clamp-2 text-[11px] leading-tight text-foreground">{goal.title}</p>
    </div>
  );

  if (!hasDetail) return tile;

  return (
    <details className="group">
      <summary className="list-none cursor-pointer">{tile}</summary>
      <div className="mt-1.5 rounded-xl border border-border p-2.5 text-xs space-y-2">
        {questions.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
              Questions
            </div>
            <ul className="list-disc ml-3 space-y-0.5 text-foreground">
              {questions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </div>
        )}
        {evidence.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
              Evidence
            </div>
            <ul className="space-y-1">
              {evidence.map((e, i) => (
                <li key={i} className="rounded-md glass-tile px-2 py-1 italic text-foreground">
                  &ldquo;{e.text}&rdquo;
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </details>
  );
}

/** Compact per-answer evaluation shown under a candidate message. */
function TurnEvalBadge({ ev }: { ev: TurnEvaluation }) {
  const score = typeof ev.score === "number" ? ev.score : null;
  const color =
    score == null
      ? "text-muted-foreground"
      : score >= 7
      ? "text-strong"
      : score >= 4
      ? "text-promising"
      : "text-weak";
  const strength = ev.strengths?.[0];
  const weakness = ev.weaknesses?.[0];
  return (
    <div className="mt-1 max-w-[80%] text-right text-[11px] text-muted-foreground">
      {score != null && (
        <span className={`font-mono font-semibold tabular-nums ${color}`}>{score}/10</span>
      )}
      {ev.depth && <span> · {ev.depth}</span>}
      {strength && <span> · 👍 {strength}</span>}
      {weakness && <span> · 👎 {weakness}</span>}
    </div>
  );
}

const DIMENSION_LABELS: Record<string, string> = {
  communication_skills: "Communication Skills",
  confidence_presentation: "Confidence & Presentation",
  technical_competency: "Technical Competency",
  problem_solving: "Problem-Solving & Critical Thinking",
  relevant_experience: "Relevant Experience",
  skills_match: "Skills Match Assessment",
  cultural_fit: "Cultural & Organizational Fit",
  leadership_ownership: "Leadership & Ownership",
  learning_agility: "Learning Agility",
  emotional_intelligence: "Emotional Intelligence",
  motivation_alignment: "Motivation & Career Alignment",
  behavioral_assessment: "Behavioral Assessment",
  resume_consistency: "Resume & Interview Consistency",
  overall_performance: "Overall Performance Evaluation",
};

const DIMENSION_ORDER = Object.keys(DIMENSION_LABELS);

function scoreColor(score: number): string {
  if (score >= 75) return "var(--strong)";
  if (score >= 50) return "var(--promising)";
  return "var(--weak)";
}

function decisionStyle(decision: string): { bg: string; text: string } {
  const d = decision.toLowerCase();
  if (d === "hire") return { bg: "var(--strong)", text: "#fff" };
  if (d === "reject") return { bg: "var(--weak)", text: "#fff" };
  return { bg: "var(--promising)", text: "#fff" };
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

  const Wrap = ({ children }: { children: ReactNode }) => (
    <section className="rounded-xl glass-tile p-4 space-y-4">
      <h4 className="flex items-center gap-2 text-sm font-semibold text-heading">
        <ClipboardCheck className="h-4 w-4 text-primary" /> Final evaluation
      </h4>
      {children}
    </section>
  );

  if (!parsed) {
    return (
      <Wrap>
        <p className="text-sm text-foreground">{raw}</p>
      </Wrap>
    );
  }

  const fr = (parsed.final_ai_recommendation ?? {}) as Record<string, unknown>;
  const ds = (parsed.dimension_scores ?? {}) as Record<string, { score: number; notes?: string }>;
  const ov = (parsed.overall_assessment ?? {}) as Record<string, unknown>;
  const goals = (parsed.goal_assessments as Record<string, unknown>[]) ?? [];

  const keyStrengths: string[] =
    (fr.key_strengths as string[]) ?? (ov.strengths as string[]) ?? [];
  const devAreas: string[] =
    (fr.development_areas as string[]) ?? (ov.areas_for_improvement as string[]) ?? [];

  const hasDimensions = Object.keys(ds).length > 0;

  return (
    <Wrap>
      {/* Strengths + Dev Areas */}
      {(keyStrengths.length > 0 || devAreas.length > 0) && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {keyStrengths.length > 0 && (
            <div>
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-strong">
                Key Strengths
              </div>
              <div className="flex flex-wrap gap-1.5">
                {keyStrengths.map((s, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 rounded-full bg-strong/15 px-2.5 py-1 text-xs text-strong"
                  >
                    <span>✓</span> {s}
                  </span>
                ))}
              </div>
            </div>
          )}
          {devAreas.length > 0 && (
            <div>
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-promising">
                Development Areas
              </div>
              <div className="flex flex-wrap gap-1.5">
                {devAreas.map((s, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 rounded-full bg-promising/15 px-2.5 py-1 text-xs text-promising"
                  >
                    <span>↗</span> {s}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 14-Dimension grid */}
      {hasDimensions && (
        <div>
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            14-Dimension Assessment
          </div>
          <div className="grid grid-cols-2 gap-2">
            {DIMENSION_ORDER.map((key) => {
              const dim = ds[key];
              if (!dim) return null;
              const score = Number(dim.score ?? 0);
              const color = scoreColor(score);
              const hexColor =
                score >= 75 ? "#34C28A" : score >= 50 ? "#F5B544" : "#F25C7C";
              const rgb = hexColor
                .slice(1)
                .match(/.{2}/g)!
                .map((h) => parseInt(h, 16))
                .join(",");
              return (
                <div
                  key={key}
                  className="rounded-xl p-3"
                  title={
                    dim.notes
                      ? `${DIMENSION_LABELS[key]}: ${dim.notes}`
                      : DIMENSION_LABELS[key]
                  }
                  style={{
                    background: `rgba(${rgb}, 0.10)`,
                    border: `1px solid rgba(${rgb}, 0.25)`,
                  }}
                >
                  <div
                    className="text-2xl font-mono font-bold tabular-nums leading-none"
                    style={{ color }}
                  >
                    {score}
                  </div>
                  <div className="mt-1 text-[11px] text-muted-foreground uppercase tracking-wide leading-tight">
                    {DIMENSION_LABELS[key]}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Per-goal detail (collapsible) */}
      {goals.length > 0 && (
        <details>
          <summary className="cursor-pointer text-xs text-muted-foreground">
            Per-goal assessment ({goals.length})
          </summary>
          <ul className="mt-2 space-y-2">
            {goals.map((g, i) => (
              <li key={i} className="rounded-lg border border-border p-2 text-sm">
                <div className="flex justify-between gap-2">
                  <span className="font-medium text-heading">
                    {String(g.goal_title ?? "Goal")}
                  </span>
                  <span className="shrink-0 text-muted-foreground">
                    <span className="font-mono font-semibold tabular-nums text-heading">
                      {Math.round(Number(g.final_score ?? 0) * 100)}%
                    </span>{" "}
                    · {String(g.completion_status ?? "")}
                  </span>
                </div>
                {Array.isArray(g.key_quotes) && (g.key_quotes as string[]).length > 0 && (
                  <p className="mt-1 text-xs italic text-muted-foreground">
                    &ldquo;{(g.key_quotes as string[])[0]}&rdquo;
                  </p>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Wrap>
  );
}

// GoalRow is defined but kept for potential future use
void GoalRow;
// decisionStyle is defined but kept for potential future use
void decisionStyle;
