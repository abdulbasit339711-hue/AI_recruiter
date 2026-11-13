"use client";

import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Brain, Loader2, Plus, Save, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import type { IqBankQuestion } from "@/types";

const BLANK: Omit<IqBankQuestion, "id"> = { prompt: "", options: ["", "", "", ""], answer: 0, active: true };

/** HR-authored IQ questions. They are served alongside the built-in bank; deleting only
 *  deactivates, so tests already in flight still score. */
export function IqQuestionBankEditor() {
  const [rows, setRows] = useState<(Omit<IqBankQuestion, "id"> & { id?: number })[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | "new" | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await api.listIqQuestions());
    } catch (e) {
      toast.error((e as Error).message || "Failed to load IQ questions");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const patch = (i: number, f: Partial<IqBankQuestion>) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...f } : r)));
  const setOption = (i: number, k: number, v: string) =>
    patch(i, { options: rows[i].options.map((o, j) => (j === k ? v : o)) });

  async function save(i: number) {
    const r = rows[i];
    setBusy(r.id ?? "new");
    try {
      const saved = await api.saveIqQuestion({ ...r, options: r.options.map((o) => o.trim()).filter(Boolean) });
      setRows((rs) => rs.map((x, j) => (j === i ? saved : x)));
      toast.success("Saved — applies to the next test");
    } catch (e) {
      toast.error((e as Error).message || "Save failed (need 2+ options and a valid correct answer)");
    } finally {
      setBusy(null);
    }
  }

  async function remove(i: number) {
    const r = rows[i];
    if (r.id == null) return setRows((rs) => rs.filter((_, j) => j !== i));
    setBusy(r.id);
    try {
      await api.deleteIqQuestion(r.id);
      patch(i, { active: false });
      toast.success("Question deactivated");
    } catch (e) {
      toast.error((e as Error).message || "Delete failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mb-6 rounded-2xl p-5" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-heading">
          <Brain className="h-4 w-4" /> IQ test questions
        </h2>
        <button
          onClick={() => setRows((rs) => [...rs, { ...BLANK }])}
          className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs hover:bg-white/5"
        >
          <Plus className="h-3.5 w-3.5" /> Add question
        </button>
      </div>
      <p className="mb-4 text-xs text-muted-foreground">Your questions are mixed with the built-in set. Pick the correct option with the radio button.</p>
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">No custom questions yet.</p>
      ) : (
        <div className="space-y-4">
          {rows.map((r, i) => (
            <div key={r.id ?? `new-${i}`} className={`space-y-2 rounded-xl border border-border p-3 ${r.active ? "" : "opacity-50"}`}>
              <input
                value={r.prompt}
                onChange={(e) => patch(i, { prompt: e.target.value })}
                placeholder="Question"
                className="w-full rounded-lg border border-border bg-transparent px-3 py-2 text-sm"
              />
              {r.options.map((o, k) => (
                <label key={k} className="flex items-center gap-2 text-sm">
                  <input type="radio" checked={r.answer === k} onChange={() => patch(i, { answer: k })} />
                  <input
                    value={o}
                    onChange={(e) => setOption(i, k, e.target.value)}
                    placeholder={`Option ${k + 1}`}
                    className="flex-1 rounded-lg border border-border bg-transparent px-2 py-1.5 text-sm"
                  />
                </label>
              ))}
              <div className="flex items-center justify-between pt-1">
                <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <input type="checkbox" checked={r.active} onChange={(e) => patch(i, { active: e.target.checked })} /> Active
                </label>
                <div className="flex gap-2">
                  <button onClick={() => remove(i)} disabled={busy === (r.id ?? "new")} className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs hover:bg-white/5 disabled:opacity-50">
                    <Trash2 className="h-3.5 w-3.5" /> {r.id == null ? "Discard" : "Deactivate"}
                  </button>
                  <button onClick={() => save(i)} disabled={busy === (r.id ?? "new")} className="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-xs text-primary-foreground disabled:opacity-50">
                    <Save className="h-3.5 w-3.5" /> Save
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
