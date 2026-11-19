import crypto from "node:crypto";
import { prisma } from "./db";

export type DiffStatus = "NEW" | "CHANGED" | "UNCHANGED" | "REMOVED";

export interface ParsedResourceJson {
  title: string;
  description: string;
  instructions: string;
  filename: string;
  resourceType: string;
}

export interface ParsedLessonJson {
  number: string;
  order: number | null;
  title: string;
  lessonType: string;
  description: string;
  videoDescription: string;
  scriptText: string;
  scriptHash: string;
  knowledgeChecks: string[];
  productionInstructions: string;
  tags: string[];
  resources: ParsedResourceJson[];
}

export interface ParsedModuleJson {
  number: string;
  title: string;
  description: string;
  lessons: ParsedLessonJson[];
}

export interface ParsedCourseJson {
  title: string;
  description: string;
  modules: ParsedModuleJson[];
}

export interface LessonDiffEntry {
  moduleNumber: string;
  lessonNumber: string;
  title: string;
  status: DiffStatus;
  existingLessonId?: string;
}

export interface ModuleDiffEntry {
  moduleNumber: string;
  title: string;
  status: DiffStatus;
}

export interface CourseDiff {
  courseExists: boolean;
  modules: ModuleDiffEntry[];
  lessons: LessonDiffEntry[];
}

function hashScript(text: string): string {
  return crypto.createHash("sha256").update(text, "utf-8").digest("hex");
}

/**
 * Compare a freshly-parsed curriculum against the existing Course (if any) with the same slug.
 * Lessons and modules are matched by number (module_number / lesson_number), not by title or
 * position — a re-upload that only rewords a title is a CHANGED lesson, not a NEW one followed
 * by a REMOVED one. A lesson is CHANGED only if its script text actually hashes differently;
 * metadata-only edits elsewhere do not force video regeneration (see the smart-regeneration
 * invalidation rules in queue/pipeline.ts, which key off this same distinction).
 */
export async function diffCurriculum(courseSlug: string, parsed: ParsedCourseJson): Promise<CourseDiff> {
  const existing = await prisma.course.findUnique({
    where: { slug: courseSlug },
    include: { modules: { include: { lessons: true } } },
  });

  if (!existing) {
    return {
      courseExists: false,
      modules: parsed.modules.map((m) => ({ moduleNumber: m.number, title: m.title, status: "NEW" })),
      lessons: parsed.modules.flatMap((m) =>
        m.lessons.map((l) => ({
          moduleNumber: m.number,
          lessonNumber: l.number,
          title: l.title,
          status: "NEW" as DiffStatus,
        }))
      ),
    };
  }

  const existingModuleByNumber = new Map(existing.modules.map((m) => [m.number, m]));
  const seenModuleNumbers = new Set<string>();
  const moduleDiffs: ModuleDiffEntry[] = [];
  const lessonDiffs: LessonDiffEntry[] = [];

  for (const parsedModule of parsed.modules) {
    seenModuleNumbers.add(parsedModule.number);
    const existingModule = existingModuleByNumber.get(parsedModule.number);
    moduleDiffs.push({
      moduleNumber: parsedModule.number,
      title: parsedModule.title,
      status: existingModule ? "UNCHANGED" : "NEW",
    });

    const existingLessonByNumber = new Map((existingModule?.lessons ?? []).map((l) => [l.number, l]));
    const seenLessonNumbers = new Set<string>();

    for (const parsedLesson of parsedModule.lessons) {
      seenLessonNumbers.add(parsedLesson.number);
      const existingLesson = existingLessonByNumber.get(parsedLesson.number);
      if (!existingLesson) {
        lessonDiffs.push({
          moduleNumber: parsedModule.number,
          lessonNumber: parsedLesson.number,
          title: parsedLesson.title,
          status: "NEW",
        });
        continue;
      }
      const newHash = parsedLesson.scriptHash || hashScript(parsedLesson.scriptText);
      const changed = newHash !== existingLesson.scriptHash;
      lessonDiffs.push({
        moduleNumber: parsedModule.number,
        lessonNumber: parsedLesson.number,
        title: parsedLesson.title,
        status: changed ? "CHANGED" : "UNCHANGED",
        existingLessonId: existingLesson.id,
      });
    }

    for (const [number, lesson] of existingLessonByNumber) {
      if (!seenLessonNumbers.has(number)) {
        lessonDiffs.push({
          moduleNumber: parsedModule.number,
          lessonNumber: number,
          title: lesson.title,
          status: "REMOVED",
          existingLessonId: lesson.id,
        });
      }
    }
  }

  for (const [number, module] of existingModuleByNumber) {
    if (!seenModuleNumbers.has(number)) {
      moduleDiffs.push({ moduleNumber: number, title: module.title, status: "REMOVED" });
      for (const lesson of module.lessons) {
        lessonDiffs.push({
          moduleNumber: number,
          lessonNumber: lesson.number,
          title: lesson.title,
          status: "REMOVED",
          existingLessonId: lesson.id,
        });
      }
    }
  }

  return { courseExists: true, modules: moduleDiffs, lessons: lessonDiffs };
}
