import { prisma } from "../db";

/**
 * The step dependency graph. A lesson's steps form a DAG; a resource's steps form a second,
 * independent two-step chain. This is the single source of truth smart regeneration and retry
 * both key off: invalidating a step invalidates everything downstream of it (transitively), so
 * e.g. an edited script invalidates slides -> video -> aws_upload/bunny_upload -> moodle_publish
 * without touching narration if the voice didn't change, while a brand-only edit invalidates
 * slides/video/editable_assets without re-synthesizing narration at all.
 */
export const LESSON_STEPS = [
  "slides",
  "narration",
  "video",
  "editable_assets",
  "aws_upload",
  "bunny_upload",
  "moodle_publish",
] as const;
export type LessonStep = (typeof LESSON_STEPS)[number];

export const RESOURCE_STEPS = ["resource_upload", "resource_moodle"] as const;
export type ResourceStep = (typeof RESOURCE_STEPS)[number];

const LESSON_DEPENDENTS: Record<LessonStep, LessonStep[]> = {
  slides: ["video", "editable_assets"],
  narration: ["video"],
  video: ["aws_upload", "bunny_upload"],
  editable_assets: [],
  aws_upload: ["moodle_publish"],
  bunny_upload: ["moodle_publish"],
  moodle_publish: [],
};

const RESOURCE_DEPENDENTS: Record<ResourceStep, ResourceStep[]> = {
  resource_upload: ["resource_moodle"],
  resource_moodle: [],
};

/** All steps downstream of `step`, transitively, not including `step` itself. */
export function downstreamOfLessonStep(step: LessonStep): LessonStep[] {
  const seen = new Set<LessonStep>();
  const stack = [...LESSON_DEPENDENTS[step]];
  while (stack.length) {
    const next = stack.pop()!;
    if (seen.has(next)) continue;
    seen.add(next);
    stack.push(...LESSON_DEPENDENTS[next]);
  }
  return [...seen];
}

export function downstreamOfResourceStep(step: ResourceStep): ResourceStep[] {
  const seen = new Set<ResourceStep>();
  const stack = [...RESOURCE_DEPENDENTS[step]];
  while (stack.length) {
    const next = stack.pop()!;
    if (seen.has(next)) continue;
    seen.add(next);
    stack.push(...RESOURCE_DEPENDENTS[next]);
  }
  return [...seen];
}

/** What a given kind of edit should invalidate, expressed as the root steps to invalidate
 * (their downstream steps are pulled in automatically by invalidateLessonSteps). */
export const INVALIDATION_TRIGGERS = {
  scriptChanged: ["slides", "narration"] as LessonStep[],
  brandChanged: ["slides"] as LessonStep[],
  voiceChanged: ["narration"] as LessonStep[],
  videoDescriptionChanged: [] as LessonStep[], // affects only Moodle description text
  moodleDestinationChanged: ["moodle_publish"] as LessonStep[],
  manualVideoReplacement: ["aws_upload", "bunny_upload"] as LessonStep[],
} as const;

async function ensureJobStep(lessonId: string, step: string, resourceId: string) {
  return prisma.jobStep.upsert({
    where: { lessonId_step_resourceId: { lessonId, step, resourceId } },
    update: {},
    create: { lessonId, step, resourceId, status: "pending" },
  });
}

/** Mark `rootSteps` and everything downstream of them as pending again, creating JobStep rows
 * that don't exist yet. Steps not reachable from `rootSteps` are left exactly as they are —
 * this is the whole point: a brand-only edit never touches narration's completed state. */
