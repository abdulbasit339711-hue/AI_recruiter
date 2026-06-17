// Client for the Pipecat voice service (separate origin from the main API).

export const VOICE_BASE_URL =
  process.env.NEXT_PUBLIC_VOICE_URL || "http://127.0.0.1:7860";

// When the voice service is reached through an ngrok-free tunnel (phone access),
// ngrok serves an interstitial HTML warning page instead of the JSON response
// unless this header is present. Harmless when not behind ngrok.
const VOICE_HEADERS = { "ngrok-skip-browser-warning": "true" } as const;

export interface QuestionGoal {
  id: string;
  title: string;
  description: string;
  priority_weight: number;
  questions: string[];
}

// The interview question bank for a job (resolved to its role) — read/edit via the
// voice service, which owns goal_templates.
export async function getJobQuestions(
  jobId: number
): Promise<{ job_id: number; role_type: string; goals: QuestionGoal[] }> {
  const res = await fetch(`${VOICE_BASE_URL}/jobs/${jobId}/questions`, {
    headers: VOICE_HEADERS,
  });
  if (!res.ok) throw new Error(`Failed to load questions (${res.status})`);
  return res.json();
}

export async function updateJobGoal(goal: QuestionGoal): Promise<void> {
  const res = await fetch(`${VOICE_BASE_URL}/goals/templates/${goal.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...VOICE_HEADERS },
    body: JSON.stringify({
      title: goal.title,
      description: goal.description,
      priority_weight: goal.priority_weight,
      questions: goal.questions,
    }),
  });
  if (!res.ok) throw new Error(`Failed to save (${res.status})`);
}

export interface InterviewValidation {
  valid: boolean;
  error?: string;
  candidate_name?: string | null;
  job_title?: string | null;
  room_name?: string;
  session_id?: string | null;
  livekit_token?: string;
  livekit_url?: string;
  // Conversation so far when resuming an interrupted interview; empty on a first join.
  prior_transcript?: { speaker: string; text: string }[];
  // Soft guideline duration (seconds) for the on-screen countdown.
  time_limit_seconds?: number;
}

export async function validateInterview(token: string): Promise<InterviewValidation> {
  const res = await fetch(
    `${VOICE_BASE_URL}/interview/validate?token=${encodeURIComponent(token)}`,
    { cache: "no-store", headers: VOICE_HEADERS }
  );
  if (!res.ok) return { valid: false, error: `server error (${res.status})` };
  return res.json();
}

export function interviewEventsUrl(sessionId?: string | null): string {
  // Scope the live event stream to this interview's session so a candidate never
  // receives another candidate's transcript.
  return sessionId
    ? `${VOICE_BASE_URL}/events?session=${encodeURIComponent(sessionId)}`
    : `${VOICE_BASE_URL}/events`;
}

export async function sendInterviewChat(text: string, sessionId?: string | null): Promise<void> {
  // Pass the interview's session_id so the text reaches THIS candidate's bot
  // (not the shared default bot).
  await fetch(`${VOICE_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...VOICE_HEADERS },
    body: JSON.stringify({ text, session: sessionId ?? undefined }),
  });
}
