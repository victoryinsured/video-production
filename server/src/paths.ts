import fs from "node:fs";
import path from "node:path";
import { env } from "./env";

/**
 * Reduce an untrusted filename (from a parsed curriculum document's `RESOURCE FILENAME:` value,
 * or an uploaded file's original name) to a safe basename: no directory separators, no leading
 * dots that could resolve to a parent directory, and a restricted character set. Protects every
 * local disk write and S3 key built from these values against path traversal.
 */
export function sanitizeFilename(input: string): string {
  const base = path.basename(input.trim());
  const cleaned = base.replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^\.+/, "").slice(0, 200);
  return cleaned.length > 0 ? cleaned : "file";
}

function ensureDir(dir: string): string {
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export const storageRoot = path.resolve(env.storageRoot);

export function uploadsDir(): string {
  return ensureDir(path.join(storageRoot, "uploads"));
}

export function jobsDir(): string {
  return ensureDir(path.join(storageRoot, "jobs"));
}

export function courseOutputDir(courseSlug: string): string {
  return ensureDir(path.join(storageRoot, "output", sanitizeFilename(courseSlug)));
}

export function lessonOutputDir(courseSlug: string, moduleSlug: string, lessonSlug: string): string {
  return ensureDir(
    path.join(storageRoot, "output", sanitizeFilename(courseSlug), sanitizeFilename(moduleSlug), sanitizeFilename(lessonSlug))
  );
}

export function resourceStorageDir(courseSlug: string, moduleSlug: string, lessonSlug: string): string {
  return ensureDir(path.join(lessonOutputDir(courseSlug, moduleSlug, lessonSlug), "resources"));
}

export function brandAssetsDir(): string {
  return ensureDir(path.join(storageRoot, "brand-assets"));
}

export function newJobFilePath(): string {
  return path.join(jobsDir(), `job_${Date.now()}_${Math.random().toString(36).slice(2, 8)}.json`);
}
