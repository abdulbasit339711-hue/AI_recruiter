import { useSyncExternalStore } from 'react';
import type { Job, Candidate } from './types';
import { jobs as initialJobs, candidates as initialCandidates } from './data';

let _jobs: Job[] = [...initialJobs];
let _candidates: Candidate[] = [...initialCandidates];
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

function getSnapshot() {
  return _jobs;
}

function getCandidateSnapshot() {
  return _candidates;
}

// We use a single version counter to drive re-renders for both lists.
let _version = 0;
function getVersion() {
  return _version;
}

export function useJobs() {
  return useSyncExternalStore(
    (cb) => {
      const unsub = subscribe(cb);
      return unsub;
    },
    () => _jobs,
    () => _jobs,
  );
}

export function useCandidates() {
  return useSyncExternalStore(
    (cb) => subscribe(cb),
    () => _candidates,
    () => _candidates,
  );
}

export const storeActions = {
  addJob(job: Job) {
    _jobs = [job, ..._jobs];
    _version++;
    emit();
  },
  archiveJob(id: string) {
    _jobs = _jobs.map((j) => (j.id === id ? { ...j, status: 'Archived' as const } : j));
    _version++;
    emit();
  },
  updateCandidateStatus(id: string, status: Candidate['status']) {
    _candidates = _candidates.map((c) => (c.id === id ? { ...c, status } : c));
    _version++;
    emit();
  },
};
