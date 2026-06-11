// Client for the Pipecat voice service (separate origin from the main API).

export const VOICE_BASE_URL =
  process.env.NEXT_PUBLIC_VOICE_URL || "http://127.0.0.1:7860";

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
    { cache: "no-store" }
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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, session: sessionId ?? undefined }),
  });
}
