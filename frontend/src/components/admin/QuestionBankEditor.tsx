"use client";

import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Loader2, ListChecks, Save } from "lucide-react";

import { getJobQuestions, updateJobGoal, type QuestionGoal } from "@/lib/voice";

/**
 * Per-job interview question editor. Questions are stored per ROLE in the voice
 * service's goal_templates (jobs sharing a role share the bank), and edited IN PLACE
 * so existing interview goal references stay valid. Edits apply to the NEXT interview.
 */
export function QuestionBankEditor({ jobId }: { jobId: number }) {
  const [open, setOpen] = useState(false);
  const [goals, setGoals] = useState<QuestionGoal[]>([]);
  const [role, setRole] = useState("");
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getJobQuestions(jobId);
      setGoals(data.goals);
      setRole(data.role_type);
    } catch (e) {
      toast.error((e as Error).message || "Failed to load questions");
      setGoals([]);
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  function patch(id: string, fields: Partial<QuestionGoal>) {
    setGoals((gs) => gs.map((g) => (g.id === id ? { ...g, ...fields } : g)));
  }

  async function save(goal: QuestionGoal) {
    setSavingId(goal.id);
    try {
      await updateJobGoal({ ...goal, questions: goal.questions.filter((q) => q.trim()) });
      toast.success(`Saved “${goal.title}” — applies to the next interview`);
    } catch (e) {
      toast.error((e as Error).message || "Save failed");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-md border border-white/10 px-3 py-1.5 text-xs font-medium hover:bg-white/5"
      >
        <ListChecks className="h-4 w-4" /> Questions
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 max-h-[70vh] w-[28rem] overflow-y-auto rounded-xl border border-white/10 bg-popover p-4 shadow-xl">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              Interview questions {role && <>for role <span className="text-foreground">{role}</span></>}
            </p>
            <button onClick={() => setOpen(false)} className="text-xs text-muted-foreground hover:text-foreground">Close</button>
          </div>
          {loading ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </div>
          ) : goals.length === 0 ? (
            <p className="py-6 text-center text-xs text-muted-foreground">
              No question templates yet for this role. They are generated on the first interview.
            </p>
          ) : (
            <div className="space-y-4">
              {goals.map((g) => (
                <div key={g.id} className="rounded-lg border border-white/10 p-3">
                  <input
                    value={g.title}
                    onChange={(e) => patch(g.id, { title: e.target.value })}
                    className="mb-2 w-full rounded-md border border-white/10 bg-background px-2 py-1.5 text-sm font-medium focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <label className="mb-1 block text-[11px] text-muted-foreground">Questions (one per line)</label>
                  <textarea
                    value={g.questions.join("\n")}
                    onChange={(e) => patch(g.id, { questions: e.target.value.split("\n") })}
                    rows={Math.max(2, g.questions.length)}
                    className="w-full rounded-md border border-white/10 bg-background px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <div className="mt-2 flex items-center justify-end">
                    <button
                      onClick={() => save(g)}
                      disabled={savingId === g.id}
                      className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-60"
                    >
                      {savingId === g.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                      Save
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
