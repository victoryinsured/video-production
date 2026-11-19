import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, BrandTemplate, Course, Voice } from "../api";

export default function CoursesPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [brandTemplates, setBrandTemplates] = useState<BrandTemplate[]>([]);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const [coursesResp, brandResp, voicesResp] = await Promise.all([
        api.get<{ courses: Course[] }>("/courses"),
        api.get<{ templates: BrandTemplate[] }>("/brand-templates"),
        api.get<{ voices: Voice[] }>("/voices"),
      ]);
      setCourses(coursesResp.courses);
      setBrandTemplates(brandResp.templates);
      setVoices(voicesResp.voices);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load courses.");
    }
  }

  async function updateDefaults(courseId: string, patch: Record<string, unknown>) {
    setSavingId(courseId);
    try {
      await api.patch(`/courses/${courseId}`, patch);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save course defaults.");
    } finally {
      setSavingId(null);
    }
  }

  async function generate(courseId: string) {
    try {
      await api.post(`/courses/${courseId}/generate`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start generation.");
    }
  }

  return (
    <div>
      <h1>Courses</h1>
      <p className="page-subtitle">Review course defaults, then generate & publish entire courses.</p>
      {error && <div className="error-banner">{error}</div>}

      {courses.length === 0 && <p>No courses yet — upload a curriculum document to create one.</p>}

      {courses.map((course) => (
        <div className="card" key={course.id}>
          <div className="card-row">
            <div>
              <strong>{course.title}</strong>{" "}
              <span className={`badge status-${course.status}`}>{course.status}</span>
              <p className="page-subtitle" style={{ margin: "4px 0 0" }}>
                {course.modules.length} module(s), {course.modules.reduce((n, m) => n + m.lessons.length, 0)} lesson(s)
              </p>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="secondary" onClick={() => setExpanded(expanded === course.id ? null : course.id)}>
                {expanded === course.id ? "Hide details" : "Details"}
              </button>
              <Link className="btn secondary" to={`/dashboard/${course.id}`}>
                Dashboard
              </Link>
              <button onClick={() => generate(course.id)}>Generate &amp; Publish Entire Course</button>
            </div>
          </div>

          {expanded === course.id && (
            <div style={{ marginTop: 20 }}>
              <h2 style={{ marginTop: 0 }}>Course Defaults</h2>
              <div className="field-row">
                <div className="field">
                  <label>Brand template</label>
                  <select
                    value={course.brandTemplateId ?? ""}
                    onChange={(e) => updateDefaults(course.id, { brandTemplateId: e.target.value || null })}
                    disabled={savingId === course.id}
                  >
                    <option value="">Use global default</option>
                    {brandTemplates.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                        {t.isDefault ? " (default)" : ""}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Voice</label>
                  <select
                    value={course.voiceId ?? ""}
                    onChange={(e) => updateDefaults(course.id, { voiceId: e.target.value || null })}
                    disabled={savingId === course.id}
                  >
                    <option value="">Use global default</option>
                    {voices.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name}
                        {v.isDefault ? " (default)" : ""}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label>AWS bucket</label>
                  <input
                    type="text"
                    defaultValue={course.awsBucket ?? ""}
                    onBlur={(e) => updateDefaults(course.id, { awsBucket: e.target.value || null })}
                  />
                </div>
                <div className="field">
                  <label>AWS key prefix</label>
                  <input
                    type="text"
                    defaultValue={course.awsKeyPrefix ?? ""}
                    onBlur={(e) => updateDefaults(course.id, { awsKeyPrefix: e.target.value || null })}
                  />
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Bunny Stream library ID</label>
                  <input
                    type="text"
                    defaultValue={course.bunnyLibraryId ?? ""}
                    onBlur={(e) => updateDefaults(course.id, { bunnyLibraryId: e.target.value || null })}
                  />
                </div>
                <div className="field">
                  <label>Moodle course ID</label>
                  <input
                    type="number"
                    defaultValue={course.moodleCourseId ?? ""}
                    onBlur={(e) =>
                      updateDefaults(course.id, { moodleCourseId: e.target.value ? Number(e.target.value) : null })
                    }
                  />
                </div>
              </div>

              <h2>Lessons</h2>
              {course.modules.map((module) => (
                <div key={module.id} style={{ marginBottom: 12 }}>
                  <strong>
                    Module {module.number}: {module.title}
                  </strong>
                  <table>
                    <tbody>
                      {module.lessons.map((lesson) => (
                        <tr key={lesson.id}>
                          <td>{lesson.number}</td>
                          <td>{lesson.title}</td>
                          <td>
                            <span className={`badge status-${lesson.status}`}>{lesson.status}</span>
                          </td>
                          <td>
                            <Link className="btn secondary" to={`/courses/${course.id}/lessons/${lesson.id}`}>
                              Edit
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
