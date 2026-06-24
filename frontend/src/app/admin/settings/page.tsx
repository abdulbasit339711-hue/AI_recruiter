"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "react-hot-toast";
import { Settings, Save, Info, FlaskConical } from "lucide-react";

type Setting = {
  key: string;
  value: string | null;
  label: string;
  description: string;
  type: string;
  min?: number;
  max?: number;
};

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [testingInterview, setTestingInterview] = useState(false);

  useEffect(() => {
    api.getSettings()
      .then((data) => {
        setSettings(data);
        const initial: Record<string, string> = {};
        data.forEach((s) => { initial[s.key] = s.value ?? ""; });
        setValues(initial);
      })
      .catch(() => toast.error("Failed to load settings."))
      .finally(() => setLoading(false));
  }, []);

  async function handleTestInterview() {
    setTestingInterview(true);
    try {
      const data = await api.createTestInterview();
      window.open(data.interview_url, "_blank");
      toast.success(`Test interview opened for ${data.candidate_name} — ${data.job_title}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to create test interview";
      toast.error(msg);
    } finally {
      setTestingInterview(false);
    }
  }

  async function handleSave(key: string) {
    setSaving((p) => ({ ...p, [key]: true }));
    try {
      await api.updateSetting(key, values[key]);
      toast.success("Setting saved.");
    } catch {
      toast.error("Failed to save setting.");
    } finally {
      setSaving((p) => ({ ...p, [key]: false }));
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <div className="mb-8 flex items-center gap-3">
        <span
          className="flex h-10 w-10 items-center justify-center rounded-xl"
          style={{ background: "rgba(28,153,191,0.12)", color: "#1C99BF" }}
        >
          <Settings className="h-5 w-5" />
        </span>
        <div>
          <h1 className="text-2xl font-bold text-heading">Settings</h1>
          <p className="text-sm text-muted-foreground">Configure system-wide recruitment behaviour.</p>
        </div>
      </div>

      {/* Test Interview card — always visible */}
      <div
        className="mb-6 rounded-2xl p-5"
        style={{ background: "var(--surface-card)", border: "1px solid var(--surface-border)" }}
      >
        <div className="mb-1 flex items-start gap-2">
          <FlaskConical className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#A78BFA" }} />
          <p className="font-semibold text-heading">Test Voice Interview</p>
        </div>
        <p className="mb-4 text-xs text-muted-foreground">
          Opens a live interview room using an existing candidate. Use this to verify that Emily greets correctly and that audio is working end-to-end.
        </p>
        <button
          onClick={handleTestInterview}
          disabled={testingInterview}
          className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition-all disabled:opacity-40"
          style={{ background: "#A78BFA" }}
        >
          <FlaskConical className="h-4 w-4" />
          {testingInterview ? "Generating link…" : "Open Test Interview"}
        </button>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="animate-pulse rounded-2xl p-5"
              style={{ background: "var(--surface-card)", border: "1px solid var(--surface-border)" }}
            >
              <div className="mb-2 h-4 w-40 rounded bg-white/[0.08]" />
              <div className="h-3 w-64 rounded bg-white/[0.05]" />
              <div className="mt-4 h-10 w-full rounded-xl bg-white/[0.06]" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {settings.map((s) => (
            <div
              key={s.key}
              className="rounded-2xl p-5"
              style={{ background: "var(--surface-card)", border: "1px solid var(--surface-border)" }}
            >
              <div className="mb-1 flex items-start gap-2">
                <p className="font-semibold text-heading">{s.label}</p>
              </div>
              <p className="mb-4 flex items-start gap-1.5 text-xs text-muted-foreground">
                <Info className="mt-0.5 h-3 w-3 shrink-0 opacity-60" />
                {s.description}
              </p>

              {s.type === "number" ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min={s.min ?? 0}
                      max={s.max ?? 100}
                      step={1}
                      value={values[s.key] ?? "60"}
                      onChange={(e) => setValues((p) => ({ ...p, [s.key]: e.target.value }))}
                      className="h-2 flex-1 cursor-pointer appearance-none rounded-full bg-white/10 accent-[#1C99BF]"
                    />
                    <span
                      className="w-14 rounded-lg px-2 py-1 text-center text-sm font-bold"
                      style={{ background: "rgba(28,153,191,0.12)", color: "#1C99BF" }}
                    >
                      {values[s.key] ?? "60"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{s.min ?? 0} — never invite</span>
                    <span>100 — only perfect scores</span>
                  </div>
                  {/* Tier context */}
                  <div
                    className="mt-2 rounded-xl p-3 text-xs"
                    style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}
                  >
                    <p className="mb-1.5 font-semibold text-muted-foreground">Score breakdown reference</p>
                    <div className="space-y-1">
                      {[
                        { tier: "Tier 1 — Profile Rules", max: 30, color: "#60A5FA", desc: "spaCy: email, phone, education, experience, keywords" },
                        { tier: "Tier 2 — Semantic Match", max: 40, color: "#A78BFA", desc: "sentence-transformers: resume ↔ JD cosine similarity" },
                        { tier: "Tier 3 — LLM Evaluation", max: 30, color: "#34D399", desc: "Groq: custom prompt evaluation (gated at T1+T2 ≥ 25)" },
                      ].map(({ tier, max, color, desc }) => (
                        <div key={tier} className="flex items-start gap-2">
                          <span
                            className="mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold"
                            style={{ background: `${color}18`, color }}
                          >
                            /{max}
                          </span>
                          <div>
                            <p className="font-medium" style={{ color }}>{tier}</p>
                            <p className="text-muted-foreground/70">{desc}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                    <p className="mt-2 text-muted-foreground/60">
                      A threshold of <strong className="text-[#1C99BF]">{values[s.key] ?? "60"}</strong>/100 means candidates need strong profile signals + good semantic match to receive an interview invitation.
                    </p>
                  </div>
                </div>
              ) : (
                <input
                  type="text"
                  value={values[s.key] ?? ""}
                  onChange={(e) => setValues((p) => ({ ...p, [s.key]: e.target.value }))}
                  className="w-full rounded-xl border bg-transparent px-3 py-2 text-sm text-heading outline-none focus:ring-2 focus:ring-[#1C99BF]/40"
                  style={{ borderColor: "rgba(255,255,255,0.1)" }}
                />
              )}

              <button
                onClick={() => handleSave(s.key)}
                disabled={saving[s.key]}
                className="mt-4 flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition-all disabled:opacity-40"
                style={{ background: "#1C99BF" }}
              >
                <Save className="h-4 w-4" />
                {saving[s.key] ? "Saving…" : "Save"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
