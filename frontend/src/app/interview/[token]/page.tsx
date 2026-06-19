"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  Room,
  RoomEvent,
  Track,
  type RemoteTrack,
  type Participant,
} from "livekit-client";
import {
  Loader2,
  Mic,
  MicOff,
  Video,
  VideoOff,
  AlertTriangle,
  CheckCircle2,
  PhoneOff,
  Captions,
  MessageSquareText,
  Bot,
  User,
  X,
  Send,
} from "lucide-react";

import { validateInterview, sendInterviewChat, type InterviewValidation } from "@/lib/voice";
import { useInterviewLive } from "@/hooks/useInterviewLive";
import { SpeakingBars } from "@/components/ui/motion";

type Phase = "validating" | "ready" | "connecting" | "live" | "ended" | "invalid";
type Speaker = "agent" | "you" | null;

export default function InterviewPage() {
  const { token } = useParams<{ token: string }>();
  const [phase, setPhase] = useState<Phase>("validating");
  const [info, setInfo] = useState<InterviewValidation | null>(null);
  const [chat, setChat] = useState("");
  // Optimistic chat: show the candidate's typed line immediately (as "sending…")
  // instead of waiting for the SSE round-trip — that lag is what felt unsmooth.
  const [sending, setSending] = useState(false);
  const [pending, setPending] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Meet-style call UI state
  const [micEnabled, setMicEnabled] = useState(true);
  // Camera is best-effort: the interview works without it (audio is what's scored),
  // but when a device is present we publish it and show a local self-view so the
  // candidate can frame themselves — and so the bot can later receive the stream.
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [activeSpeaker, setActiveSpeaker] = useState<Speaker>(null);
  const [showCaptions, setShowCaptions] = useState(true);
  // Open by default: candidates with no working mic answer via this chat panel,
  // so it must be visible without hunting for the toggle (esp. on mobile).
  const [showPanel, setShowPanel] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  // Browser autoplay policy can block the bot's remote audio when it subscribes
  // asynchronously (after connect, outside the click gesture). Track that so we can
  // show a "tap to enable sound" prompt and call room.startAudio() on a gesture.
  const [audioBlocked, setAudioBlocked] = useState(false);
  // Whether the AI interviewer (the "recruiter-bot" participant) is in the room.
  // null = not yet known / still connecting; false = it has left (session ended/timed out).
  const [agentPresent, setAgentPresent] = useState<boolean | null>(null);
  // Demo / watch mode (link opened with ?demo=1): the candidate answers are injected
  // by the mock driver and only show as captions, so the browser SPEAKS them with a
  // distinct voice — letting you watch a full two-voice interview without a mic.
  // (Off by default, so a real candidate's own captions are never read back to them.)
  const [demoMode, setDemoMode] = useState(false);

  const roomRef = useRef<Room | null>(null);
  const selfVideoRef = useRef<HTMLVideoElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const startRef = useRef<number | null>(null);
  const spokenRef = useRef<Set<string>>(new Set());

  // Subscribe to the live transcript stream as soon as the link is validated —
  // not only once "live" — otherwise the bot's opening greeting (broadcast right
  // at connect) is missed, since the SSE stream isn't replayed to late joiners.
  // Goals / per-answer AI scores are interviewer-internal and intentionally NOT
  // surfaced here — they live in the HR dashboard only.
  const { transcript, connected, goals } = useInterviewLive(
    phase === "ready" || phase === "connecting" || phase === "live",
    info?.session_id,
    info?.prior_transcript
  );

  useEffect(() => {
    let active = true;
    validateInterview(token)
      .then((v) => {
        if (!active) return;
        setInfo(v);
        setPhase(v.valid ? "ready" : "invalid");
      })
      .catch(() => {
        if (!active) return;
        setInfo({ valid: false, error: "Couldn't reach the interview server. Please check your connection and try again." });
        setPhase("invalid");
      });
    return () => {
      active = false;
      roomRef.current?.disconnect();
    };
  }, [token]);

  // Enable demo/watch mode from the URL (?demo=1) — read on the client to avoid a
  // Suspense boundary requirement around useSearchParams.
  useEffect(() => {
    setDemoMode(new URLSearchParams(window.location.search).get("demo") === "1");
  }, []);

  // Demo mode: speak each NEW candidate caption aloud (browser speechSynthesis) with a
  // distinct voice, so the mock candidate is audible alongside the interviewer's voice.
  useEffect(() => {
    if (!demoMode || typeof window === "undefined" || !window.speechSynthesis) return;
    for (const t of transcript) {
      if (t.speaker === "agent") continue; // interviewer is voiced by the bot over LiveKit
      const key = `${t.speaker}:${t.text}`;
      if (spokenRef.current.has(key)) continue;
      spokenRef.current.add(key);
      const u = new SpeechSynthesisUtterance(t.text);
      u.rate = 1.05;
      u.pitch = 1.15; // slightly higher → clearly distinct from the interviewer
      window.speechSynthesis.speak(u);
    }
  }, [transcript, demoMode]);

  // Stop any candidate speech when leaving.
  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  // Once a typed line arrives back as a real candidate turn over SSE, drop its
  // optimistic placeholder so it isn't shown twice.
  useEffect(() => {
    if (!pending.length) return;
    setPending((p) =>
      p.filter((t) => !transcript.some((turn) => turn.speaker === "candidate" && turn.text.trim() === t)),
    );
  }, [transcript]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [transcript, pending, showPanel]);

  // Call timer — ticks once the room connects.
  useEffect(() => {
    if (phase !== "live") return;
    if (startRef.current == null) startRef.current = Date.now();
    const id = setInterval(
      () => setElapsed(Math.floor((Date.now() - (startRef.current ?? Date.now())) / 1000)),
      1000
    );
    return () => clearInterval(id);
  }, [phase]);

  // Attach (or detach) the local camera track to the self-view <video> whenever the
  // camera is toggled or the stage mounts. The element only exists in the "live"
  // phase, so we (re)attach here rather than inline in start()/toggleCamera().
  useEffect(() => {
    const room = roomRef.current;
    const el = selfVideoRef.current;
    if (phase !== "live" || !room || !el) return;
    const track = room.localParticipant.getTrackPublication(Track.Source.Camera)?.videoTrack;
    if (cameraEnabled && track) {
      track.attach(el);
      return () => {
        try {
          track.detach(el);
        } catch {
          /* element already gone */
        }
      };
    }
  }, [cameraEnabled, phase, activeSpeaker]);

  async function start() {
    if (!info?.livekit_url || !info.livekit_token) return;
    setError(null);
    setPhase("connecting");
    try {
      const room = new Room({ adaptiveStream: true, dynacast: true });
      roomRef.current = room;
      room.on(RoomEvent.Connected, () => setPhase("live"));
      room.on(RoomEvent.Disconnected, () => setPhase("ended"));
      // Surface audio-device / WebAudio failures to the candidate instead of
      // leaving them as a silent console error.
      room.on(RoomEvent.MediaDevicesError, (e: Error) => setError(describeMediaError(e)));
      room.on(RoomEvent.ActiveSpeakersChanged, (speakers: Participant[]) => {
        if (speakers.some((s) => s.isLocal)) setActiveSpeaker("you");
        else if (speakers.length) setActiveSpeaker("agent");
        else setActiveSpeaker(null);
      });
      room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        if (track.kind === Track.Kind.Audio) {
          const el = track.attach();
          el.style.display = "none";
          document.body.appendChild(el);
        }
      });
      // Autoplay policy: if the browser blocks audio, room.canPlaybackAudio is false
      // until a user gesture calls room.startAudio(). Surface that to the candidate.
      room.on(RoomEvent.AudioPlaybackStatusChanged, () => {
        setAudioBlocked(!room.canPlaybackAudio);
      });
      // Track the AI interviewer's presence so the candidate can SEE when the bot
      // joins or leaves (e.g. on session end / idle timeout). The bot joins the room
      // as "recruiter-bot" before the candidate.
      const isAgent = (p: Participant) => p.identity === "recruiter-bot";
      room.on(RoomEvent.ParticipantConnected, (p: Participant) => {
        if (isAgent(p)) setAgentPresent(true);
      });
      room.on(RoomEvent.ParticipantDisconnected, (p: Participant) => {
        if (isAgent(p)) setAgentPresent(false);
      });
      // Bound the join so a blocked/again WebRTC path can't hang on "Connecting…"
      // forever (corporate Wi‑Fi / VPN often block the UDP/TURN media transport even
      // when HTTPS works). On timeout we surface a clear, retryable error below.
      const CONNECT_TIMEOUT_MS = 20000;
      await Promise.race([
        room.connect(info.livekit_url, info.livekit_token),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("CONNECT_TIMEOUT")), CONNECT_TIMEOUT_MS)
        ),
      ]);
      // Seed from whoever is already in the room (the bot is normally there first).
      setAgentPresent([...room.remoteParticipants.values()].some(isAgent));
      // Join is a user gesture, so this usually unblocks remote audio immediately.
      try {
        await room.startAudio();
      } catch {
        /* fall back to the "enable sound" prompt below */
      }
      setAudioBlocked(!room.canPlaybackAudio);
      // Mic is best-effort: a broken/denied microphone must NOT abort the join —
      // otherwise start() throws here, never reaches "live", and the candidate
      // can't even see the "tap to enable sound" prompt (so the bot is silent).
      // Candidates with no working mic can still answer via the text chat box.
      try {
        await room.localParticipant.setMicrophoneEnabled(true);
        setMicEnabled(true);
      } catch {
        setMicEnabled(false);
      }
      // Camera is optional — a missing/denied device must NOT fail the interview,
      // so enable it on a best-effort basis and just leave it off if unavailable.
      try {
        await room.localParticipant.setCameraEnabled(true);
        setCameraEnabled(true);
      } catch {
        setCameraEnabled(false);
      }
    } catch (e) {
      console.error(e);
      // Clean up the half-open room so a retry starts fresh.
      try {
        roomRef.current?.disconnect();
      } catch {
        /* ignore */
      }
      roomRef.current = null;
      const timedOut = e instanceof Error && e.message === "CONNECT_TIMEOUT";
      setError(
        timedOut
          ? "Couldn’t connect to the live interview — the audio/video connection timed out. " +
              "Your network may be blocking it (corporate Wi‑Fi or a VPN often do). Try a " +
              "different network or turn off any VPN, then tap “Join now” to retry."
          : describeMediaError(e)
      );
      setPhase("ready");
    }
  }

  async function toggleCamera() {
    const room = roomRef.current;
    if (!room) return;
    const next = !cameraEnabled;
    try {
      await room.localParticipant.setCameraEnabled(next);
      setCameraEnabled(next);
    } catch (e) {
      setError(describeMediaError(e));
    }
  }

  async function toggleMic() {
    const room = roomRef.current;
    if (!room) return;
    const next = !micEnabled;
    try {
      await room.localParticipant.setMicrophoneEnabled(next);
      setMicEnabled(next);
    } catch (e) {
      setError(describeMediaError(e));
    }
  }

  function leave() {
    roomRef.current?.disconnect();
    setPhase("ended");
  }

  async function enableAudio() {
    const room = roomRef.current;
    if (!room) return;
    try {
      await room.startAudio();
      setAudioBlocked(!room.canPlaybackAudio);
    } catch (e) {
      setError(describeMediaError(e));
    }
  }

  async function submitChat(e: React.FormEvent) {
    e.preventDefault();
    const text = chat.trim();
    if (!text || sending) return;
    setChat("");
    setSending(true);
    setPending((p) => [...p, text]);   // show immediately
    try {
      await sendInterviewChat(text, info?.session_id);
      // Safety net: if the server never echoes it back over SSE, clear the
      // optimistic bubble after a bit so it doesn't hang as "sending…" forever.
      setTimeout(() => setPending((p) => p.filter((t) => t !== text)), 15000);
    } catch {
      setPending((p) => p.filter((t) => t !== text));  // roll back
      setChat(text);                                   // let them retry
      setError("Couldn't send your message. Check your connection and try again.");
    } finally {
      setSending(false);
    }
  }

  // ---- Validating / invalid: simple centered states -------------------------
  if (phase === "validating") {
    return (
      <Shell>
        <div className="flex flex-1 flex-col items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-400" />
          <p className="mt-4 text-zinc-400">Validating your interview link…</p>
        </div>
      </Shell>
    );
  }

  if (phase === "invalid") {
    return (
      <Shell>
        <div className="flex flex-1 flex-col items-center justify-center px-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-amber-500/10">
            <AlertTriangle className="h-8 w-8 text-amber-400" />
          </div>
          <h1 className="mt-5 text-xl font-semibold text-zinc-100">This link can’t be used</h1>
          <p className="mt-2 max-w-md text-center text-zinc-400">
            {info?.error || "Your interview link is invalid or has expired."} If you believe this is a
            mistake, contact the recruiter who invited you.
          </p>
        </div>
      </Shell>
    );
  }

  // ---- Pre-join lobby (Meet "Ready to join?") -------------------------------
  if (phase === "ready" || phase === "connecting") {
    return (
      <Shell>
        <div className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-10 lg:flex-row lg:gap-14">
          {/* Preview tile */}
          <div className="relative aspect-video w-full max-w-xl overflow-hidden rounded-2xl bg-zinc-900 ring-1 ring-zinc-800">
            <div className="flex h-full flex-col items-center justify-center gap-4">
              <Avatar kind="you" size="lg" speaking={false} />
              <p className="text-sm text-zinc-400">Camera starts when you join</p>
            </div>
            <div className="absolute bottom-3 left-3 rounded-md bg-black/50 px-2.5 py-1 text-sm text-zinc-100">
              {info?.candidate_name || "You"}
            </div>
            <div className="absolute bottom-3 right-3 flex h-9 w-9 items-center justify-center rounded-full bg-emerald-600">
              <Mic className="h-4 w-4 text-white" />
            </div>
          </div>

          {/* Join card */}
          <div className="w-full max-w-sm text-center">
            <h1 className="text-2xl font-semibold text-zinc-50">{info?.job_title || "AI Interview"}</h1>
            <p className="mt-1 text-zinc-400">
              {info?.candidate_name ? `Welcome, ${info.candidate_name}.` : "Welcome."} Ready when you are.
            </p>

            {error && (
              <div className="mt-5 flex items-start gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-left text-sm text-amber-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              onClick={start}
              disabled={phase === "connecting"}
              className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-full bg-blue-600 px-6 py-3.5 font-medium text-white transition hover:bg-blue-500 disabled:opacity-70"
            >
              {phase === "connecting" ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" /> Connecting…
                </>
              ) : (
                "Join now"
              )}
            </button>
            <p className="mt-4 text-xs text-zinc-500">
              Find a quiet place and allow camera &amp; microphone access when prompted. The AI
              interviewer will greet you as soon as you join.
            </p>
          </div>
        </div>
      </Shell>
    );
  }

  // ---- Ended ----------------------------------------------------------------
  if (phase === "ended") {
    return (
      <Shell>
        <div className="flex flex-1 flex-col items-center justify-center px-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/10">
            <CheckCircle2 className="h-8 w-8 text-emerald-400" />
          </div>
          <h1 className="mt-5 text-xl font-semibold text-zinc-100">Interview ended</h1>
          <p className="mt-2 max-w-md text-center text-zinc-400">
            Thanks{info?.candidate_name ? `, ${info.candidate_name}` : ""}! Your responses have been
            recorded. You can close this window — the recruiter will be in touch.
          </p>
        </div>
      </Shell>
    );
  }

  // ---- Live call (Meet/Zoom stage) ------------------------------------------
  const latest = lastTurns(transcript, 2);

  return (
    <div className="flex h-screen flex-col bg-[#202124] text-zinc-100">
      {/* Top bar */}
      <header className="flex items-center justify-between px-4 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-medium text-zinc-200">{info?.job_title || "AI Interview"}</h1>
          <p className="truncate text-xs text-zinc-500">{info?.candidate_name || "you"}</p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {/* Topic progress (covered / total) from the live goal stream. */}
          {goals.length > 0 && (
            <span className="rounded-full bg-zinc-800 px-2.5 py-1 text-zinc-300">
              Topics {goals.filter((g) => g.progress >= 0.5 || /complete|cover|done/i.test(g.status)).length}/{goals.length}
            </span>
          )}
          {/* Soft countdown (guideline only — the interview ends on completion, not a hard cap). */}
          {info?.time_limit_seconds ? (
            (() => {
              const remaining = Math.max(0, info.time_limit_seconds - elapsed);
              return (
                <span className={`tabular-nums ${remaining <= 60 ? "text-amber-400" : "text-zinc-500"}`}>
                  {remaining > 0 ? `${fmtTime(remaining)} left` : "time’s up"}
                </span>
              );
            })()
          ) : null}
          <span className="tabular-nums text-zinc-400">{fmtTime(elapsed)}</span>
          <span
            className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 ${
              connected ? "bg-emerald-900/40 text-emerald-300" : "bg-zinc-800 text-zinc-400"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "bg-zinc-500"}`} />
            {connected ? "Live" : "Connecting"}
          </span>
          {/* Interviewer (bot) presence — so the candidate knows if it joined or left. */}
          <span
            className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 ${
              agentPresent === false
                ? "bg-red-900/40 text-red-300"
                : agentPresent
                ? "bg-emerald-900/40 text-emerald-300"
                : "bg-zinc-800 text-zinc-400"
            }`}
          >
            <Bot className="h-3 w-3" />
            {agentPresent === false
              ? "Interviewer left"
              : agentPresent
              ? "Interviewer present"
              : "Interviewer connecting…"}
          </span>
          {demoMode && (
            <span className="flex items-center gap-1.5 rounded-full bg-amber-900/40 px-2.5 py-1 text-amber-300">
              <User className="h-3 w-3" /> Demo voice
            </span>
          )}
        </div>
      </header>

      {error && (
        <div className="mx-4 flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="flex-1">{error}</div>
          <button onClick={() => setError(null)} className="text-amber-300/70 hover:text-amber-200" aria-label="Dismiss">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {audioBlocked && (
        <button
          onClick={enableAudio}
          className="mx-4 flex items-center gap-2 rounded-xl border border-blue-500/40 bg-blue-500/10 p-3 text-left text-sm text-blue-200 transition hover:bg-blue-500/20"
        >
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>Your browser blocked audio. <span className="font-semibold underline">Tap here to enable sound</span> and hear the interviewer.</span>
        </button>
      )}

      {/* Stage + side panel. Stack vertically on phones (tiles on top, the
          transcript + chat box below) so the chat box is reachable; switch to a
          side-by-side row on sm+ screens. Without flex-col on mobile the panel
          got squeezed off-screen — candidates saw audio but no usable UI. */}
      <div className="flex min-h-0 flex-1 flex-col gap-3 px-3 pb-2 sm:flex-row">
        <main className="relative flex min-w-0 flex-1 items-center justify-center">
          <div className="grid w-full max-w-5xl gap-3 sm:grid-cols-2">
            <Tile
              kind="agent"
              label="AI Interviewer"
              speaking={activeSpeaker === "agent"}
              muted={false}
            />
            <Tile
              kind="you"
              label={info?.candidate_name || "You"}
              speaking={activeSpeaker === "you" && micEnabled}
              muted={!micEnabled}
              videoRef={selfVideoRef}
              showVideo={cameraEnabled}
            />
          </div>

          {/* Captions overlay */}
          {showCaptions && latest.length > 0 && (
            <div className="pointer-events-none absolute bottom-3 left-1/2 w-full max-w-3xl -translate-x-1/2 px-4">
              <div className="space-y-1 rounded-xl bg-black/70 p-3 text-center backdrop-blur">
                {latest.map((t, i) => (
                  <p key={i} className="text-sm leading-snug text-zinc-100">
                    <span className="font-semibold text-zinc-400">
                      {t.speaker === "agent" ? "Interviewer" : "You"}:{" "}
                    </span>
                    {t.text}
                  </p>
                ))}
              </div>
            </div>
          )}
        </main>

        {/* Side panel */}
        {showPanel && (
          <aside className="flex w-full max-w-sm flex-col overflow-hidden rounded-2xl bg-zinc-900 ring-1 ring-zinc-800 sm:w-96">
            <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
              <span className="flex items-center gap-2 text-sm font-medium text-zinc-200">
                <MessageSquareText className="h-4 w-4" /> Transcript
              </span>
              <button onClick={() => setShowPanel(false)} className="text-zinc-500 hover:text-zinc-300" aria-label="Close panel">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
              {transcript.length === 0 && pending.length === 0 ? (
                <p className="text-xs text-zinc-600">The conversation will appear here.</p>
              ) : (
                <>
                  {transcript.map((t, i) => <Bubble key={i} speaker={t.speaker} text={t.text} />)}
                  {/* Optimistic, not-yet-confirmed candidate lines */}
                  {pending.map((t, i) => <Bubble key={`p${i}`} speaker="candidate" text={t} pending />)}
                </>
              )}
            </div>

            <form onSubmit={submitChat} className="flex gap-2 border-t border-zinc-800 p-3">
              <input
                value={chat}
                onChange={(e) => setChat(e.target.value)}
                placeholder="Type instead of speaking…"
                disabled={sending}
                className="flex-1 rounded-full border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm outline-none focus:border-blue-500 disabled:opacity-60"
              />
              <button
                type="submit"
                disabled={sending || !chat.trim()}
                className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-600 text-white transition hover:bg-blue-500 disabled:opacity-50"
                aria-label="Send"
              >
                <Send className={`h-4 w-4 ${sending ? "animate-pulse" : ""}`} />
              </button>
            </form>
          </aside>
        )}
      </div>

      {/* Control bar */}
      <footer className="flex items-center justify-center gap-3 py-4">
        <ControlButton
          onClick={toggleMic}
          active={!micEnabled}
          label={micEnabled ? "Mute microphone" : "Unmute microphone"}
        >
          {micEnabled ? <Mic className="h-5 w-5" /> : <MicOff className="h-5 w-5" />}
        </ControlButton>

        <ControlButton
          onClick={toggleCamera}
          active={!cameraEnabled}
          label={cameraEnabled ? "Turn camera off" : "Turn camera on"}
        >
          {cameraEnabled ? <Video className="h-5 w-5" /> : <VideoOff className="h-5 w-5" />}
        </ControlButton>

        <ControlButton
          onClick={() => setShowCaptions((v) => !v)}
          active={!showCaptions}
          label={showCaptions ? "Hide captions" : "Show captions"}
        >
          <Captions className="h-5 w-5" />
        </ControlButton>

        <ControlButton
          onClick={() => setShowPanel((v) => !v)}
          highlighted={showPanel}
          label="Show transcript"
        >
          <MessageSquareText className="h-5 w-5" />
        </ControlButton>

        <button
          onClick={leave}
          className="flex h-12 items-center gap-2 rounded-full bg-red-600 px-6 font-medium text-white transition hover:bg-red-500"
          aria-label="Leave interview"
        >
          <PhoneOff className="h-5 w-5" /> Leave
        </button>
      </footer>
    </div>
  );
}

/* ------------------------------------------------------------------ helpers */

function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

function lastTurns(transcript: { speaker: string; text: string }[], n: number) {
  return transcript.slice(-n);
}

function describeMediaError(e: unknown): string {
  const err = e as { name?: string; message?: string };
  const name = err?.name || "";
  const msg = err?.message || "";
  if (name === "NotAllowedError" || /permission|denied/i.test(msg))
    return "Microphone access is blocked. Allow microphone access in your browser, then click “Join now” again.";
  if (name === "NotFoundError" || /not\s*found|no .*(microphone|device)/i.test(msg))
    return "No microphone was found. Connect a microphone (or use a device that has one) and try again.";
  if (/audiocontext|webaudio|audio (device|renderer)/i.test(msg))
    return "Your browser couldn’t start audio. Make sure this device has working speakers and a microphone, then try again.";
  return "We couldn’t start the interview audio. Check your internet connection and microphone, then try again.";
}

/* --------------------------------------------------------------- components */

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-screen flex-col bg-[#202124] text-zinc-100">{children}</div>;
}

function Avatar({
  kind,
  size = "md",
  speaking,
}: {
  kind: "agent" | "you";
  size?: "md" | "lg";
  speaking: boolean;
}) {
  const isAgent = kind === "agent";
  const dim = size === "lg" ? "h-28 w-28" : "h-20 w-20";
  const icon = size === "lg" ? "h-12 w-12" : "h-9 w-9";
  return (
    <div
      className={`relative flex ${dim} items-center justify-center rounded-full ${
        isAgent ? "bg-blue-600/90" : "bg-zinc-700"
      } transition-all ${speaking ? "ring-4 ring-blue-400/70" : "ring-0"}`}
    >
      {speaking && <span className="absolute inset-0 animate-ping rounded-full bg-blue-400/20" />}
      {isAgent ? <Bot className={`${icon} text-white`} /> : <User className={`${icon} text-zinc-300`} />}
    </div>
  );
}

function Tile({
  kind,
  label,
  speaking,
  muted,
  videoRef,
  showVideo,
}: {
  kind: "agent" | "you";
  label: string;
  speaking: boolean;
  muted: boolean;
  videoRef?: React.Ref<HTMLVideoElement>;
  showVideo?: boolean;
}) {
  return (
    <div
      className={`relative flex aspect-video items-center justify-center overflow-hidden rounded-2xl bg-zinc-900 transition-all ${
        speaking ? "ring-2 ring-blue-400" : "ring-1 ring-zinc-800"
      }`}
    >
      {/* Local self-view. Kept mounted (hidden) when the camera is off so the
          attach effect always has an element to bind the track to. Mirrored, like
          every video-call self-view. */}
      {kind === "you" && (
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className={`absolute inset-0 h-full w-full -scale-x-100 object-cover ${showVideo ? "" : "hidden"}`}
        />
      )}
      <div className={`flex flex-col items-center gap-3 ${showVideo ? "hidden" : ""}`}>
        <SpeakingBars active={speaking} color="#60a5fa" bars={5} className="text-blue-400" />
      </div>

      <div className="absolute bottom-3 left-3 flex max-w-[70%] items-center gap-2 truncate rounded-md bg-black/50 px-2.5 py-1 text-sm text-zinc-100">
        {speaking && <SpeakingBars active color="#7dd3fc" bars={3} />}
        <span className="truncate">{label}</span>
      </div>
      <div
        className={`absolute bottom-3 right-3 flex h-8 w-8 items-center justify-center rounded-full ${
          muted ? "bg-red-600" : "bg-black/50"
        }`}
      >
        {muted ? <MicOff className="h-4 w-4 text-white" /> : <Mic className="h-4 w-4 text-zinc-200" />}
      </div>
    </div>
  );
}

function ControlButton({
  children,
  onClick,
  active,
  highlighted,
  label,
}: {
  children: React.ReactNode;
  onClick: () => void;
  active?: boolean; // "off"/danger state (e.g. muted)
  highlighted?: boolean; // panel open
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className={`flex h-12 w-12 items-center justify-center rounded-full transition ${
        active
          ? "bg-red-600 text-white hover:bg-red-500"
          : highlighted
          ? "bg-blue-600 text-white hover:bg-blue-500"
          : "bg-zinc-700 text-zinc-100 hover:bg-zinc-600"
      }`}
    >
      {children}
    </button>
  );
}

function Bubble({ speaker, text, pending }: { speaker: string; text: string; pending?: boolean }) {
  const isAgent = speaker === "agent";
  return (
    <div className={`flex ${isAgent ? "justify-start" : "justify-end"}`}>
      <div
        className={`max-w-[85%] rounded-2xl p-3 text-sm shadow-sm ${
          isAgent ? "rounded-bl-none bg-zinc-800 text-zinc-200" : "rounded-br-none bg-blue-600 text-white"
        }`}
      >
        {text}
      </div>
    </div>
  );
}
