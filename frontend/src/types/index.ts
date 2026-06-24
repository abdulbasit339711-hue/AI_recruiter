export interface Org {
  id: number;
  slug: string;
  name: string;
  primary_color: string;
  logo_url: string | null;
  tagline: string | null;
  about: string | null;
  contact_email: string | null;
  social_links: { website?: string; linkedin?: string; twitter?: string };
  created_at: string;
}

export interface Job {
  id: number;
  title: string;
  department: string;
  job_description: string;
  llm_prompt: string | null;
  voice_prompt: string | null;
  status: "Active" | "Archived";
  created_at: string;
  org_id: number | null;
  org_slug: string | null;
  org_name: string | null;
  candidate_count?: number;
  shortlisted_count?: number;
  avg_score?: number | null;
  top_score?: number | null;
  resume_deadline: string | null;
  interview_deadline: string | null;
}

export type InterviewPassedCandidate = {
  id: number;
  name: string | null;
  email: string | null;
  job_id: number;
  total_score: number;
  interview_phase1_score: number | null;
  interview_phase2_score: number | null;
  interview_overall_score: number | null;
  interview_completed_at: string | null;
  status: string;
  hr_status: string | null;
};

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
  iq_score?: number | null;        // time-adjusted percentage 0–100
  iq_correct?: number | null;
  iq_total?: number | null;
  iq_time_seconds?: number | null; // server-measured time taken
  iq_attempted_at?: string | null; // ISO timestamp when submitted
  iq_details?: string | null;      // JSON: IqQuestionDetail[]

  // Availability scheduling
  availability_invited_at?: string | null;
  availability_response?: string | null;
  availability_submitted_at?: string | null;
  interview_confirmed_slot?: string | null;
  interview_confirmed_at?: string | null;
  interview_token?: string | null;

  // Enriched resume profile (extracted during scoring)
  github_url?: string | null;
  linkedin_url?: string | null;
  projects?: string | null;       // JSON list of project names
  certifications?: string | null; // JSON list of certifications
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

export interface IqQuestionDetail {
  id: string;
  prompt: string;
  options: string[];
  chosen: number | null;
  chosen_text: string | null;
  correct: number;
  correct_text: string;
  is_correct: boolean;
  time_seconds: number;
}

export interface IqSubmitResponse {
  correct: number;
  total: number;
  accuracy: number;      // raw correct/total percentage
  score: number;         // time-adjusted percentage 0–100
  time_seconds: number;  // server-measured time taken
  detail: IqQuestionDetail[];
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
