import { ReactNode } from "react";
import { Mic } from "lucide-react";

/**
 * Minimal, distraction-free layout for the live AI interview / call interface.
 * No admin or careers chrome — just the call.
 */
export default function InterviewLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="border-b border-white/10">
        <div className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-3 text-sm font-medium">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary/15 text-primary">
            <Mic className="h-3.5 w-3.5" />
          </span>
          AI Interview
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
