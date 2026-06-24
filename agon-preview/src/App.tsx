import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AdminDashboard } from './pages/AdminDashboard';
import { CandidatesList } from './pages/CandidatesList';
import { CandidateInterview } from './pages/CandidateInterview';
import { JobManagement } from './pages/JobManagement';
import { LiveInterview } from './pages/LiveInterview';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/admin/dashboard" replace />} />
        <Route path="/admin/dashboard" element={<AdminDashboard />} />
        <Route path="/admin/candidates" element={<CandidatesList />} />
        <Route path="/admin/candidates/:id/interview" element={<CandidateInterview />} />
        <Route path="/admin/jobs" element={<JobManagement />} />
        <Route path="/interview/:token" element={<LiveInterview />} />
        <Route path="*" element={<Navigate to="/admin/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
