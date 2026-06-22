import { ReactNode } from "react";

/**
 * Full-bleed, distraction-free wrapper for the live AI interview / call UI.
 *
 * Each phase of the interview page renders its OWN chrome (the live call has its
 * own top bar + control footer, sized to a full `h-screen` stage). This layout
 * must therefore NOT add its own header or flex wrapper: doing so pushed the
 * call's full-height stage down by the header's height, shoving the control bar
 * (mute / captions / transcript / leave) off the bottom of the viewport. Keep it
 * a transparent full-height container so the page owns the whole viewport.
 */
export default function InterviewLayout({ children }: { children: ReactNode }) {
  return <div className="min-h-screen bg-background">{children}</div>;
}
