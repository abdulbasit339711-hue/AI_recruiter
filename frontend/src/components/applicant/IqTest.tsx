"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Timer, Brain } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import type { IqTestResponse, IqSubmitResponse } from "@/types";

interface IqTestProps {
  jobId: number;
  color?: string;
  /** Called when the screen is finished (or skipped on error). `result` is null
   *  when the test couldn't run — the apply flow then proceeds without a score. */
  onComplete: (result: IqSubmitResponse | null) => void;
}

type Phase = "loading" | "error" | "active" | "submitting";

/** A short, timed aptitude screen taken before résumé upload. Questions are
 *  served (and scored) by the backend; this component only collects choices. */
export function IqTest({ jobId, color = "#1C99BF", onComplete }: IqTestProps) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [test, setTest] = useState<IqTestResponse | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [secondsLeft, setSecondsLeft] = useState(0);
  const answersRef = useRef(answers);
  answersRef.current = answers;
  // Per-question time tracking (client-reported, for the HR breakdown).
  const timesRef = useRef<Record<string, number>>({});
  const questionStartRef = useRef<number>(0);

  const perQuestion = test ? Math.max(15, Math.floor(test.time_limit_seconds / test.total)) : 0;

  // Load the test once.
  useEffect(() => {
    let cancelled = false;
    api
      .getIqTest(jobId)
      .then((t) => {
        if (cancelled) return;
        setTest(t);
        setPhase("active");
      })
      .catch(() => {
        if (!cancelled) setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  const submit = useCallback(async () => {
    if (!test) return;
    setPhase("submitting");
    try {
      const result = await api.submitIqTest(test.test_token, answersRef.current, timesRef.current);
      onComplete(result);
    } catch {
      // Scoring failed (e.g. the test token expired) — don't trap the applicant.
      onComplete(null);
    }
  }, [test, onComplete]);

  const advance = useCallback(() => {
    setIndex((i) => {
      if (!test) return i;
      // Record time spent on the question we're leaving (once).
      const qid = test.questions[i].id;
      if (timesRef.current[qid] === undefined) {
        timesRef.current[qid] = Math.max(0, Math.round((Date.now() - questionStartRef.current) / 1000));
      }
      if (i + 1 >= test.total) {
        void submit();
        return i;
      }
      return i + 1;
    });
  }, [test, submit]);

  // Per-question countdown; auto-advances when it hits zero.
  useEffect(() => {
    if (phase !== "active" || !test) return;
    setSecondsLeft(perQuestion);
    questionStartRef.current = Date.now();  // start this question's clock
    const id = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          clearInterval(id);
          advance();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [index, phase, test, perQuestion, advance]);

  const choose = (qid: string, optIdx: number) => {
    setAnswers((a) => ({ ...a, [qid]: optIdx }));
    advance();
  };

  if (phase === "loading") {
    return (
      <div className="flex items-center justify-center gap-3 glass rounded-2xl p-10 text-sm text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin text-primary" /> Preparing your aptitude screen…
      </div>
    );
  }

  if (phase === "error" || !test) {
    return (
      <div className="space-y-4 glass rounded-2xl p-6 text-center">
        <p className="text-sm text-muted-foreground">
          The aptitude screen is unavailable right now. You can continue with your application.
        </p>
        <button
          onClick={() => onComplete(null)}
          className="w-full rounded-xl px-4 py-3.5 text-sm font-semibold text-white transition hover:opacity-90"
          style={{ background: color }}
        >
          Continue to résumé upload
        </button>
      </div>
    );
  }

  if (phase === "submitting") {
    return (
      <div className="flex items-center justify-center gap-3 glass rounded-2xl p-10 text-sm text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin text-primary" /> Scoring your answers…
      </div>
    );
  }

  const q = test.questions[index];
  const lowTime = secondsLeft <= 5;

  return (
    <div className="space-y-5 glass rounded-2xl p-5">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 font-medium" style={{ color }}>
          <Brain className="h-4 w-4" /> Aptitude screen
        </span>
        <span
          className={`flex items-center gap-1 tabular-nums ${lowTime ? "text-weak" : "text-muted-foreground"}`}
          aria-live="polite"
        >
          <Timer className="h-4 w-4" /> {secondsLeft}s
        </span>
      </div>

      {/* Progress */}
      <div className="flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-foreground/10">
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${(index / test.total) * 100}%`, background: color }}
          />
        </div>
        <span className="text-xs text-muted-foreground">
          {index + 1} / {test.total}
        </span>
      </div>

      <p className="font-display text-lg font-semibold text-heading">{q.prompt}</p>

      <div className="grid gap-2.5">
        {q.options.map((opt, i) => (
          <button
            key={i}
            type="button"
            onClick={() => choose(q.id, i)}
            className="group flex items-center gap-3 rounded-xl border border-border bg-foreground/[0.03] px-4 py-3 text-left text-sm transition hover:border-primary/60 hover:bg-primary/[0.07] focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border font-mono text-xs font-semibold text-muted-foreground transition-colors group-hover:border-primary/60 group-hover:bg-primary group-hover:text-primary-foreground">
              {String.fromCharCode(65 + i)}
            </span>
            <span className="text-foreground">{opt}</span>
          </button>
        ))}
      </div>

      <p className="text-xs text-muted-foreground">
        Pick the best answer — the question advances automatically. Your score is recorded for the
        hiring team but does not block your application.
      </p>
    </div>
  );
}

export default IqTest;