export async function invalidateLessonSteps(lessonId: string, rootSteps: LessonStep[]): Promise<LessonStep[]> {
  if (rootSteps.length === 0) return [];
  const all = new Set<LessonStep>(rootSteps);
  for (const step of rootSteps) {
    for (const downstream of downstreamOfLessonStep(step)) all.add(downstream);
  }
  const steps = [...all];
  await prisma.$transaction(
    steps.map((step) =>
      prisma.jobStep.upsert({
        where: { lessonId_step_resourceId: { lessonId, step, resourceId: "" } },
        update: { status: "pending", error: null, resultJson: null },
        create: { lessonId, step, resourceId: "", status: "pending" },
      })
    )
  );
  await prisma.lesson.update({ where: { id: lessonId }, data: { status: "not_started" } });
  return steps;
}

export async function invalidateResourceSteps(
  lessonId: string,
  resourceId: string,
  rootSteps: ResourceStep[]
): Promise<ResourceStep[]> {
  if (rootSteps.length === 0) return [];
  const all = new Set<ResourceStep>(rootSteps);
  for (const step of rootSteps) {
    for (const downstream of downstreamOfResourceStep(step)) all.add(downstream);
  }
  const steps = [...all];
  await prisma.$transaction(
    steps.map((step) =>
      prisma.jobStep.upsert({
        where: { lessonId_step_resourceId: { lessonId, step, resourceId } },
        update: { status: "pending", error: null, resultJson: null },
        create: { lessonId, step, resourceId, status: "pending" },
      })
    )
  );
  return steps;
}

/** Enqueue every pipeline step for a lesson (and its resources) from scratch — used for
 * "Generate & Publish Entire Course" and for a brand-new lesson. Steps that already have a
 * completed JobStep row are left untouched (smart regeneration: a re-run never redoes
 * completed work unless something upstream invalidated it first). */
export async function enqueueLessonPipeline(lessonId: string): Promise<void> {
  for (const step of LESSON_STEPS) {
    await ensureJobStep(lessonId, step, "");
  }
  const resources = await prisma.resource.findMany({ where: { lessonId } });
  for (const resource of resources) {
    for (const step of RESOURCE_STEPS) {
      await ensureJobStep(lessonId, step, resource.id);
    }
  }
}

/** Reset every failed step on a lesson back to pending so the worker picks it up again, without
 * touching steps that already completed successfully. */
export async function retryFailedSteps(lessonId: string): Promise<number> {
  const result = await prisma.jobStep.updateMany({
    where: { lessonId, status: "failed" },
    data: { status: "pending", error: null },
  });
  return result.count;
}

export async function nextPendingStepsForLesson(lessonId: string) {
  return prisma.jobStep.findMany({ where: { lessonId, status: "pending" } });
}

export function stepIsLessonLevel(step: string): step is LessonStep {
  return (LESSON_STEPS as readonly string[]).includes(step);
}

export function stepIsResourceLevel(step: string): step is ResourceStep {
  return (RESOURCE_STEPS as readonly string[]).includes(step);
}

/** A step is runnable once every step it directly depends on (not transitively — direct
 * predecessors only) has completed. Used by the worker to decide what to pick up next. */
const LESSON_PREDECESSORS: Record<LessonStep, LessonStep[]> = {
  slides: [],
  narration: [],
  video: ["slides", "narration"],
  editable_assets: ["slides"],
  aws_upload: ["video"],
  bunny_upload: ["video"],
  moodle_publish: ["aws_upload", "bunny_upload"],
};

const RESOURCE_PREDECESSORS: Record<ResourceStep, ResourceStep[]> = {
  resource_upload: [],
  resource_moodle: ["resource_upload"],
};

export async function isStepRunnable(lessonId: string, step: string, resourceId: string): Promise<boolean> {
  const predecessors = resourceId
    ? RESOURCE_PREDECESSORS[step as ResourceStep] ?? []
    : LESSON_PREDECESSORS[step as LessonStep] ?? [];
  if (predecessors.length === 0) return true;
  const rows = await prisma.jobStep.findMany({
    where: { lessonId, resourceId, step: { in: predecessors } },
    select: { status: true },
  });
  if (rows.length < predecessors.length) return false;
  return rows.every((r) => r.status === "complete");
}
