import { create } from "zustand";

interface RecruiterState {
  selectedJobId: number | null;
  setSelectedJobId: (id: number | null) => void;
  selectedCandidateId: number | null;
  setSelectedCandidateId: (id: number | null) => void;
  showArchivedJobs: boolean;
  setShowArchivedJobs: (val: boolean) => void;
  minScoreFilter: number;
  setMinScoreFilter: (val: number) => void;
  statusFilters: ("Processed" | "Pending" | "Failed")[];
  setStatusFilters: (val: ("Processed" | "Pending" | "Failed")[]) => void;
}

export const useRecruiterStore = create<RecruiterState>((set) => ({
  selectedJobId: null,
  setSelectedJobId: (id) => set({ selectedJobId: id, selectedCandidateId: null }),
  selectedCandidateId: null,
  setSelectedCandidateId: (id) => set({ selectedCandidateId: id }),
  showArchivedJobs: false,
  setShowArchivedJobs: (val) => set({ showArchivedJobs: val }),
  minScoreFilter: 0,
  setMinScoreFilter: (val) => set({ minScoreFilter: val }),
  statusFilters: ["Processed", "Pending"],
  setStatusFilters: (val) => set({ statusFilters: val }),
}));
