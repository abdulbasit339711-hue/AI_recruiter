// src/components/admin/ResumeViewer.tsx
"use client";

import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogClose } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { getCandidateResumeUrl } from "@/lib/api";
import { X } from "lucide-react";

type ResumeViewerProps = {
  candidateId: number;
  open: boolean;
  onClose: () => void;
};

export const ResumeViewer: React.FC<ResumeViewerProps> = ({ candidateId, open, onClose }) => {
  const [resumeText, setResumeText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || candidateId <= 0) return;

    let cancelled = false;
    setLoading(true);
    setError(null);
    setResumeText("");

    fetch(getCandidateResumeUrl(candidateId))
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(await response.text());
        }
        return response.text();
      })
      .then((text) => {
        if (!cancelled) setResumeText(text);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load resume.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [candidateId, open]);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden">
        <DialogHeader className="flex items-center justify-between">
          <DialogTitle>Resume Preview</DialogTitle>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </DialogHeader>
        <div className="h-[80vh] overflow-auto rounded-md border border-white/10 bg-background p-4">
          {isLoading && <p className="text-sm text-muted-foreground">Loading resume...</p>}
          {error && <p className="text-sm text-red-500">{error}</p>}
          {!isLoading && !error && (
            <pre className="whitespace-pre-wrap break-words text-sm leading-6">
              {resumeText || "No resume text available."}
            </pre>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
