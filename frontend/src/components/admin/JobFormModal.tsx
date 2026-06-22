// src/components/admin/JobFormModal.tsx
"use client";

import React from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import type { Job } from "@/types";
import { useOrgs } from "@/hooks/useOrgs";

const jobSchema = z.object({
  title: z.string().min(3, "Title is required"),
  department: z.string().min(2, "Department is required"),
  job_description: z.string().min(10, "Description is required"),
  llm_prompt: z.string().optional(),
  org_id: z.string().optional(),
  resume_deadline: z.string().optional(),
  interview_deadline: z.string().optional(),
});

type FormValues = z.infer<typeof jobSchema>;

interface JobFormModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (
    data: Omit<FormValues, "org_id"> & { org_id?: number | null },
    id?: number
  ) => void;
  initialData?: Job;
}

export const JobFormModal: React.FC<JobFormModalProps> = ({ open, onClose, onSubmit, initialData }) => {
  const { data: orgs } = useOrgs();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<FormValues>({
    resolver: zodResolver(jobSchema),
    defaultValues: initialData
      ? {
          title: initialData.title,
          department: initialData.department,
          job_description: initialData.job_description,
          llm_prompt: initialData.llm_prompt ?? "",
          org_id: initialData.org_id?.toString() ?? "",
          resume_deadline: initialData.resume_deadline ?? "",
          interview_deadline: initialData.interview_deadline ?? "",
        }
      : undefined,
  });

  React.useEffect(() => {
    if (initialData) {
      reset({
        title: initialData.title,
        department: initialData.department,
        job_description: initialData.job_description,
        llm_prompt: initialData.llm_prompt ?? "",
        org_id: initialData.org_id?.toString() ?? "",
        resume_deadline: initialData.resume_deadline ?? "",
        interview_deadline: initialData.interview_deadline ?? "",
      });
    } else {
      reset({ org_id: "", resume_deadline: "", interview_deadline: "" });
    }
  }, [initialData, reset]);

  const submitHandler = async (data: FormValues) => {
    const { org_id, ...rest } = data;
    await onSubmit({ ...rest, org_id: org_id ? Number(org_id) : null }, initialData?.id);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{initialData ? "Edit Job" : "Create New Job"}</DialogTitle>
          <DialogDescription>
            {initialData ? "Modify the job details" : "Enter the new job information"}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(submitHandler)} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="job-org" className="text-sm font-medium">
              Organization <span className="text-muted-foreground font-normal">(optional)</span>
            </label>
            <select
              id="job-org"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
              {...register("org_id")}
            >
              <option value="">— No organization —</option>
              {orgs?.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name} ({o.slug})
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label htmlFor="job-title" className="text-sm font-medium">Title</label>
            <Input id="job-title" placeholder="e.g. Senior Python Developer" {...register("title")} />
            {errors.title && <p className="text-sm text-red-500">{errors.title.message}</p>}
          </div>
          <div className="space-y-1.5">
            <label htmlFor="job-department" className="text-sm font-medium">Department</label>
            <Input id="job-department" placeholder="e.g. Engineering" {...register("department")} />
            {errors.department && <p className="text-sm text-red-500">{errors.department.message}</p>}
          </div>
          <div className="space-y-1.5">
            <label htmlFor="job-description" className="text-sm font-medium">Job Description</label>
            <Textarea
              id="job-description"
              placeholder="Describe the role, responsibilities, and required skills"
              rows={4}
              {...register("job_description")}
            />
            {errors.job_description && (
              <p className="text-sm text-red-500">{errors.job_description.message}</p>
            )}
          </div>
          <div className="space-y-1.5">
            <label htmlFor="job-llm-prompt" className="text-sm font-medium">
              LLM Evaluation Prompt <span className="text-muted-foreground font-normal">(optional)</span>
            </label>
            <Textarea
              id="job-llm-prompt"
              placeholder="Custom instructions for AI scoring of resumes (Tier 3)"
              rows={2}
              {...register("llm_prompt")}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label htmlFor="job-resume-deadline" className="text-sm font-medium">
                Resume Deadline <span className="text-muted-foreground font-normal">(optional)</span>
              </label>
              <Input
                id="job-resume-deadline"
                type="date"
                {...register("resume_deadline")}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="job-interview-deadline" className="text-sm font-medium">
                Interview Deadline <span className="text-muted-foreground font-normal">(optional)</span>
              </label>
              <Input
                id="job-interview-deadline"
                type="date"
                {...register("interview_deadline")}
              />
            </div>
          </div>
          <DialogFooter className="flex justify-end space-x-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : initialData ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
