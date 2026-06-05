"use client";

import React, { useState } from "react";
import { MessageSquare, Send, User, Clock, X } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "react-hot-toast";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface CandidateNotesPanelProps {
  candidateId: number;
  hrNotes: string | null;
  onUpdate: () => void;
  onClose?: () => void;
}

interface ParsedNote {
  timestamp: string | null;
  author: string | null;
  text: string;
}

export const CandidateNotesPanel: React.FC<CandidateNotesPanelProps> = ({
  candidateId,
  hrNotes,
  onUpdate,
  onClose,
}) => {
  const [newNote, setNewNote] = useState("");
  const [author, setAuthor] = useState("hr@company.com"); // default author
  const [submitting, setSubmitting] = useState(false);

  const parseNotes = (notesStr: string | null): ParsedNote[] => {
    if (!notesStr) return [];
    return notesStr
      .split("\n")
      .filter((line) => line.trim() !== "")
      .map((line) => {
        const trimmed = line.trim();
        if (trimmed.startsWith("[")) {
          const closeBracketIdx = trimmed.indexOf("]");
          if (closeBracketIdx !== -1) {
            const timestamp = trimmed.substring(1, closeBracketIdx);
            const rest = trimmed.substring(closeBracketIdx + 1).trim();
            const colonIdx = rest.indexOf(":");
            if (colonIdx !== -1) {
              const author = rest.substring(0, colonIdx).trim();
              const text = rest.substring(colonIdx + 1).trim();
              return { timestamp, author, text };
            }
          }
        }
        return {
          timestamp: null,
          author: null,
          text: line,
        };
      });
  };

  const parsedNotes = parseNotes(hrNotes);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNote.trim()) return;

    setSubmitting(true);
    try {
      await api.addCandidateNote(candidateId, {
        note: newNote.trim(),
        author: author.trim() || "Anonymous Recruiter",
      });
      toast.success("Note added successfully.");
      setNewNote("");
      onUpdate();
    } catch (err) {
      toast.error("Failed to add note.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Title & Close */}
      <div className="flex items-center justify-between border-b border-white/10 pb-2">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold">HR Recruiter Notes</h3>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-white/10 hover:text-white transition-colors"
            title="Close notes panel"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Notes List */}
      <div className="max-h-60 overflow-y-auto space-y-3 pr-1">
        {parsedNotes.length === 0 ? (
          <p className="text-xs text-muted-foreground italic py-2">No notes recorded yet for this candidate.</p>
        ) : (
          parsedNotes.map((note, idx) => (
            <div
              key={idx}
              className="rounded-lg border border-white/5 bg-white/[0.01] p-3 space-y-1.5 transition-all duration-200 hover:bg-white/[0.02]"
            >
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <div className="flex items-center gap-1">
                  <User className="h-3.5 w-3.5 text-gray-400" />
                  <span className="font-medium text-gray-300">{note.author || "System"}</span>
                </div>
                {note.timestamp && (
                  <div className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    <span>{note.timestamp}</span>
                  </div>
                )}
              </div>
              <p className="text-xs text-gray-200 whitespace-pre-wrap leading-relaxed">
                {note.text}
              </p>
            </div>
          ))
        )}
      </div>

      {/* Note Form */}
      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="grid grid-cols-[120px_1fr] gap-2 items-center">
          <label htmlFor="author-input" className="text-xs text-muted-foreground">
            Author Email:
          </label>
          <input
            id="author-input"
            type="text"
            className="h-8 rounded border border-white/10 bg-background/50 px-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-primary"
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            placeholder="hr@company.com"
            required
          />
        </div>
        <div className="relative">
          <Textarea
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            placeholder="Write a recruiter note..."
            rows={3}
            className="w-full text-xs"
            disabled={submitting}
          />
          <div className="mt-2 flex justify-end">
            <Button type="submit" size="sm" disabled={submitting || !newNote.trim()}>
              <Send className="h-3.5 w-3.5 mr-1.5" />
              {submitting ? "Saving..." : "Add Note"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
};

export default CandidateNotesPanel;
