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

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const client = axios.create({
  baseURL: API_BASE_URL,
});

export function getCandidateEventsUrl(candidateId: number): string {
  return `${API_BASE_URL}/candidates/${candidateId}/events`;
}

export function getJobEventsUrl(jobId: number): string {
  return `${API_BASE_URL}/jobs/${jobId}/events`;
}

export function getCandidateResumeUrl(candidateId: number): string {
  return `${API_BASE_URL}/candidates/${candidateId}/resume`;
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
