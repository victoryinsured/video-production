import { FormEvent, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError, BrandTemplate, JobStep, Lesson, Resource, Voice } from "../api";

const LESSON_STEPS = ["slides", "narration", "video", "editable_assets", "aws_upload", "bunny_upload", "moodle_publish"];

export default function LessonPage() {
  const { lessonId } = useParams();
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [jobSteps, setJobSteps] = useState<JobStep[]>([]);
  const [brandTemplates, setBrandTemplates] = useState<BrandTemplate[]>([]);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lessonId]);

  async function load() {
    if (!lessonId) return;
    try {
      const [lessonResp, brandResp, voicesResp] = await Promise.all([
        api.get<{ lesson: Lesson; jobSteps: JobStep[] }>(`/lessons/${lessonId}`),
        api.get<{ templates: BrandTemplate[] }>("/brand-templates"),
        api.get<{ voices: Voice[] }>("/voices"),
      ]);
      setLesson(lessonResp.lesson);
      setJobSteps(lessonResp.jobSteps);
      setBrandTemplates(brandResp.templates);
      setVoices(voicesResp.voices);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load lesson.");
    }
  }

  async function handleSave(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!lesson) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    const form = new FormData(e.currentTarget);
    try {
      await api.patch(`/lessons/${lesson.id}`, {
        title: form.get("title"),
        videoDescription: form.get("videoDescription"),
        scriptText: form.get("scriptText"),
        productionInstructions: form.get("productionInstructions"),
        brandTemplateId: (form.get("brandTemplateId") as string) || null,
        voiceId: (form.get("voiceId") as string) || null,
      });
      setNotice("Saved. Any affected pipeline steps have been queued for regeneration.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function regenerateStep(step: string) {
    if (!lesson) return;
    try {
      await api.post(`/lessons/${lesson.id}/regenerate-step`, { step });
      setNotice(`Queued "${step}" (and anything downstream of it) for regeneration.`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not queue regeneration.");
    }
  }

  async function retryFailed() {
    if (!lesson) return;
    try {
      const resp = await api.post<{ retried: number }>(`/lessons/${lesson.id}/retry`);
      setNotice(`Retrying ${resp.retried} failed step(s).`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Retry failed.");
    }
  }

  async function uploadVideo(file: File) {
    if (!lesson) return;
    const form = new FormData();
    form.append("video", file);
    try {
      await api.upload(`/lessons/${lesson.id}/video`, form);
      setNotice("Replacement video uploaded. Upload/publish steps have been queued.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Video upload failed.");
    }
  }

  async function pasteBunnyId(bunnyVideoId: string) {
    if (!lesson || !bunnyVideoId.trim()) return;
    try {
      await api.post(`/lessons/${lesson.id}/bunny-id`, { bunnyVideoId: bunnyVideoId.trim() });
      setNotice("Bunny video ID saved. Moodle publish has been queued.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save Bunny video ID.");
    }
  }

  async function addResource(title: string) {
    if (!lesson || !title.trim()) return;
    try {
      await api.post(`/lessons/${lesson.id}/resources`, { title: title.trim() });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add resource.");
    }
  }

  async function uploadResourceFile(resourceId: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    try {
      await api.upload(`/lessons/resources/${resourceId}/upload`, form);
      setNotice("Resource file uploaded and queued for distribution.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Resource upload failed.");
    }
  }

  async function deleteResource(resourceId: string) {
    try {
      await api.delete(`/lessons/resources/${resourceId}`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete resource.");
    }
  }

  if (!lesson) return <div>{error ?? "Loading…"}</div>;

  const lessonSteps = jobSteps.filter((s) => !s.resourceId);
  const hasFailed = lessonSteps.some((s) => s.status === "failed");

  return (
    <div>
      <h1>
        {lesson.number} — {lesson.title}
      </h1>
      <p className="page-subtitle">Edit the lesson, override brand/voice, or manually replace production outputs.</p>

      {error && <div className="error-banner">{error}</div>}
      {notice && <div className="success-banner">{notice}</div>}

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Pipeline status</h2>
        <div className="step-list">
          {LESSON_STEPS.map((stepName) => {
            const step = lessonSteps.find((s) => s.step === stepName);
            const status = step?.status ?? "pending";
            return (
              <span key={stepName} className={`badge status-${status}`} title={step?.error ?? ""}>
                {stepName}: {status}
              </span>
            );
          })}
        </div>
        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {hasFailed && (
            <button className="secondary" onClick={retryFailed}>
              Retry failed steps
            </button>
          )}
          {LESSON_STEPS.map((stepName) => (
            <button key={stepName} className="secondary" onClick={() => regenerateStep(stepName)}>
              Regenerate {stepName}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSave}>
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Lesson content</h2>
          <div className="field">
            <label>Title</label>
            <input type="text" name="title" defaultValue={lesson.title} />
          </div>
          <div className="field">
            <label>Video description (used for the Moodle activity description)</label>
            <textarea name="videoDescription" defaultValue={lesson.videoDescription} />
          </div>
          <div className="field">
            <label>Script (sent to narration verbatim — editing this re-renders slides and narration)</label>
            <textarea name="scriptText" defaultValue={lesson.scriptText} style={{ minHeight: 220 }} />
          </div>
          <div className="field">
            <label>Production instructions (internal notes, not shown to learners)</label>
            <textarea name="productionInstructions" defaultValue={lesson.productionInstructions} />
          </div>
          <div className="field-row">
            <div className="field">
              <label>Brand override</label>
              <select name="brandTemplateId" defaultValue={lesson.brandTemplateId ?? ""}>
                <option value="">Use course default</option>
                {brandTemplates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Voice override</label>
              <select name="voiceId" defaultValue={lesson.voiceId ?? ""}>
                <option value="">Use course default</option>
                {voices.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Manual overrides</h2>
        <div className="field">
          <label>Upload a replacement video (skips rendering entirely)</label>
          <input
            type="file"
            accept="video/*"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadVideo(file);
            }}
          />
        </div>
        <div className="field">
          <label>Paste a Bunny Stream video ID (if already uploaded directly in Bunny)</label>
          <PasteIdForm placeholder="e.g. 3f29a1c4-..." onSubmit={pasteBunnyId} buttonLabel="Save Bunny ID" />
        </div>
        <p className="page-subtitle" style={{ marginBottom: 0 }}>
          Current Bunny video ID: {lesson.bunnyVideoId ?? "none"} · AWS key: {lesson.awsVideoKey ?? "none"} · Moodle
          activity: {lesson.moodleActivityId ?? "none"}
        </p>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Resources</h2>
        {(lesson.resources ?? []).map((resource) => (
          <ResourceRow
            key={resource.id}
            resource={resource}
            onUpload={(file) => uploadResourceFile(resource.id, file)}
            onDelete={() => deleteResource(resource.id)}
          />
        ))}
        <PasteIdForm placeholder="New resource title" onSubmit={addResource} buttonLabel="Add resource" />
      </div>
    </div>
  );
}

function ResourceRow({
  resource,
  onUpload,
  onDelete,
}: {
  resource: Resource;
  onUpload: (file: File) => void;
  onDelete: () => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="card-row" style={{ borderTop: "1px solid var(--border)", paddingTop: 12, marginTop: 12 }}>
      <div>
        <strong>{resource.title}</strong> <span className={`badge status-${resource.status}`}>{resource.status}</span>
        <p className="page-subtitle" style={{ margin: "4px 0 0" }}>
          {resource.filename || "No file uploaded yet"} · {resource.resourceType}
        </p>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          ref={fileInputRef}
          type="file"
          style={{ display: "none" }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onUpload(file);
          }}
        />
        <button className="secondary" onClick={() => fileInputRef.current?.click()}>
          Upload file
        </button>
        <button className="danger" onClick={onDelete}>
          Delete
        </button>
      </div>
    </div>
  );
}

function PasteIdForm({
  placeholder,
  buttonLabel,
  onSubmit,
}: {
  placeholder: string;
  buttonLabel: string;
  onSubmit: (value: string) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <input type="text" placeholder={placeholder} value={value} onChange={(e) => setValue(e.target.value)} />
      <button
        type="button"
        className="secondary"
        onClick={() => {
          onSubmit(value);
          setValue("");
        }}
      >
        {buttonLabel}
      </button>
    </div>
  );
}
