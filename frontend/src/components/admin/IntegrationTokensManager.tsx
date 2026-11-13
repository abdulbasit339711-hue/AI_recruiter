"use client";

import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Copy, KeyRound, Loader2, Plus } from "lucide-react";

import { api } from "@/lib/api";
import type { IntegrationToken, Org } from "@/types";

/** Per-customer API tokens for the HR platform (HRMS). Admin only: for non-admins the list
 *  call is rejected (403) and the card hides itself. The plaintext is shown once, at creation. */
export function IntegrationTokensManager() {
  const [tokens, setTokens] = useState<IntegrationToken[]>([]);
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [allowed, setAllowed] = useState(true);
  const [loading, setLoading] = useState(true);
  const [orgId, setOrgId] = useState<number | "">("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [fresh, setFresh] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [t, o] = await Promise.all([api.listIntegrationTokens(), api.getOrgs()]);
      setTokens(t);
      setOrgs(o);
    } catch {
      setAllowed(false);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const orgName = (id: number) => orgs.find((o) => o.id === id)?.name ?? `Org #${id}`;

  async function create() {
    if (orgId === "" || !name.trim()) return;
    setCreating(true);
    try {
      const res = await api.createIntegrationToken(orgId, name.trim());
      setFresh(res.token);
      setName("");
      await load();
    } catch (e) {
      toast.error((e as Error).message || "Could not create token");
    } finally {
      setCreating(false);
    }
  }

  async function revoke(t: IntegrationToken) {
    if (!window.confirm(`Revoke "${t.name}"? The HR platform using it will stop working immediately.`)) return;
    try {
      await api.revokeIntegrationToken(t.id);
      toast.success("Token revoked");
      await load();
    } catch (e) {
      toast.error((e as Error).message || "Revoke failed");
    }
  }

  if (!allowed) return null;

  return (
    <div className="mb-6 rounded-2xl p-5" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
      <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-heading">
        <KeyRound className="h-4 w-4" /> HR platform tokens
      </h2>
      <p className="mb-4 text-xs text-muted-foreground">
        One token per customer. It only reaches that customer&apos;s jobs and candidates. Give it to the HR platform as AI_RECRUITER_TOKEN.
      </p>

      {fresh && (
        <div className="mb-4 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs">
          <p className="mb-2 text-amber-200">Copy this token now — it won&apos;t be shown again.</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 break-all rounded bg-black/30 px-2 py-1.5">{fresh}</code>
            <button
              onClick={() => navigator.clipboard.writeText(fresh).then(() => toast.success("Copied"))}
              className="rounded-md border border-border p-1.5 hover:bg-white/5"
              aria-label="Copy token"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
            <button onClick={() => setFresh(null)} className="text-xs text-muted-foreground underline">Done</button>
          </div>
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <select
          value={orgId}
          onChange={(e) => setOrgId(e.target.value ? Number(e.target.value) : "")}
          className="rounded-lg border border-border bg-transparent px-2 py-1.5 text-sm"
        >
          <option value="">Customer…</option>
          {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Label, e.g. acme-hrms"
          className="min-w-[10rem] flex-1 rounded-lg border border-border bg-transparent px-3 py-1.5 text-sm"
        />
        <button
          onClick={create}
          disabled={creating || orgId === "" || !name.trim()}
          className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground disabled:opacity-50"
        >
          {creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />} Create token
        </button>
      </div>

      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : tokens.length === 0 ? (
        <p className="text-xs text-muted-foreground">No tokens yet.</p>
      ) : (
        <ul className="divide-y divide-border text-sm">
          {tokens.map((t) => (
            <li key={t.id} className={`flex items-center justify-between gap-3 py-2 ${t.revoked ? "opacity-50" : ""}`}>
              <div>
                <p className="font-medium">{t.name} <span className="text-xs font-normal text-muted-foreground">· {orgName(t.org_id)}</span></p>
                <p className="text-xs text-muted-foreground">
                  Created {new Date(t.created_at).toLocaleDateString()} ·{" "}
                  {t.last_used_at ? `last used ${new Date(t.last_used_at).toLocaleString()}` : "never used"}
                </p>
              </div>
              {t.revoked ? (
                <span className="text-xs text-muted-foreground">Revoked</span>
              ) : (
                <button onClick={() => revoke(t)} className="rounded-md border border-border px-2.5 py-1 text-xs hover:bg-white/5">Revoke</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
