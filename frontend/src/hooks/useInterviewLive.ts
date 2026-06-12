"use client";

import { useEffect, useRef, useState } from "react";
import { interviewEventsUrl } from "@/lib/voice";

export interface TranscriptTurn {
  speaker: string; // "candidate" | "agent"
  text: string;
}

export interface GoalRow {
  title: string;
  progress: number;
  status: string;
}

export interface JudgeEval {
  score: number;
  completeness: number;
  depth: string;
  follow_up_needed: boolean;
  suggested_probe?: string;
}

interface LiveState {
  transcript: TranscriptTurn[];
  goals: GoalRow[];
  judge: JudgeEval | null;
  connected: boolean;
}

function mapGoals(raw: unknown): GoalRow[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((g: Record<string, unknown>) => ({
    title: String(g.title ?? ""),
    progress: Number(g.progress ?? 0),
    status: String(g.status ?? "not_started"),
  }));
}

/** Parse an SSE payload defensively: a malformed/non-object event yields null
 *  instead of throwing inside the listener (which would surface as an uncaught
 *  error) or feeding garbage into React state. */
function parseEventData(e: Event): Record<string, unknown> | null {
  const raw = (e as MessageEvent).data;
  if (typeof raw !== "string") return null;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

/** Subscribe to the voice service's SSE stream and accumulate live interview state.
 *  Pass the interview's sessionId so the stream is scoped to this candidate only.
 *  `seed` is the conversation-so-far returned on a resume; it's shown immediately
 *  (the SSE stream only carries NEW turns, never a replay of history). */
export function useInterviewLive(
  enabled: boolean,
  sessionId?: string | null,
  seed?: TranscriptTurn[] | null
): LiveState {
  const [transcript, setTranscript] = useState<TranscriptTurn[]>([]);
  const [goals, setGoals] = useState<GoalRow[]>([]);
  const [judge, setJudge] = useState<JudgeEval | null>(null);
  const [connected, setConnected] = useState(false);
  const streamingRef = useRef(false);
  const seededRef = useRef(false);

  // Seed the prior conversation once (resume). Prepend so it sits before any live
  // turn that may have already arrived; the historical turns are always older.
  useEffect(() => {
    if (seededRef.current || !seed || seed.length === 0) return;
    seededRef.current = true;
    setTranscript((prev) => [...seed, ...prev]);
  }, [seed]);

  useEffect(() => {
    if (!enabled) return;
    const es = new EventSource(interviewEventsUrl(sessionId));
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);

    es.addEventListener("transcript", (e) => {
      const d = parseEventData(e);
      if (!d) return;
      // When scoped to a session, ignore any transcript that isn't ours (e.g. the
      // default/testing bot's events, which carry no session_id).
      if (sessionId && d.session_id !== sessionId) return;
      const text = typeof d.text === "string" ? d.text : "";
      const speaker = typeof d.speaker === "string" ? d.speaker : "agent";
      if (!text) return;
      if (speaker === "agent" && d.streaming) {
        setTranscript((prev) => {
          if (streamingRef.current && prev.length && prev[prev.length - 1].speaker === "agent") {
            const copy = [...prev];
            copy[copy.length - 1] = { speaker: "agent", text: copy[copy.length - 1].text + " " + text };
            return copy;
          }
          streamingRef.current = true;
          return [...prev, { speaker: "agent", text }];
        });
      } else {
        streamingRef.current = false;
        setTranscript((prev) => [...prev, { speaker, text }]);
      }
    });

    const onGoals = (e: Event) => {
      const d = parseEventData(e);
      if (!d) return;
      const summary = d.summary as Record<string, unknown> | undefined;
      const goalsObj = d.goals as Record<string, unknown> | undefined;
      const g = summary?.goals ?? goalsObj?.goals ?? d.goals;
      const mapped = mapGoals(g);
      if (mapped.length) setGoals(mapped);
    };
    es.addEventListener("goals_initialized", onGoals);
    es.addEventListener("goal_progress_update", onGoals);

    es.addEventListener("judge_evaluation", (e) => {
      const d = parseEventData(e);
      if (!d) return;
      setJudge({
        score: Number(d.score ?? 0),
        completeness: Number(d.completeness ?? 0),
        depth: String(d.depth ?? "unknown"),
        follow_up_needed: Boolean(d.follow_up_needed),
        suggested_probe: typeof d.suggested_probe === "string" ? d.suggested_probe : undefined,
      });
    });

    return () => es.close();
  }, [enabled, sessionId]);

  return { transcript, goals, judge, connected };
}
