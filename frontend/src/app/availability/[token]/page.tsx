"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { ChevronLeft, ChevronRight, Clock, Check } from "lucide-react";
import { api } from "@/lib/api";

// ─── Date helpers (all relative to PKT = UTC+5) ───────────────────────────────

function todayPKT(): Date {
  const now = new Date();
  const pkt = new Date(now.getTime() + now.getTimezoneOffset() * 60_000 + 5 * 60 * 60 * 1000);
  return new Date(pkt.getFullYear(), pkt.getMonth(), pkt.getDate());
}

function getAvailableDates(n = 14): Date[] {
  const dates: Date[] = [];
  const today = todayPKT();
  let d = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  while (dates.length < n) {
    const dow = d.getDay();
    if (dow >= 1 && dow <= 5) dates.push(new Date(d));
    d.setDate(d.getDate() + 1);
  }
  return dates;
}

function isSameDay(a: Date, b: Date) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

// Mon-first calendar grid for a given month
function buildCells(year: number, month: number): (Date | null)[] {
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDow = (new Date(year, month, 1).getDay() + 6) % 7; // Mon=0
  const cells: (Date | null)[] = [
    ...Array<null>(firstDow).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => new Date(year, month, i + 1)),
  ];
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

// ─── Slot config ──────────────────────────────────────────────────────────────

const SLOT_HOURS = [
  { hour: 9,  label: "9:00 AM"  },
  { hour: 10, label: "10:00 AM" },
  { hour: 11, label: "11:00 AM" },
  { hour: 14, label: "2:00 PM"  },
  { hour: 15, label: "3:00 PM"  },
  { hour: 16, label: "4:00 PM"  },
];

const MONTH_NAMES = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];
const MONTH_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const DAY_NAMES   = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
const DOW_LABELS  = ["Mo","Tu","We","Th","Fr","Sa","Su"];

function formatSlot(date: Date, hour: number): string {
  const h = hour > 12 ? hour - 12 : hour;
  const ampm = hour >= 12 ? "PM" : "AM";
  return `${DAY_NAMES[date.getDay()]}, ${MONTH_SHORT[date.getMonth()]} ${date.getDate()} at ${h}:00 ${ampm} PKT`;
}

function formatDayHeading(date: Date): string {
  return `${DAY_NAMES[date.getDay()]}, ${MONTH_SHORT[date.getMonth()]} ${date.getDate()}`;
}

