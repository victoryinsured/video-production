import { DragEvent, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";

interface DiffEntry {
  moduleNumber: string;
  lessonNumber?: string;
  title: string;
  status: "NEW" | "CHANGED" | "UNCHANGED" | "REMOVED";
}

interface CourseDiff {
  courseExists: boolean;
  modules: DiffEntry[];
  lessons: DiffEntry[];
}

interface ParsedLesson {
  number: string;
  title: string;
  videoDescription: string;
  scriptText: string;
  resources: Array<{ title: string; filename: string; resourceType: string }>;
}

interface ParsedModule {
  number: string;
  title: string;
  lessons: ParsedLesson[];
}

interface ParsedCourse {
  title: string;
  description: string;
  modules: ParsedModule[];
}

interface UploadResponse {
  document: { id: string };
  course: ParsedCourse;
  diff: CourseDiff;
}

export default function UploadPage() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [approving, setApproving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  async function handleFile(file: File) {
    setUploading(true);
    setError(null);
    setResult(null);
    const form = new FormData();
    form.append("document", file);
    try {
      const response = await api.upload<UploadResponse>("/documents", form);
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  async function approve(startProduction: boolean) {
    if (!result) return;
    setApproving(true);
    setError(null);
    try {
      const response = await api.post<{ course: { id: string } }>(`/documents/${result.document.id}/approve`, {
        startProduction,
      });
      navigate(`/dashboard/${response.course.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Approval failed.");
    } finally {
      setApproving(false);
    }
  }

  const lessonCount = result?.course.modules.reduce((sum, m) => sum + m.lessons.length, 0) ?? 0;

  return (
    <div>
      <h1>Upload Curriculum</h1>
      <p className="page-subtitle">
        Upload a DOCX, PDF, TXT, or Markdown curriculum document. It will be parsed into
        course/module/lesson structure for your review before anything is produced.
      </p>

      {error && <div className="error-banner">{error}</div>}

      <div
        className={"dropzone" + (dragging ? " dragging" : "")}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        {uploading ? "Uploading and parsing…" : "Click to choose a file, or drag one here"}
        <input
          ref={inputRef}
          type="file"
          accept=".docx,.pdf,.txt,.md,.markdown"
          style={{ display: "none" }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
      </div>

      {result && (
        <div style={{ marginTop: 24 }}>
          <h2>
            {result.diff.courseExists ? "Updating" : "New course"}: {result.course.title}
          </h2>
          <p className="page-subtitle">
            {lessonCount} lesson(s) across {result.course.modules.length} module(s).
          </p>

          <div className="card">
            <h2 style={{ marginTop: 0 }}>Changes</h2>
            <table>
              <thead>
                <tr>
                  <th>Module</th>
                  <th>Lesson</th>
                  <th>Title</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {result.diff.lessons.map((entry) => (
                  <tr key={`${entry.moduleNumber}-${entry.lessonNumber}`}>
                    <td>{entry.moduleNumber}</td>
                    <td>{entry.lessonNumber}</td>
                    <td>{entry.title}</td>
                    <td>
                      <span className={`badge diff-${entry.status.toLowerCase()}`}>{entry.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card-row">
            <div>
              <strong>Ready to proceed?</strong>
              <p className="page-subtitle" style={{ margin: "4px 0 0" }}>
                Approve to save this into your course library, or approve and start production immediately.
              </p>
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <button className="secondary" disabled={approving} onClick={() => approve(false)}>
                Approve only
              </button>
              <button disabled={approving} onClick={() => approve(true)}>
                {approving ? "Working…" : "Approve & Generate"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
