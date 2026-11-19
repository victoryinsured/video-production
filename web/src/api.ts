/** Thin fetch wrapper for the Victory Video Studio API. Same-origin in both dev (via the Vite
 * proxy) and production (the Express app serves this build directly) — no base URL needed. */

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers },
    credentials: "same-origin",
  });
  if (resp.status === 401) {
    throw new ApiError("Not authenticated.", 401);
  }
  const text = await resp.text();
  const data = text ? JSON.parse(text) : {};
  if (!resp.ok) {
    throw new ApiError((data as { error?: string }).error ?? `Request failed (${resp.status})`, resp.status);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
};

// --- Domain types (loosely typed — the server is the source of truth; this is a convenience
// layer for the UI, not a strict contract test). ----------------------------------------------

export interface Resource {
  id: string;
  lessonId: string;
  title: string;
  description: string;
  instructions: string;
  filename: string;
  resourceType: string;
  storagePath: string | null;
  linkUrl: string | null;
  awsKey: string | null;
  moodleActivityId: number | null;
  status: string;
}

export interface JobStep {
  id: string;
  lessonId: string;
  resourceId: string;
  step: string;
  status: string;
  error: string | null;
  resultJson: string | null;
  attempts: number;
}

export interface Lesson {
  id: string;
  moduleId: string;
  number: string;
  order: number;
  title: string;
  lessonType: string;
  description: string;
  videoDescription: string;
  scriptText: string;
  knowledgeChecks: string;
  productionInstructions: string;
  tags: string;
  brandTemplateId: string | null;
  voiceId: string | null;
  status: string;
  videoPath: string | null;
  bunnyVideoId: string | null;
  awsVideoKey: string | null;
  moodleActivityId: number | null;
  resources?: Resource[];
}

export interface Module {
  id: string;
  courseId: string;
  number: string;
  title: string;
  description: string;
  order: number;
  lessons: Lesson[];
}

export interface Course {
  id: string;
  title: string;
  slug: string;
  description: string;
  status: string;
  brandTemplateId: string | null;
  voiceId: string | null;
  awsBucket: string | null;
  awsRegion: string | null;
  awsKeyPrefix: string | null;
  bunnyLibraryId: string | null;
  bunnyCollectionId: string | null;
  moodleCourseId: number | null;
  modules: Module[];
}

export interface BrandTemplate {
  id: string;
  name: string;
  isDefault: boolean;
  colors: string;
  fonts: string;
  cover: string;
  logoPath: string | null;
  introVideoPath: string | null;
  outroVideoPath: string | null;
  width: number;
  height: number;
  fps: number;
  audioBitrate: string;
  captionsEnabled: boolean;
  captionFontSize: number;
  captionPosition: string;
  textScale: number;
}

export interface Voice {
  id: string;
  name: string;
  elevenLabsVoiceId: string;
  isDefault: boolean;
}

export interface DashboardCourseSummary {
  id: string;
  title: string;
  slug: string;
  status: string;
  moduleCount: number;
  lessonCount: number;
  lessonsByStatus: Record<string, number>;
  updatedAt: string;
}
