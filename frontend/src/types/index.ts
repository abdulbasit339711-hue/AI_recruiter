export interface Job {
  id: number;
  title: string;
  department: string;
  job_description: string;
  llm_prompt: string | null;
  status: "Active" | "Archived";
  created_at: string;
}

export type CandidateStatus =
  | "Queued"
  | "Processing"
  | "Shortlisted"
  | "Reviewed"
  | "Rejected"
  | "Ungraded"
  | "Error"
  | "Pending"
  | "Processed"
  | "Failed";

export interface Candidate {
  id: number;
  filename: string;
  name?: string | null;
  phone?: string | null;
  email: string | null;
  raw_text?: string | null;
  job_id: number;
  tier1: number;
  tier2: number;
  tier3: number;
  total_score: number;
  summary: string | null;
  evidence: string | null;
  warnings?: string | null;
  evaluation_data?: string | null;
  current_role?: string | null;
  companies?: string | null;
  years_experience?: number | null;
  skills_matched?: string | null;
  skills_missing?: string | null;
  interview_questions?: string | null;
  status: CandidateStatus;
  created_at: string;

  // Recruitment Workflow fields
  hr_status: 'Applied' | 'Screened' | 'Interview' | 'Offer' | 'Hired' | 'Rejected' | null;
  hr_notes: string | null;
  hr_score_override: number | null;
  status_history: TimelineEntry[] | null;

  // Pre-application IQ screen (server-scored; recorded, never gates).
  iq_score?: number | null;   // percentage 0–100
  iq_correct?: number | null;
  iq_total?: number | null;
}

export interface TimelineEntry {
  type: string;
  status: string;
  changed_by: string;
  changed_at: string;
  note?: string | null;
}

export interface StatusUpdatePayload {
  hr_status: 'Applied' | 'Screened' | 'Interview' | 'Offer' | 'Hired' | 'Rejected';
  changed_by: string;
  note?: string;
}

export interface NotePayload {
  note: string;
  author: string;
}

export interface ScoreOverridePayload {
  override_score: number;
  reason: string;
  changed_by: string;
}

// ── Pre-application IQ screen ──────────────────────────────────────────────────
export interface IqQuestion {
  id: string;
  prompt: string;
  options: string[];
}

export interface IqTestResponse {
  questions: IqQuestion[];
  test_token: string;
  time_limit_seconds: number;
  total: number;
}

export interface IqSubmitResponse {
  correct: number;
  total: number;
  score: number; // percentage 0–100
  result_token: string;
}

export interface UploadResponse {
  id: number;
  filename: string;
  job_id: number;
  status: CandidateStatus;
  message: string;
  // Self-service interview link minted at upload time (may be null if the server
  // has interview links disabled).
  interview_token?: string | null;
  interview_url?: string | null;
}

export interface PaginatedCandidates {
  items: Candidate[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface CandidateSSEPayload {
  candidate_id: number;
  job_id: number | null;
  status: CandidateStatus;
  event: string;
  terminal: boolean;
  total_score?: number | null;
}

export const TERMINAL_STATUSES: CandidateStatus[] = [
  "Shortlisted",
  "Reviewed",
  "Rejected",
  "Ungraded",
  "Error",
  "Processed",
  "Failed",
];

export function isTerminalStatus(status: CandidateStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}
