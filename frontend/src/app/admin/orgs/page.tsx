"use client";

import React, { useState } from "react";
import { Building2, Plus, Pencil, Trash2, ExternalLink, Globe, Linkedin, Twitter, Mail, Check, X, Loader2 } from "lucide-react";
import { useOrgs, useCreateOrg, useUpdateOrg, useDeleteOrg } from "@/hooks/useOrgs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { FadeIn, Stagger, StaggerItem } from "@/components/ui/motion";
import type { Org } from "@/types";

type OrgFormState = {
  slug: string;
  name: string;
  primary_color: string;
  logo_url: string;
  tagline: string;
  about: string;
  contact_email: string;
  website: string;
  linkedin: string;
  twitter: string;
};

const EMPTY_FORM: OrgFormState = {
  slug: "", name: "", primary_color: "#1C99BF",
  logo_url: "", tagline: "", about: "",
  contact_email: "", website: "", linkedin: "", twitter: "",
};

function toApiParams(f: OrgFormState) {
  const social: Record<string, string> = {};
  if (f.website)  social.website  = f.website;
  if (f.linkedin) social.linkedin = f.linkedin;
  if (f.twitter)  social.twitter  = f.twitter;
  return {
    slug: f.slug,
    name: f.name,
    primary_color: f.primary_color,
    logo_url: f.logo_url || undefined,
    tagline: f.tagline || undefined,
    about: f.about || undefined,
    contact_email: f.contact_email || undefined,
    social_links: Object.keys(social).length ? JSON.stringify(social) : undefined,
  };
}

function orgToForm(o: Org): OrgFormState {
  return {
    slug: o.slug,
    name: o.name,
    primary_color: o.primary_color,
    logo_url: o.logo_url ?? "",
    tagline: o.tagline ?? "",
    about: o.about ?? "",
    contact_email: o.contact_email ?? "",
    website: o.social_links?.website ?? "",
    linkedin: o.social_links?.linkedin ?? "",
    twitter: o.social_links?.twitter ?? "",
  };
}

