import axios from "axios";
import {
  Job,
  Candidate,
  UploadResponse,
  PaginatedCandidates,
  StatusUpdatePayload,
  NotePayload,
  ScoreOverridePayload,
  TimelineEntry,
} from "@/types";

// All backend traffic goes through the same-origin Next proxy
// (src/app/api/admin/[...path]/route.ts), which injects the admin bearer token
// server-side. The real backend URL + token live in server env, never the client.
export const API_BASE_URL = "/api/admin";

const client = axios.create({
  baseURL: API_BASE_URL,
});

// Surface the backend's human-readable error instead of axios's generic
// "Request failed with status code 4xx". FastAPI returns `{ detail: string }`
// for HTTPExceptions and `{ detail: [{ msg, loc }, ...] }` for 422 validation.
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error?.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      error.message = detail;
    } else if (Array.isArray(detail) && detail.length) {
      error.message = detail
        .map((d) => (typeof d?.msg === "string" ? d.msg : String(d)))
        .join("; ");
    }
    return Promise.reject(error);
  }
);

export function getCandidateEventsUrl(candidateId: number): string {
  return `${API_BASE_URL}/candidates/${candidateId}/events`;
}

export function getJobEventsUrl(jobId: number): string {
  return `${API_BASE_URL}/jobs/${jobId}/events`;
}

export function getCandidateResumeUrl(candidateId: number): string {
  return `${API_BASE_URL}/candidates/${candidateId}/resume`;
}

export function getInterviewAudioUrl(candidateId: number): string {
  return `${API_BASE_URL}/candidates/${candidateId}/interview-audio`;
}

export function getCandidateReportUrl(candidateId: number, format: "md" | "pdf" = "pdf"): string {
  return `${API_BASE_URL}/candidates/${candidateId}/report?format=${format}`;
}

export interface InterviewResult {
  has_interview: boolean;
  has_audio?: boolean;
  session?: {
    session_id: string;
    role_type: string;
    status: string;
    started_at: string | null;
    ended_at: string | null;
    total_goals: number;
    completed_goals: number;
    average_progress: number;
    overall_assessment: string | null;
  };
  transcript?: {
    speaker: string;
    text: string;
    sequence_number: number;
    evaluation?: TurnEvaluation | null;
  }[];
  goals?: {
    title: string;
    completion_status: string;
    progress_score: number;
    confidence_level: number;
    // Planned questions for this goal + the candidate-answer evidence gathered for it.
    questions?: string[];
    evidence?: { text: string }[];
  }[];
  metrics?: {
    interview: {
      stt_tokens: number;
      llm_input_tokens: number;
      llm_output_tokens: number;
      tts_tokens: number;
      total_tokens: number;
      cost_usd: number;
    };
    scoring: { prompt_tokens: number; completion_tokens: number; cost_usd: number };
  };
}

export interface TurnEvaluation {
  score?: number; // 0-10
  completeness?: number; // 0-1
  depth?: string;
  clarity?: number; // 0-1
  strengths?: string[];
  weaknesses?: string[];
  follow_up_needed?: boolean;
  suggested_probe?: string;
}

export const api = {
  async getJobs(status?: "Active" | "Archived"): Promise<Job[]> {
    const response = await client.get<Job[]>("/jobs", { params: { status } });
    return response.data;
  },

  async getJob(jobId: number): Promise<Job> {
    const response = await client.get<Job>(`/jobs/${jobId}`);
    return response.data;
  },

  async createJob(params: {
    title: string;
    department: string;
    job_description: string;
    llm_prompt?: string;
    role_type?: string;
  }): Promise<Job> {
    const response = await client.post<Job>("/jobs", null, { params });
    return response.data;
  },

  async updateJob(
    jobId: number,
    params: {
      title?: string;
      department?: string;
      job_description?: string;
      llm_prompt?: string;
      role_type?: string;
      status?: "Active" | "Archived";
    }
  ): Promise<Job> {
    const response = await client.put<Job>(`/jobs/${jobId}`, null, { params });
    return response.data;
  },

  async deleteJob(jobId: number): Promise<{ message: string; job_id: number }> {
    const response = await client.delete<{ message: string; job_id: number }>(
      `/jobs/${jobId}`
    );
    return response.data;
  },

  async getJobCandidates(
    jobId: number,
    page = 1,
    pageSize = 50,
    status?: string,
    hrStatus?: string,
    sortBy?: string,
    order?: string
  ): Promise<PaginatedCandidates> {
    const response = await client.get<PaginatedCandidates>(
      `/jobs/${jobId}/candidates`,
      {
        params: {
          page,
          page_size: pageSize,
          status,
          hr_status: hrStatus,
          sort_by: sortBy,
          order,
        },
      }
    );
    return response.data;
  },

  async getCandidate(candidateId: number): Promise<Candidate> {
    const response = await client.get<Candidate>(`/candidates/${candidateId}`);
    return response.data;
  },

  async triggerInterviewInvite(
    candidateId: number
  ): Promise<{ status: string; candidate_id: number; link: string }> {
    const response = await client.post(`/candidates/${candidateId}/interview-invite`);
    return response.data;
  },

  async getInterviewResult(candidateId: number): Promise<InterviewResult> {
    const response = await client.get<InterviewResult>(
      `/candidates/${candidateId}/interview`
    );
    return response.data;
  },

  async updateCandidateStatus(
    id: number,
    payload: StatusUpdatePayload
  ): Promise<Candidate> {
    const response = await client.patch<Candidate>(
      `/candidates/${id}/status`,
      payload
    );
    return response.data;
  },

  async addCandidateNote(id: number, payload: NotePayload): Promise<Candidate> {
    const response = await client.post<Candidate>(
      `/candidates/${id}/notes`,
      payload
    );
    return response.data;
  },

  async overrideCandidateScore(
    id: number,
    payload: ScoreOverridePayload
  ): Promise<Candidate> {
    const response = await client.patch<Candidate>(
      `/candidates/${id}/score-override`,
      payload
    );
    return response.data;
  },

  async getCandidateTimeline(id: number): Promise<{ timeline: TimelineEntry[] }> {
    const response = await client.get<{ timeline: TimelineEntry[] }>(
      `/candidates/${id}/timeline`
    );
    return response.data;
  },

  async uploadResume(jobId: number, file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await client.post<UploadResponse>("/upload", formData, {
      params: { job_id: jobId },
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  async reprocessCandidate(
    candidateId: number
  ): Promise<{ id: number; status: string; message: string }> {
    const response = await client.post(`/candidates/${candidateId}/reprocess`);
    return response.data;
  },

  // Attach/replace an existing candidate's résumé PDF and re-score them.
  async replaceCandidateResume(
    candidateId: number,
    file: File
  ): Promise<{ id: number; filename: string; status: string; message: string }> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await client.post(`/candidates/${candidateId}/resume`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  async reprocessJobCandidates(
    jobId: number
  ): Promise<{ message: string; count: number }> {
    const response = await client.post(`/jobs/${jobId}/reprocess`);
    return response.data;
  },

  async sendShortlistEmails(
    jobId: number,
    topN?: number
  ): Promise<{ message: string; failed_count: number; errors: string[] }> {
    const response = await client.post(`/jobs/${jobId}/email`, null, {
      params: { top_n: topN },
    });
    return response.data;
  },

  async getHealth(): Promise<Record<string, unknown>> {
    const response = await client.get("/health");
    return response.data;
  },
};

export default client;
