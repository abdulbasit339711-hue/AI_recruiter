"use client";

import { useParams } from "next/navigation";

import { InterviewPanel } from "@/components/candidates/InterviewPanel";

export default function CandidateInterviewPage() {
  const { candidateId } = useParams<{ candidateId: string }>();
  const id = Number(candidateId);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <h1 className="text-xl font-semibold">Interview</h1>
      <InterviewPanel candidateId={id} />
    </div>
  );
}
