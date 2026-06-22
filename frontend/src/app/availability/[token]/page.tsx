"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

type FormData = {
  candidate_name: string | null;
  job_title: string;
  org_name: string | null;
  org_color: string;
  slots: string[];
  already_submitted: boolean;
  submitted_slot: string | null;
  confirmed_slot: string | null;
};

export default function AvailabilityPage() {
  const params = useParams();
  const token = params?.token as string;

  const [form, setForm] = useState<FormData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [custom, setCustom] = useState<string>("");
  const [useCustom, setUseCustom] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (!token) return;
    api.getAvailabilityForm(token)
      .then((data) => {
        setForm(data);
        if (data.already_submitted) setSubmitted(true);
      })
      .catch(() => setError("This link is invalid or has expired."));
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const slot = useCustom ? custom.trim() : selected;
    if (!slot) return;
    setSubmitting(true);
    try {
      await api.submitAvailability(token, useCustom ? { custom_time: slot } : { selected_slot: slot });
      setSubmitted(true);
    } catch {
      setError("Failed to submit. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const color = form?.org_color || "#1C99BF";

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#04111B] px-4">
        <div className="max-w-md text-center">
          <div className="mb-4 text-4xl">🔗</div>
          <h1 className="mb-2 text-xl font-semibold text-white">Link unavailable</h1>
          <p className="text-sm text-gray-400">{error}</p>
        </div>
      </div>
    );
  }

  if (!form) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#04111B]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-white" />
      </div>
    );
  }

  if (submitted) {
    const slot = form.submitted_slot || form.confirmed_slot || "";
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#04111B] px-4">
        <div
          className="w-full max-w-md rounded-2xl border p-8 text-center"
          style={{ background: "rgba(255,255,255,0.04)", borderColor: "rgba(255,255,255,0.08)" }}
        >
          <div
            className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl text-2xl"
            style={{ background: `${color}22` }}
          >
            ✅
          </div>
          <h1 className="mb-2 text-xl font-semibold text-white">
            {form.confirmed_slot ? "Interview Confirmed" : "Availability Received"}
          </h1>
          <p className="text-sm text-gray-400">
            {form.confirmed_slot
              ? `Your interview is confirmed for:`
              : `We've received your preferred time:`}
          </p>
          {slot && (
            <p
              className="mt-3 rounded-xl px-4 py-3 text-sm font-medium"
              style={{ background: `${color}18`, color }}
            >
              {slot}
            </p>
          )}
          {!form.confirmed_slot && (
            <p className="mt-4 text-xs text-gray-500">
              Our team will confirm your interview slot and send a confirmation email shortly.
            </p>
          )}
          <p className="mt-6 text-xs text-gray-600">
            {form.org_name || "Recruitment Team"} · {form.job_title}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#04111B] px-4 py-12">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="mb-8 text-center">
          <div
            className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl text-xl font-bold text-white"
            style={{ background: color }}
          >
            {(form.org_name || "R").slice(0, 1).toUpperCase()}
          </div>
          <p className="text-xs font-medium uppercase tracking-widest text-gray-500">
            {form.org_name || "Recruitment"}
          </p>
          <h1 className="mt-2 text-2xl font-semibold text-white">
            Schedule Your Interview
          </h1>
          <p className="mt-1 text-sm text-gray-400">
            {form.candidate_name ? `Hi ${form.candidate_name}, ` : ""}
            you&apos;ve been shortlisted for <strong className="text-white">{form.job_title}</strong>.
            Pick a time that works for you.
          </p>
        </div>

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border p-6"
          style={{ background: "rgba(255,255,255,0.04)", borderColor: "rgba(255,255,255,0.08)" }}
        >
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Available slots (Pakistan Standard Time)
          </p>

          <div className="space-y-2">
            {form.slots.map((slot) => (
              <label
                key={slot}
                className="flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 transition-all"
                style={{
                  borderColor: selected === slot && !useCustom ? color : "rgba(255,255,255,0.07)",
                  background: selected === slot && !useCustom ? `${color}12` : "rgba(255,255,255,0.02)",
                }}
              >
                <input
                  type="radio"
                  name="slot"
                  value={slot}
                  checked={selected === slot && !useCustom}
                  onChange={() => { setSelected(slot); setUseCustom(false); }}
                  className="sr-only"
                />
                <span
                  className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 transition-colors"
                  style={{
                    borderColor: selected === slot && !useCustom ? color : "rgba(255,255,255,0.2)",
                    background: selected === slot && !useCustom ? color : "transparent",
                  }}
                >
                  {selected === slot && !useCustom && (
                    <span className="block h-1.5 w-1.5 rounded-full bg-white" />
                  )}
                </span>
                <span className="text-sm text-gray-200">{slot}</span>
              </label>
            ))}

            {/* Custom time option */}
            <label
              className="flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3 transition-all"
              style={{
                borderColor: useCustom ? color : "rgba(255,255,255,0.07)",
                background: useCustom ? `${color}12` : "rgba(255,255,255,0.02)",
              }}
            >
              <input
                type="radio"
                name="slot"
                checked={useCustom}
                onChange={() => setUseCustom(true)}
                className="sr-only"
              />
              <span
                className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 transition-colors"
                style={{
                  borderColor: useCustom ? color : "rgba(255,255,255,0.2)",
                  background: useCustom ? color : "transparent",
                }}
              >
                {useCustom && <span className="block h-1.5 w-1.5 rounded-full bg-white" />}
              </span>
              <div className="flex-1">
                <span className="text-sm text-gray-200">I prefer a different time</span>
                {useCustom && (
                  <input
                    autoFocus
                    type="text"
                    placeholder="e.g. Wednesday Jan 8 at 3:00 PM PKT"
                    value={custom}
                    onChange={(e) => setCustom(e.target.value)}
                    className="mt-2 w-full rounded-lg border bg-transparent px-3 py-2 text-sm text-white placeholder-gray-600 outline-none"
                    style={{ borderColor: "rgba(255,255,255,0.12)" }}
                  />
                )}
              </div>
            </label>
          </div>

          <button
            type="submit"
            disabled={submitting || (!selected && !custom.trim())}
            className="mt-6 w-full rounded-xl py-3 text-sm font-semibold text-white transition-all disabled:opacity-40"
            style={{ background: color }}
          >
            {submitting ? "Submitting…" : "Confirm Availability"}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-gray-600">
          This link is valid for 72 hours and can only be used once.
        </p>
      </div>
    </div>
  );
}
