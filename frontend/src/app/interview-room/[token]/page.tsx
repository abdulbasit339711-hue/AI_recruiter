"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Mic, Video, Wifi, CheckCircle2, ArrowRight, Clock, AlertTriangle } from "lucide-react";

type RoomData = {
  candidate_name: string | null;
  job_title: string;
  org_name: string | null;
  org_color: string;
  org_logo_url: string | null;
  confirmed_slot: string | null;
  interview_token: string;
};

const PREP_ITEMS = [
  { icon: Mic, label: "Microphone working", hint: "Speak a few words to confirm it picks up sound." },
  { icon: Video, label: "Camera ready (optional)", hint: "Not required, but helps the interviewer see you." },
  { icon: Wifi, label: "Stable internet connection", hint: "Close unused browser tabs and apps to reduce lag." },
];

function monogram(name: string) {
  const w = name.trim().split(/\s+/);
  return w.length >= 2 ? (w[0][0] + w[1][0]).toUpperCase() : name.slice(0, 2).toUpperCase();
}

export default function InterviewRoomPage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();

  const [room, setRoom] = useState<RoomData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [joining, setJoining] = useState(false);
  const [checklist, setChecklist] = useState<boolean[]>([false, false, false]);

  useEffect(() => {
    if (!token) return;
    api.getInterviewRoom(token)
      .then(setRoom)
      .catch(() => setError("This link is invalid or has expired. Please contact the recruitment team."));
  }, [token]);

  function toggleCheck(i: number) {
    setChecklist((prev) => {
      const next = [...prev];
      next[i] = !next[i];
      return next;
    });
  }

  const allChecked = checklist.every(Boolean);

  async function handleJoin() {
    if (!room) return;
    setJoining(true);
    router.push(`/interview/${room.interview_token}`);
  }

  const color = room?.org_color || "#1C99BF";

  /* ── Error state ─────────────────────────────────────── */
  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#04111B] px-4">
        <div className="max-w-md text-center">
          <AlertTriangle className="mx-auto mb-4 h-12 w-12 text-red-400" />
          <h1 className="mb-2 text-xl font-semibold text-white">Link unavailable</h1>
          <p className="text-sm text-gray-400">{error}</p>
        </div>
      </div>
    );
  }

  /* ── Loading state ───────────────────────────────────── */
  if (!room) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#04111B]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-white" />
      </div>
    );
  }

  const orgDisplay = room.org_name || "Recruitment";
  const candidateFirst = room.candidate_name?.split(" ")[0] || "there";

  return (
    <div
      className="relative flex min-h-screen flex-col bg-[#04111B]"
      style={{
        background: `radial-gradient(900px 500px at 15% -5%, ${color}18, transparent 55%),
                     radial-gradient(600px 400px at 90% 10%, ${color}0e, transparent 50%),
                     #04111B`,
      }}
    >
      {/* ── Header ────────────────────────────────────────── */}
      <header className="border-b border-white/[0.06] px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          {room.org_logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={room.org_logo_url} alt={orgDisplay} className="h-8 w-8 rounded-lg object-contain" />
          ) : (
            <span
              className="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold text-white"
              style={{ background: color }}
            >
              {monogram(orgDisplay)}
            </span>
          )}
          <span className="text-sm font-semibold text-white/80">{orgDisplay}</span>
        </div>
      </header>

      {/* ── Main content ──────────────────────────────────── */}
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-10 sm:px-6">

        {/* Title block */}
        <div className="mb-8">
          <p className="mb-1 text-sm text-gray-400">Hi {candidateFirst}, you&apos;re all set for</p>
          <h1 className="text-3xl font-bold tracking-tight text-white">{room.job_title}</h1>
          <p className="mt-1 text-sm text-gray-500">{orgDisplay} · AI Interview</p>
        </div>

        <div className="grid gap-5 md:grid-cols-[1fr_300px]">

          {/* Left: checklist + join */}
          <div className="space-y-5">

            {/* Scheduled time */}
            {room.confirmed_slot && (
              <div
                className="flex items-start gap-3 rounded-2xl p-4"
                style={{ background: `${color}12`, border: `1px solid ${color}28` }}
              >
                <Clock className="mt-0.5 h-5 w-5 shrink-0" style={{ color }} />
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider" style={{ color }}>
                    Scheduled interview time
                  </p>
                  <p className="mt-0.5 text-base font-semibold text-white">{room.confirmed_slot}</p>
                  <p className="mt-0.5 text-xs text-gray-500">
                    You can join a few minutes early — the AI interviewer will be ready.
                  </p>
                </div>
              </div>
            )}

            {/* Pre-flight checklist */}
            <div
              className="rounded-2xl p-5"
              style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}
            >
              <p className="mb-4 text-sm font-semibold text-white">Before you join — quick checklist</p>
              <div className="space-y-3">
                {PREP_ITEMS.map(({ icon: Icon, label, hint }, i) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => toggleCheck(i)}
                    className="flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-white/[0.04]"
                  >
                    <span
                      className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-all"
                      style={
                        checklist[i]
                          ? { borderColor: color, background: color }
                          : { borderColor: "rgba(255,255,255,0.2)", background: "transparent" }
                      }
                    >
                      {checklist[i] && <CheckCircle2 className="h-3.5 w-3.5 text-white" strokeWidth={3} />}
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <Icon className="h-3.5 w-3.5 text-gray-400" />
                        <span className="text-sm font-medium text-gray-200">{label}</span>
                      </div>
                      <p className="mt-0.5 text-xs text-gray-500">{hint}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Join button */}
            <button
              onClick={handleJoin}
              disabled={joining || !allChecked}
              className="flex w-full items-center justify-center gap-2 rounded-2xl py-4 text-base font-semibold text-white transition-all disabled:cursor-not-allowed disabled:opacity-40"
              style={{
                background: allChecked
                  ? `linear-gradient(135deg, ${color}, ${color}cc)`
                  : "rgba(255,255,255,0.06)",
                boxShadow: allChecked ? `0 0 32px ${color}55` : "none",
              }}
            >
              {joining ? (
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              ) : (
                <>
                  {allChecked ? "Join Interview" : "Tick all boxes above to continue"}
                  {allChecked && <ArrowRight className="h-5 w-5" />}
                </>
              )}
            </button>

            {!allChecked && (
              <p className="text-center text-xs text-gray-600">
                Complete the checklist to unlock the join button.
              </p>
            )}
          </div>

          {/* Right: what to expect */}
          <div
            className="h-fit rounded-2xl p-5"
            style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}
          >
            <p className="mb-3 text-sm font-semibold text-white">What to expect</p>
            <ul className="space-y-3 text-xs text-gray-400">
              {[
                ["AI Interviewer", "You'll speak with an AI voice assistant that asks structured questions about your experience."],
                ["Duration", "Typically 10–20 minutes depending on the role."],
                ["Microphone", "Speak clearly. The AI listens in real time and responds to your answers."],
                ["Chat fallback", "If your mic isn't working, you can type answers using the chat panel."],
                ["Recording", "The interview is recorded for HR review. By joining you consent to this."],
              ].map(([title, desc]) => (
                <li key={title as string}>
                  <p className="font-semibold text-gray-300">{title}</p>
                  <p className="mt-0.5 leading-relaxed">{desc}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </main>

      {/* ── Footer ────────────────────────────────────────── */}
      <footer className="border-t border-white/[0.05] py-4 text-center text-xs text-gray-700">
        {orgDisplay} · Powered by AI Recruiter
      </footer>
    </div>
  );
}
