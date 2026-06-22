"use client";

import React from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ApplicantJobCard } from "@/components/applicant/ApplicantJobCard";
import { AnimatePresence } from "framer-motion";
import { FadeIn, Stagger, StaggerItem } from "@/components/ui/motion";
import { Globe, Linkedin, Twitter, Mail } from "lucide-react";
import type { Org } from "@/types";

export default function CareersPage() {
  const { orgSlug } = useParams<{ orgSlug: string }>();

  const { data: org } = useQuery<Org>({
    queryKey: ["orgs", orgSlug],
    queryFn: () => api.getOrgBySlug(orgSlug),
    staleTime: 60_000,
    enabled: !!orgSlug,
  });

  const { data: jobs, isLoading, isError } = useQuery({
    queryKey: ["orgs", orgSlug, "jobs"],
    queryFn: () => api.getOrgJobs(orgSlug),
    staleTime: 60_000,
    enabled: !!orgSlug,
  });

  const color = org?.primary_color || "#1C99BF";
  const name = org?.name || orgSlug;

  return (
    <section className="mx-auto max-w-6xl space-y-10 p-4 py-10">
      {/* Hero */}
      <FadeIn y={20}>
        <div className="glass rounded-2xl p-8 md:p-10">
          <p className="font-mono text-xs uppercase tracking-[0.06em] text-muted-foreground">
            Careers at {name}
          </p>
          <h1 className="mt-2 font-display text-[36px] font-bold leading-tight tracking-tight text-heading">
            {org?.tagline || `Join ${name}`}
          </h1>
          {org?.about && (
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">
              {org.about}
            </p>
          )}

          {/* Social links + contact */}
          {(org?.social_links?.website || org?.social_links?.linkedin || org?.social_links?.twitter || org?.contact_email) && (
            <div className="mt-6 flex flex-wrap gap-4">
              {org?.social_links?.website && (
                <a
                  href={org.social_links.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  <Globe className="h-4 w-4" style={{ color }} />
                  Website
                </a>
              )}
              {org?.social_links?.linkedin && (
                <a
                  href={org.social_links.linkedin}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  <Linkedin className="h-4 w-4" style={{ color }} />
                  LinkedIn
                </a>
              )}
              {org?.social_links?.twitter && (
                <a
                  href={org.social_links.twitter}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  <Twitter className="h-4 w-4" style={{ color }} />
                  Twitter
                </a>
              )}
              {org?.contact_email && (
                <a
                  href={`mailto:${org.contact_email}`}
                  className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  <Mail className="h-4 w-4" style={{ color }} />
                  {org.contact_email}
                </a>
              )}
            </div>
          )}
        </div>
      </FadeIn>

      {/* Job listing */}
      <div>
        <FadeIn y={12} delay={0.1}>
          <h2 className="font-display text-xl font-semibold text-heading">Open roles</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Submit your résumé — every application starts with a short aptitude screen. No account required.
          </p>
        </FadeIn>

        {isLoading && (
          <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-48 animate-pulse glass rounded-2xl" />
            ))}
          </div>
        )}

        {isError && (
          <p className="mt-4 text-sm text-muted-foreground">Failed to load jobs.</p>
        )}

        {!isLoading && !isError && (
          <Stagger className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3" gap={0.06} delay={0.15}>
            <AnimatePresence>
              {jobs?.map((job) => (
                <StaggerItem key={job.id}>
                  <ApplicantJobCard
                    job={job}
                    href={`/careers/${orgSlug}/${job.id}`}
                    brandColor={color}
                  />
                </StaggerItem>
              ))}
              {jobs?.length === 0 && (
                <p className="col-span-full text-sm text-muted-foreground">
                  No open roles right now — check back soon.
                </p>
              )}
            </AnimatePresence>
          </Stagger>
        )}
      </div>
    </section>
  );
}
