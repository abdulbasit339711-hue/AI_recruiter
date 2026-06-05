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

const jobSchema = z.object({
  title: z.string().min(3, "Title is required"),
  department: z.string().min(2, "Department is required"),
  job_description: z.string().min(10, "Description is required"),
  llm_prompt: z.string().optional(),
});

type FormValues = z.infer<typeof jobSchema>;

interface JobFormModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: FormValues, id?: number) => void; // if id provided, treat as edit
  initialData?: Job; // optional for editing
}

export const JobFormModal: React.FC<JobFormModalProps> = ({ open, onClose, onSubmit, initialData }) => {
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
      });
    } else {
      reset();
    }
  }, [initialData, reset]);

  const submitHandler = async (data: FormValues) => {
    await onSubmit(data, initialData?.id);
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
          <div>
            <Input placeholder="Title" {...register("title")} />
            {errors.title && <p className="text-sm text-red-500">{errors.title.message}</p>}
          </div>
          <div>
            <Input placeholder="Department" {...register("department")} />
            {errors.department && <p className="text-sm text-red-500">{errors.department.message}</p>}
          </div>
          <div>
            <Textarea
              placeholder="Job description"
              rows={4}
              {...register("job_description")}
            />
            {errors.job_description && (
              <p className="text-sm text-red-500">{errors.job_description.message}</p>
            )}
          </div>
          <div>
            <Textarea
              placeholder="LLM prompt (optional)"
              rows={2}
              {...register("llm_prompt")}
            />
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