function slugify(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export default function OrgsPage() {
  const { data: orgs, isLoading } = useOrgs();
  const createOrg = useCreateOrg();
  const updateOrg = useUpdateOrg();
  const deleteOrg = useDeleteOrg();

  const [showCreate, setShowCreate] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<OrgFormState>(EMPTY_FORM);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openCreate = () => { setForm(EMPTY_FORM); setError(null); setShowCreate(true); setEditId(null); };
  const openEdit = (o: Org) => { setForm(orgToForm(o)); setError(null); setEditId(o.id); setShowCreate(false); };
  const closeForm = () => { setShowCreate(false); setEditId(null); };

  const set = (key: keyof OrgFormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const val = e.target.value;
    setForm((f) => {
      const next = { ...f, [key]: val };
      if (key === "name" && !editId) next.slug = slugify(val);
      return next;
    });
  };

  const handleSave = async () => {
    setError(null);
    try {
      if (editId) {
        const { slug: _slug, ...rest } = toApiParams(form);
        await updateOrg.mutateAsync({ id: editId, ...rest });
      } else {
        await createOrg.mutateAsync(toApiParams(form));
      }
      closeForm();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteOrg.mutateAsync(id);
      setDeleteConfirm(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  const isSaving = createOrg.isPending || updateOrg.isPending;
  const isFormOpen = showCreate || editId !== null;

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-4 py-8">
      <FadeIn y={16}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-[28px] font-bold text-heading">Organizations</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Manage company branding for the whitelabel careers portal.
            </p>
          </div>
          {!isFormOpen && (
            <Button onClick={openCreate} className="shrink-0 gap-2">
              <Plus className="h-4 w-4" /> New organization
            </Button>
          )}
        </div>
      </FadeIn>

      {/* Create / Edit form */}
      {isFormOpen && (
        <FadeIn y={12}>
          <div className="glass rounded-2xl p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold text-heading">
                {editId ? "Edit organization" : "New organization"}
              </h2>
              <button onClick={closeForm} className="text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Organization name</label>
                <Input value={form.name} onChange={set("name")} placeholder="Acme Corp" />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  URL slug{" "}
                  <span className="font-normal text-muted-foreground text-xs">/careers/[slug]</span>
                </label>
                <Input
                  value={form.slug}
                  onChange={set("slug")}
                  placeholder="acme-corp"
                  disabled={!!editId}
                  className={editId ? "opacity-50 cursor-not-allowed" : ""}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Brand color</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={form.primary_color}
                    onChange={set("primary_color")}
                    className="h-9 w-12 cursor-pointer rounded-md border border-input bg-background"
                  />
                  <Input
                    value={form.primary_color}
                    onChange={set("primary_color")}
                    placeholder="#1C99BF"
                    className="font-mono text-sm"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Logo URL <span className="font-normal text-muted-foreground text-xs">(optional)</span></label>
                <Input value={form.logo_url} onChange={set("logo_url")} placeholder="https://..." />
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <label className="text-sm font-medium">Tagline <span className="font-normal text-muted-foreground text-xs">(shown below org name)</span></label>
                <Input value={form.tagline} onChange={set("tagline")} placeholder="Building the future of work" />
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <label className="text-sm font-medium">About <span className="font-normal text-muted-foreground text-xs">(hero blurb on careers page)</span></label>
                <Textarea
                  value={form.about}
                  onChange={set("about")}
                  rows={3}
                  placeholder="A short paragraph about your company that applicants will see..."
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Contact email <span className="font-normal text-muted-foreground text-xs">(optional)</span></label>
                <Input value={form.contact_email} onChange={set("contact_email")} type="email" placeholder="careers@acme.com" />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Website</label>
                <Input value={form.website} onChange={set("website")} placeholder="https://acme.com" />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">LinkedIn URL</label>
                <Input value={form.linkedin} onChange={set("linkedin")} placeholder="https://linkedin.com/company/acme" />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Twitter / X URL</label>
                <Input value={form.twitter} onChange={set("twitter")} placeholder="https://x.com/acme" />
              </div>
            </div>

            {error && (
              <p className="rounded-xl border px-4 py-3 text-sm" style={{ borderColor: "var(--weak)", background: "var(--weak-bg)", color: "var(--weak-text)" }}>
                {error}
              </p>
            )}

            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={closeForm} disabled={isSaving}>Cancel</Button>
              <Button onClick={handleSave} disabled={isSaving || !form.name || !form.slug} className="gap-2">
                {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                {editId ? "Save changes" : "Create organization"}
              </Button>
            </div>
          </div>
        </FadeIn>
      )}

      {/* Org list */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => <div key={i} className="h-24 animate-pulse glass rounded-2xl" />)}
        </div>
      ) : orgs?.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-4 glass rounded-2xl py-16 text-center">
          <Building2 className="h-10 w-10 text-muted-foreground/40" />
          <div>
            <p className="font-medium text-heading">No organizations yet</p>
            <p className="mt-1 text-sm text-muted-foreground">Create one to enable whitelabeled careers pages.</p>
          </div>
          <Button onClick={openCreate} className="gap-2"><Plus className="h-4 w-4" /> New organization</Button>
        </div>
      ) : (
        <Stagger gap={0.05}>
          {orgs?.map((org) => (
            <StaggerItem key={org.id}>
              <div className="glass rounded-2xl p-5">
                <div className="flex items-start gap-4">
                  {/* Color swatch / logo */}
                  <div
                    className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-base font-bold text-white select-none"
                    style={{ background: org.primary_color }}
                  >
                    {org.logo_url
                      // eslint-disable-next-line @next/next/no-img-element
                      ? <img src={org.logo_url} alt={org.name} className="h-12 w-12 rounded-xl object-contain" />
                      : org.name.slice(0, 2).toUpperCase()
                    }
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-display font-semibold text-heading">{org.name}</h3>
                      <span className="rounded-md bg-foreground/[0.06] px-2 py-0.5 font-mono text-xs text-muted-foreground">
                        /{org.slug}
                      </span>
                    </div>
                    {org.tagline && <p className="mt-0.5 text-sm text-muted-foreground">{org.tagline}</p>}

                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                      <a
                        href={`/careers/${org.slug}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 hover:text-primary transition-colors"
                      >
                        <ExternalLink className="h-3 w-3" /> /careers/{org.slug}
                      </a>
                      {org.contact_email && (
                        <span className="flex items-center gap-1"><Mail className="h-3 w-3" /> {org.contact_email}</span>
                      )}
                      {org.social_links?.website && (
                        <a href={org.social_links.website} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 hover:text-primary transition-colors">
                          <Globe className="h-3 w-3" /> Website
                        </a>
                      )}
                      {org.social_links?.linkedin && (
                        <a href={org.social_links.linkedin} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 hover:text-primary transition-colors">
                          <Linkedin className="h-3 w-3" /> LinkedIn
                        </a>
                      )}
                      {org.social_links?.twitter && (
                        <a href={org.social_links.twitter} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 hover:text-primary transition-colors">
                          <Twitter className="h-3 w-3" /> Twitter
                        </a>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  {deleteConfirm === org.id ? (
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-muted-foreground">Delete?</span>
                      <Button size="sm" variant="destructive" onClick={() => handleDelete(org.id)} disabled={deleteOrg.isPending}>
                        {deleteOrg.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : "Yes"}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setDeleteConfirm(null)}>No</Button>
                    </div>
                  ) : (
                    <div className="flex shrink-0 gap-1">
                      <button
                        onClick={() => openEdit(org)}
                        className="rounded-lg p-2 text-muted-foreground hover:text-heading hover:bg-foreground/[0.06] transition-colors"
                        title="Edit"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(org.id)}
                        className="rounded-lg p-2 text-muted-foreground hover:text-red-500 hover:bg-red-500/[0.08] transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      )}
    </div>
  );
}
