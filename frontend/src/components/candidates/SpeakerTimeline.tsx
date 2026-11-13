"use client";

import { useMemo } from "react";

interface Turn {
  speaker: string;
  text: string;
  timestamp?: string | null;
}

interface Seg {
  speaker: "agent" | "candidate";
  start: number; // seconds from the first turn
  dur: number;
  text: string;
}

const WORDS_PER_SEC = 2.5; // ~150 wpm, used only where timestamps can't tell us
const MAX_TURN_SEC = 120; // a long silence shouldn't make one turn swallow the chart

const words = (s: string) => (s.match(/[A-Za-z0-9']+/g) ?? []).length;
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

function buildSegments(turns: Turn[]): Seg[] {
  const ts = turns.map((t) => (t.timestamp ? Date.parse(t.timestamp) : NaN));
  const usable = ts.every((x, i) => !Number.isNaN(x) && (i === 0 || x >= ts[i - 1]));
  const est = (t: Turn) => Math.max(2, words(t.text) / WORDS_PER_SEC);
  let clock = 0;
  return turns.map((t, i) => {
    const speaker = t.speaker === "agent" ? "agent" : "candidate";
    const start = usable ? (ts[i] - ts[0]) / 1000 : clock;
    const dur = usable && i < turns.length - 1 ? Math.min(MAX_TURN_SEC, (ts[i + 1] - ts[i]) / 1000) : est(t);
    clock += est(t);
    return { speaker, start, dur: Math.max(dur, 0.5), text: t.text };
  });
}

/** Who held the floor when: an interviewer lane and a candidate lane over the interview's time axis. */
export function SpeakerTimeline({ transcript }: { transcript: Turn[] }) {
  const { segs, total, share, longest, estimated } = useMemo(() => {
    const segs = buildSegments(transcript);
    const total = Math.max(1, ...segs.map((s) => s.start + s.dur));
    const sum = (who: Seg["speaker"]) => segs.filter((s) => s.speaker === who).reduce((a, s) => a + s.dur, 0);
    const c = sum("candidate");
    const a = sum("agent");
    const cand = segs.filter((s) => s.speaker === "candidate");
    return {
      segs,
      total,
      share: c + a ? Math.round((100 * c) / (c + a)) : 0,
      longest: cand.length ? Math.max(...cand.map((s) => s.dur)) : 0,
      estimated: !transcript.every((t) => t.timestamp),
    };
  }, [transcript]);

  if (transcript.length < 2) return null;

  const ticks = Array.from({ length: 5 }, (_, i) => (total * i) / 4);
  const lane = (who: Seg["speaker"], color: string) => (
    <div className="relative h-6 rounded bg-foreground/[0.06]">
      {segs.filter((s) => s.speaker === who).map((s, i) => (
        <div
          key={i}
          title={`${mmss(s.start)} · ${Math.round(s.dur)}s — ${s.text.slice(0, 160)}`}
          className="absolute top-0.5 bottom-0.5 rounded-sm"
          style={{ left: `${(s.start / total) * 100}%`, width: `${Math.max(0.5, (s.dur / total) * 100)}%`, background: color }}
        />
      ))}
    </div>
  );

  return (
    <section className="rounded-xl glass-tile p-4">
      <h4 className="mb-3 text-sm font-semibold text-heading">
        Speaker timeline
        <span className="ml-2 text-[11px] font-normal text-muted-foreground">
          {mmss(total)} · candidate held the floor {share}% of the time · longest answer {mmss(longest)}
        </span>
      </h4>
      <div className="space-y-1.5">
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground"><span className="w-20 shrink-0">Interviewer</span><div className="flex-1">{lane("agent", "rgba(160,170,185,0.8)")}</div></div>
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground"><span className="w-20 shrink-0">Candidate</span><div className="flex-1">{lane("candidate", "var(--primary, #1C99BF)")}</div></div>
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <span className="w-20 shrink-0" />
          <div className="flex flex-1 justify-between font-mono">{ticks.map((t, i) => <span key={i}>{mmss(t)}</span>)}</div>
        </div>
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">
        Hover a block to read the turn.{" "}
        {estimated
          ? "Timestamps were missing for some turns, so durations are estimated from word counts."
          : "Each turn runs from when it was recorded until the next turn (capped at 2 minutes), so it is approximate."}
      </p>
    </section>
  );
}
