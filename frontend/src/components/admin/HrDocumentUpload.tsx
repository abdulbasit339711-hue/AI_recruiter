"use client";

/**
 * HrDocumentUpload.tsx
 * ────────────────────
 * HR document upload panel for the candidate profile page.
 *
 * Features
 * ─────────
 * • Drag-and-drop OR click-to-browse file selection
 * • Accepts PDF (text + image/scanned), JPG, PNG, TIFF, BMP, WEBP, TXT
 * • Shows a live upload progress bar
 * • Displays extracted profile fields after the server processes the document
 * • Lets HR choose the document type (CV / Offer Letter / Contract / …)
 * • "Apply to Profile" button to merge extracted fields into the candidate record
 * • Lists existing documents with delete capability
 */

import { useCallback, useEffect, useRef, useState } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ExtractedFields {
  name?: string;
  email?: string;
  phone?: string;
  date_of_birth?: string;
  national_id?: string;
  address?: string;
  current_role?: string;
  department?: string;
  employee_id?: string;
  companies?: string[];
  total_years_experience?: number;
  education?: { degree?: string; institution?: string; year?: number | null };
  skills?: string[];
  certifications?: string[];
  emergency_contact?: string;
  document_type?: string;
  document_summary?: string;
}

interface UploadResult {
  id: number;
  candidate_id: number;
  filename: string;
  file_type: string;
  file_size_kb: number;
  ocr_used: boolean;
  document_type: string;
  uploaded_at: string;
  extracted_fields: ExtractedFields;
  fields_applied_to_profile: Record<string, unknown>;
  message: string;
}

