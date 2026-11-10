import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, Course, DashboardCourseSummary, JobStep } from "../api";

const LESSON_STEPS = ["slides", "narration", "video", "editable_assets", "aws_upload", "bunny_upload", "moodle_publish"];

export default function DashboardPage() {
  const { courseId } = useParams();
  if (courseId) return <CourseDashboard courseId={courseId} />;
  return <OverviewDashboard />;
}

function OverviewDashboard() {
  const [summaries, setSummaries] = useState<DashboardCourseSummary[]>([]);
  const [counts, setCounts] = useState({ failedSteps: 0, runningSteps: 0, pendingSteps: 0 });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  async function load() {
    try {
      const resp = await api.get<{ courses: DashboardCourseSummary[]; failedSteps: number; runningSteps: number; pendingSteps: number }>(
        "/dashboard"
      );
      setSummaries(resp.courses);
      setCounts(resp);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load dashboard.");
    }
  }

  return (
    <div>
      <h1>Production Dashboard</h1>
      <p className="page-subtitle">Live status across every course. Refreshes automatically.</p>
      {error && <div className="error-banner">{error}</div>}

      <div className="card-row" style={{ marginBottom: 16 }}>
        <div className="step-chip">Pending: {counts.pendingSteps}</div>
        <div className="step-chip">Running: {counts.runningSteps}</div>
        <div className="step-chip">Failed: {counts.failedSteps}</div>
      </div>

      {summaries.map((course) => (
        <Link to={`/dashboard/${course.id}`} key={course.id} className="card" style={{ display: "block", textDecoration: "none", color: "inherit" }}>
          <div className="card-row">
            <div>
              <strong>{course.title}</strong> <span className={`badge status-${course.status}`}>{course.status}</span>
              <p className="page-subtitle" style={{ margin: "4px 0 0" }}>
                {course.lessonCount} lesson(s) across {course.moduleCount} module(s)
              </p>
            </div>
            <div className="step-list">
              {Object.entries(course.lessonsByStatus).map(([status, count]) => (
                <span key={status} className={`badge status-${status}`}>
                  {status}: {count}
                </span>
              ))}
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}

function CourseDashboard({ courseId }: { courseId: string }) {
  const [course, setCourse] = useState<Course | null>(null);
  const [jobSteps, setJobSteps] = useState<JobStep[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    load();
    const interval = setInterval(load, 4000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId]);

  async function load() {
    try {
      const [courseResp, jobsResp] = await Promise.all([
        api.get<{ course: Course }>(`/dashboard/course/${courseId}`),
        api.get<{ jobSteps: JobStep[] }>(`/jobs/course/${courseId}`),
      ]);
      setCourse(courseResp.course);
      setJobSteps(jobsResp.jobSteps);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load course dashboard.");
    }
  }

  async function retry(lessonId: string) {
    try {
      await api.post(`/lessons/${lessonId}/retry`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Retry failed.");
    }
  }

  if (!course) return <div>{error ?? "Loading…"}</div>;

  function stepsFor(lessonId: string) {
    return jobSteps.filter((s) => s.lessonId === lessonId && !s.resourceId);
  }

  return (
    <div>
      <h1>{course.title}</h1>
      <p className="page-subtitle">Production status for every lesson.</p>
      {error && <div className="error-banner">{error}</div>}

      {course.modules.map((module) => (
        <div key={module.id}>
          <h2>
            Module {module.number}: {module.title}
          </h2>
          {module.lessons.map((lesson) => {
            const steps = stepsFor(lesson.id);
            const hasFailed = steps.some((s) => s.status === "failed");
            return (
              <div className="card" key={lesson.id}>
                <div className="card-row">
                  <div>
                    <strong>
                      {lesson.number} — {lesson.title}
                    </strong>{" "}
                    <span className={`badge status-${lesson.status}`}>{lesson.status}</span>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    {hasFailed && (
                      <button className="secondary" onClick={() => retry(lesson.id)}>
                        Retry failed steps
                      </button>
                    )}
                    <Link className="btn secondary" to={`/courses/${course.id}/lessons/${lesson.id}`}>
                      Open
                    </Link>
                  </div>
                </div>
                <div className="step-list" style={{ marginTop: 10 }}>
                  {LESSON_STEPS.map((stepName) => {
                    const step = steps.find((s) => s.step === stepName);
                    const status = step?.status ?? "pending";
                    return (
                      <span key={stepName} className={`badge status-${status}`} title={step?.error ?? ""}>
                        {stepName}: {status}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