// ─── Types ───────────────────────────────────────────────────────────────────

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

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AvailabilityPage() {
  const params = useParams();
  const token = params?.token as string;

  const [form, setForm]             = useState<FormData | null>(null);
  const [error, setError]           = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted]   = useState(false);

  const availableDates = useMemo(() => getAvailableDates(14), []);
  const [viewYear,  setViewYear]  = useState(() => availableDates[0]?.getFullYear() ?? new Date().getFullYear());
  const [viewMonth, setViewMonth] = useState(() => availableDates[0]?.getMonth()    ?? new Date().getMonth());
  const [selDate, setSelDate]     = useState<Date | null>(null);
  const [selHour, setSelHour]     = useState<number | null>(null);

  useEffect(() => {
    if (!token) return;
    api.getAvailabilityForm(token)
      .then(data => {
        setForm(data);
        if (data.already_submitted) setSubmitted(true);
      })
      .catch(() => setError("This link is invalid or has expired."));
  }, [token]);

  const color = form?.org_color || "#1C99BF";

  const cells = useMemo(() => buildCells(viewYear, viewMonth), [viewYear, viewMonth]);

  const isAvailable = (d: Date | null): boolean =>
    !!d && availableDates.some(a => isSameDay(a, d));

  const prevMonth = () => {
    if (viewMonth === 0) { setViewMonth(11); setViewYear(y => y - 1); }
    else setViewMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (viewMonth === 11) { setViewMonth(0); setViewYear(y => y + 1); }
    else setViewMonth(m => m + 1);
  };

  async function handleConfirm() {
    if (!selDate || selHour === null) return;
    setSubmitting(true);
    try {
      await api.submitAvailability(token, { selected_slot: formatSlot(selDate, selHour) });
      setForm(f => f ? { ...f, submitted_slot: formatSlot(selDate!, selHour!) } : f);
      setSubmitted(true);
    } catch {
      setError("Failed to submit. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  // ─── States ──────────────────────────────────────────────────────────────

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
            className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl"
            style={{ background: `${color}22`, color }}
          >
            <Check className="h-7 w-7" />
          </div>
          <h1 className="mb-2 text-xl font-semibold text-white">
            {form.confirmed_slot ? "Interview Confirmed" : "Availability Received"}
          </h1>
          <p className="text-sm text-gray-400">
            {form.confirmed_slot ? "Your interview is confirmed for:" : "We received your preferred time:"}
          </p>
          {slot && (
            <p className="mt-3 rounded-xl px-4 py-3 text-sm font-medium" style={{ background: `${color}18`, color }}>
              {slot}
            </p>
          )}
          {!form.confirmed_slot && (
            <p className="mt-4 text-xs text-gray-500">
              Our team will confirm and send a calendar invite shortly.
            </p>
          )}
          <p className="mt-6 text-xs text-gray-600">
            {form.org_name || "Recruitment Team"} · {form.job_title}
          </p>
        </div>
      </div>
    );
  }

  // ─── Calendar picker ──────────────────────────────────────────────────────

  const selectedSlotLabel = selDate && selHour !== null ? formatSlot(selDate, selHour) : null;

  const weeks: (Date | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  return (
    <div className="flex min-h-screen flex-col items-center bg-[#04111B] px-4 py-12">
      {/* Header */}
      <div className="mb-8 text-center">
        <div
          className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl text-xl font-bold text-white select-none"
          style={{ background: color }}
        >
          {(form.org_name || "R").slice(0, 1).toUpperCase()}
        </div>
        <p className="text-xs font-medium uppercase tracking-widest text-gray-500">
          {form.org_name || "Recruitment"}
        </p>
        <h1 className="mt-2 text-2xl font-semibold text-white">Schedule Your Interview</h1>
        <p className="mt-1 text-sm text-gray-400">
          {form.candidate_name ? `Hi ${form.candidate_name} — ` : ""}
          shortlisted for{" "}
          <strong className="text-white">{form.job_title}</strong>.
          Pick a day and time (PKT).
        </p>
      </div>

      {/* Main card */}
      <div
        className="w-full max-w-2xl overflow-hidden rounded-2xl border"
        style={{ background: "rgba(255,255,255,0.04)", borderColor: "rgba(255,255,255,0.08)" }}
      >
        <div className="flex flex-col md:flex-row">

          {/* ── Left: month calendar ── */}
          <div className="flex-shrink-0 border-b border-white/[0.06] p-5 md:w-72 md:border-b-0 md:border-r md:border-white/[0.06]">
            {/* Month nav */}
            <div className="mb-4 flex items-center justify-between">
              <button
                onClick={prevMonth}
                className="rounded-lg p-1.5 text-gray-500 transition hover:bg-white/[0.06] hover:text-white"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-sm font-semibold text-white">
                {MONTH_NAMES[viewMonth]} {viewYear}
              </span>
              <button
                onClick={nextMonth}
                className="rounded-lg p-1.5 text-gray-500 transition hover:bg-white/[0.06] hover:text-white"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>

            {/* DOW headers */}
            <div className="mb-1 grid grid-cols-7">
              {DOW_LABELS.map(d => (
                <div key={d} className="py-1 text-center text-[11px] font-medium text-gray-600">{d}</div>
              ))}
            </div>

            {/* Day cells */}
            {weeks.map((week, wi) => (
              <div key={wi} className="grid grid-cols-7">
                {week.map((day, di) => {
                  if (!day) return <div key={di} />;
                  const avail  = isAvailable(day);
                  const isSel  = !!selDate && isSameDay(day, selDate);
                  const isWknd = day.getDay() === 0 || day.getDay() === 6;
                  return (
                    <button
                      key={di}
                      onClick={() => avail && (setSelDate(day), setSelHour(null))}
                      disabled={!avail}
                      className="relative flex h-9 w-full items-center justify-center rounded-lg text-sm transition-all"
                      style={
                        isSel
                          ? { background: color, color: "#fff" }
                          : avail
                          ? { color: "#e5e7eb" }
                          : { color: isWknd ? "#1f2937" : "#374151", cursor: "default" }
                      }
                      onMouseEnter={e => {
                        if (avail && !isSel)
                          (e.currentTarget as HTMLButtonElement).style.background = `${color}30`;
                      }}
                      onMouseLeave={e => {
                        if (avail && !isSel)
                          (e.currentTarget as HTMLButtonElement).style.background = "";
                      }}
                    >
                      {day.getDate()}
                      {avail && !isSel && (
                        <span
                          className="absolute bottom-1 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full"
                          style={{ background: color }}
                        />
                      )}
                    </button>
                  );
                })}
              </div>
            ))}

            <p className="mt-4 flex items-center gap-1.5 text-xs text-gray-600">
              <Clock className="h-3 w-3" /> All times in Pakistan Standard Time
            </p>
          </div>

          {/* ── Right: time slots ── */}
          <div className="flex flex-1 flex-col p-5">
            {!selDate ? (
              <div className="flex flex-1 flex-col items-center justify-center py-10 text-center">
                <div className="mb-3 text-3xl opacity-20">📅</div>
                <p className="text-sm text-gray-600">
                  Select an available date<br />to see time slots
                </p>
              </div>
            ) : (
              <>
                <h3 className="mb-4 text-sm font-semibold text-white">
                  {formatDayHeading(selDate)}
                </h3>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {SLOT_HOURS.map(({ hour, label }) => {
                    const isSel = selHour === hour;
                    return (
                      <button
                        key={hour}
                        onClick={() => setSelHour(hour)}
                        className="rounded-xl border px-3 py-2.5 text-sm font-medium transition-all"
                        style={
                          isSel
                            ? { background: color, borderColor: color, color: "#fff" }
                            : {
                                borderColor: "rgba(255,255,255,0.09)",
                                color: "#9ca3af",
                                background: "rgba(255,255,255,0.02)",
                              }
                        }
                        onMouseEnter={e => {
                          if (!isSel) {
                            const el = e.currentTarget as HTMLButtonElement;
                            el.style.borderColor = `${color}70`;
                            el.style.color = "#e5e7eb";
                          }
                        }}
                        onMouseLeave={e => {
                          if (!isSel) {
                            const el = e.currentTarget as HTMLButtonElement;
                            el.style.borderColor = "rgba(255,255,255,0.09)";
                            el.style.color = "#9ca3af";
                          }
                        }}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Confirm strip */}
        <div className="border-t border-white/[0.06] px-5 py-4">
          {selectedSlotLabel ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-gray-400">
                <span className="font-medium text-white">{selectedSlotLabel}</span>
              </p>
              <button
                onClick={handleConfirm}
                disabled={submitting}
                className="shrink-0 rounded-xl px-6 py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                style={{ background: color }}
              >
                {submitting ? "Confirming…" : "Confirm this time"}
              </button>
            </div>
          ) : (
            <p className="text-center text-xs text-gray-700">
              Choose a date and time above, then confirm.
            </p>
          )}
        </div>
      </div>

      <p className="mt-4 text-center text-xs text-gray-700">
        This link is valid for 72 hours and can only be used once.
      </p>
    </div>
  );
}