interface DocumentRecord {
  id: number;
  candidate_id: number;
  filename: string;
  file_type: string;
  file_size_kb: number;
  ocr_used: boolean;
  document_type: string;
  uploaded_by?: string;
  uploaded_at?: string;
  extracted_fields: ExtractedFields;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const DOCUMENT_TYPES = [
  "CV",
  "Offer Letter",
  "Contract",
  "ID Document",
  "Certificate",
  "Medical",
  "Reference Letter",
  "Other",
];

const ACCEPTED_EXTENSIONS = ".pdf,.jpg,.jpeg,.png,.tiff,.tif,.bmp,.webp,.txt";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fileSize(kb: number): string {
  return kb < 1024 ? `${kb} KB` : `${(kb / 1024).toFixed(1)} MB`;
}

function formatDate(iso?: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

// ── Subcomponents ─────────────────────────────────────────────────────────────

function FieldGrid({ fields }: { fields: ExtractedFields }) {
  const rows: { label: string; value: string }[] = [];

  const add = (label: string, value: unknown) => {
    if (!value || (typeof value === "string" && !value.trim())) return;
    if (Array.isArray(value) && value.length === 0) return;
    rows.push({
      label,
      value: Array.isArray(value) ? value.join(", ") : String(value),
    });
  };

  add("Name", fields.name);
  add("Email", fields.email);
  add("Phone", fields.phone);
  add("Date of Birth", fields.date_of_birth);
  add("National / ID No.", fields.national_id);
  add("Employee ID", fields.employee_id);
  add("Current Role", fields.current_role);
  add("Department", fields.department);
  add("Address", fields.address);
  add("Emergency Contact", fields.emergency_contact);
  add("Companies", fields.companies);
  add("Years Experience", fields.total_years_experience);
  add("Skills", fields.skills);
  add("Certifications", fields.certifications);

  if (fields.education?.degree) {
    add(
      "Education",
      [fields.education.degree, fields.education.institution, fields.education.year]
        .filter(Boolean)
        .join(", ")
    );
  }

  if (rows.length === 0) return null;

  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm mt-2">
      {rows.map(({ label, value }) => (
        <div key={label} className="col-span-1">
          <span className="font-medium text-gray-600">{label}: </span>
          <span className="text-gray-900">{value}</span>
        </div>
      ))}
    </div>
  );
}

function DocumentRow({
  doc,
  apiBase,
  authHeader,
  onDeleted,
  onApplied,
}: {
  doc: DocumentRecord;
  apiBase: string;
  authHeader: string;
  onDeleted: (id: number) => void;
  onApplied: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyMsg, setApplyMsg] = useState<string | null>(null);

  async function handleDelete() {
    if (!confirm(`Delete document "${doc.filename}"?`)) return;
    setDeleting(true);
    try {
      const res = await fetch(
        `${apiBase}/candidates/${doc.candidate_id}/documents/${doc.id}`,
        { method: "DELETE", headers: { Authorization: authHeader } }
      );
      if (res.ok) onDeleted(doc.id);
    } finally {
      setDeleting(false);
    }
  }

  async function handleApply() {
    setApplying(true);
    setApplyMsg(null);
    try {
      const res = await fetch(
        `${apiBase}/candidates/${doc.candidate_id}/documents/${doc.id}/apply-to-profile`,
        { method: "POST", headers: { Authorization: authHeader } }
      );
      const data = await res.json();
      setApplyMsg(data.message || "Applied.");
      onApplied(doc.id);
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white shadow-sm">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-2xl">{fileIcon(doc.file_type)}</span>
          <div>
            <p className="font-semibold text-gray-800 text-sm">{doc.filename}</p>
            <p className="text-xs text-gray-500">
              {doc.document_type} · {fileSize(doc.file_size_kb)}
              {doc.ocr_used && (
                <span className="ml-2 bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded text-[10px] font-medium">
                  OCR
                </span>
              )}
              {doc.uploaded_at && (
                <span className="ml-2">{formatDate(doc.uploaded_at)}</span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-blue-600 hover:underline"
          >
            {expanded ? "▲ Hide" : "▼ Extracted fields"}
          </button>
          <button
            onClick={handleApply}
            disabled={applying}
            className="text-xs bg-green-600 hover:bg-green-700 text-white px-2 py-1 rounded disabled:opacity-50"
          >
            {applying ? "Applying…" : "Apply to Profile"}
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="text-xs bg-red-500 hover:bg-red-600 text-white px-2 py-1 rounded disabled:opacity-50"
          >
            {deleting ? "…" : "Delete"}
          </button>
        </div>
      </div>

      {applyMsg && (
        <p className="text-xs text-green-700 mt-2 bg-green-50 px-3 py-1 rounded">
          ✓ {applyMsg}
        </p>
      )}

      {/* Expanded extracted fields */}
      {expanded && (
        <div className="mt-3 border-t pt-3">
          {doc.extracted_fields?.document_summary && (
            <p className="text-xs italic text-gray-600 mb-2">
              {doc.extracted_fields.document_summary}
            </p>
          )}
          <FieldGrid fields={doc.extracted_fields} />
        </div>
      )}
    </div>
  );
}

function fileIcon(type?: string): string {
  if (!type) return "📄";
  if (["jpg", "jpeg", "png", "bmp", "webp", "tiff", "tif"].includes(type)) return "🖼️";
  if (type === "pdf") return "📕";
  if (type === "txt") return "📝";
  return "📄";
}

// ── Main Component ────────────────────────────────────────────────────────────

interface HrDocumentUploadProps {
  candidateId: number;
  /** Base API URL, e.g. "http://localhost:8000" */
  apiBase?: string;
  /** Value for the Authorization header */
  authToken?: string;
}

export default function HrDocumentUpload({
  candidateId,
  apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  authToken,
}: HrDocumentUploadProps) {
  const authHeader = authToken ? `Bearer ${authToken}` : "";

  // ── State ─────────────────────────────────────────────────────────────────
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<string>("Other");
  const [autoApply, setAutoApply] = useState(true);
  const [progress, setProgress] = useState<number>(0);  // 0-100
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Fetch existing documents ──────────────────────────────────────────────
  const fetchDocuments = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const res = await fetch(`${apiBase}/candidates/${candidateId}/documents`, {
        headers: { Authorization: authHeader },
      });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents ?? []);
      }
    } finally {
      setLoadingDocs(false);
    }
  }, [apiBase, candidateId, authHeader]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // ── Drag-and-drop handlers ────────────────────────────────────────────────
  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  };
  const onDragLeave = () => setDragging(false);
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFileSelected(file);
  };

  function handleFileSelected(file: File) {
    setSelectedFile(file);
    setResult(null);
    setError(null);
    setProgress(0);
  }

  // ── Upload logic (XHR for progress tracking) ──────────────────────────────
  async function handleUpload() {
    if (!selectedFile) return;
    setUploading(true);
    setError(null);
    setResult(null);
    setProgress(0);

    const fd = new FormData();
    fd.append("file", selectedFile);
    fd.append("document_type", docType);
    fd.append("auto_apply", String(autoApply));

    await new Promise<void>((resolve) => {
      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener("progress", (evt) => {
        if (evt.lengthComputable) {
          setProgress(Math.round((evt.loaded / evt.total) * 90));
        }
      });

      xhr.addEventListener("load", () => {
        setProgress(100);
        try {
          const data: UploadResult = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) {
            setResult(data);
            setSelectedFile(null);
            fetchDocuments();
          } else {
            setError((data as any).detail ?? "Upload failed.");
          }
        } catch {
          setError("Unexpected server response.");
        }
        setUploading(false);
        resolve();
      });

      xhr.addEventListener("error", () => {
        setError("Network error during upload.");
        setUploading(false);
        resolve();
      });

      xhr.open("POST", `${apiBase}/candidates/${candidateId}/documents`);
      if (authHeader) xhr.setRequestHeader("Authorization", authHeader);
      xhr.send(fd);
    });
  }

  function handleDocDeleted(id: number) {
    setDocuments((prev) => prev.filter((d) => d.id !== id));
  }

  function handleDocApplied(_id: number) {
    // Could trigger parent refresh here if needed
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* ── Upload Area ─────────────────────────────────────────────────── */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <h3 className="font-semibold text-gray-700 mb-4 text-base flex items-center gap-2">
          <span>📎</span> Upload HR Document
        </h3>

        {/* Drag-and-drop zone */}
        <div
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            dragging
              ? "border-blue-500 bg-blue-50"
              : "border-gray-300 hover:border-blue-400 hover:bg-gray-50"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS}
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFileSelected(f);
              e.target.value = "";
            }}
          />
          {selectedFile ? (
            <div className="space-y-1">
              <p className="text-2xl">{fileIcon(selectedFile.name.split(".").pop())}</p>
              <p className="font-medium text-gray-800">{selectedFile.name}</p>
              <p className="text-sm text-gray-500">
                {(selectedFile.size / 1024).toFixed(0)} KB
              </p>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedFile(null);
                }}
                className="text-xs text-red-500 hover:underline mt-1"
              >
                Remove
              </button>
            </div>
          ) : (
            <div className="space-y-1 text-gray-500">
              <p className="text-3xl">📁</p>
              <p className="font-medium">Drop a file here or click to browse</p>
              <p className="text-xs">
                PDF (text or scanned), JPG, PNG, TIFF, BMP, WEBP, TXT · max 10 MB
              </p>
              <p className="text-xs text-purple-600 font-medium mt-1">
                ✨ Scanned &amp; image documents are processed with OCR automatically
              </p>
            </div>
          )}
        </div>

        {/* Options row */}
        {selectedFile && (
          <div className="mt-4 flex flex-col sm:flex-row items-start sm:items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-600 whitespace-nowrap">
                Document Type
              </label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                {DOCUMENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input
                type="checkbox"
                checked={autoApply}
                onChange={(e) => setAutoApply(e.target.checked)}
                className="w-4 h-4 accent-blue-600"
              />
              Auto-fill candidate profile from extracted data
            </label>
          </div>
        )}

        {/* Upload button */}
        {selectedFile && (
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="mt-4 w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg transition-colors"
          >
            {uploading ? "Processing…" : "Upload & Extract"}
          </button>
        )}

        {/* Progress bar */}
        {uploading && (
          <div className="mt-3">
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-gray-500 mt-1 text-center">
              {progress < 95
                ? "Uploading & running OCR / LLM extraction…"
                : "Finalising…"}
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mt-3 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
            ❌ {error}
          </div>
        )}

        {/* Upload result – extracted fields preview */}
        {result && (
          <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4">
            <p className="text-green-800 font-semibold text-sm mb-1">
              ✅ {result.message}
            </p>

            {result.ocr_used && (
              <p className="text-xs text-purple-700 bg-purple-50 rounded px-2 py-1 inline-block mb-2">
                🔍 OCR was used to read this document
              </p>
            )}

            {result.extracted_fields?.document_summary && (
              <p className="text-xs italic text-gray-600 mb-2">
                {result.extracted_fields.document_summary}
              </p>
            )}

            <FieldGrid fields={result.extracted_fields} />

            {Object.keys(result.fields_applied_to_profile).length > 0 && (
              <p className="text-xs text-green-700 mt-2 font-medium">
                ✓ Profile fields updated:{" "}
                {Object.keys(result.fields_applied_to_profile).join(", ")}
              </p>
            )}
          </div>
        )}
      </div>

      {/* ── Existing Documents ───────────────────────────────────────────── */}
      <div>
        <h3 className="font-semibold text-gray-700 mb-3 text-base flex items-center gap-2">
          <span>📂</span> Uploaded Documents
          <span className="ml-auto text-xs text-gray-400 font-normal">
            {documents.length} document{documents.length !== 1 ? "s" : ""}
          </span>
        </h3>

        {loadingDocs ? (
          <p className="text-sm text-gray-400 text-center py-6">Loading…</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6 border border-dashed border-gray-200 rounded-lg">
            No documents uploaded yet.
          </p>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => (
              <DocumentRow
                key={doc.id}
                doc={doc}
                apiBase={apiBase}
                authHeader={authHeader}
                onDeleted={handleDocDeleted}
                onApplied={handleDocApplied}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
