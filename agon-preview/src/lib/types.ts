export type ScoreTier = 'strong' | 'promising' | 'weak';

export type CandidateStatus = 'Pending Review' | 'Shortlisted' | 'In Interview' | 'Hired' | 'Rejected' | 'Archived';

export interface Candidate {
  id: string;
  name: string;
  jobTitle: string;
  jobId: string;
  score: number;
  status: CandidateStatus;
  appliedDate: string;
  avatarColor: string;
  decision: 'HIRE' | 'CONSIDER' | 'REJECT';
  summary: {
    profileMatch: number;
    semanticMatch: number;
    llmScore: number;
    aiMatch: number;
  };
  interview: {
    duration: string;
    talkRatio: number;
    goalsCovered: number;
    totalGoals: number;
    engagementAvg: number;
    strengths: string[];
    developmentAreas: string[];
    botTalkRatio: number;
    candidateTalkRatio: number;
    engagementTimeline: number[];
    miniStats: { label: string; value: string }[];
    assessmentScores: { label: string; score: number }[];
    goals: { title: string; coverage: number; outcome: 'Passed' | 'Partial' | 'Failed' }[];
    transcript: { speaker: 'bot' | 'candidate'; text: string; time: string }[];
  };
}

export interface Job {
  id: string;
  title: string;
  department: string;
  description: string;
  llmPrompt: string;
  candidateCount: number;
  status: 'Active' | 'Archived';
  scoreDistribution: number[]; // [0-20, 21-40, 41-60, 61-80, 81-100]
  avgScore: number;
  createdAt: string;
}

export function tierFromScore(score: number): ScoreTier {
  if (score >= 75) return 'strong';
  if (score >= 50) return 'promising';
  return 'weak';
}

export function decisionFromScore(score: number): 'HIRE' | 'CONSIDER' | 'REJECT' {
  if (score >= 75) return 'HIRE';
  if (score >= 50) return 'CONSIDER';
  return 'REJECT';
}
