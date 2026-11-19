import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { Router } from "express";
import multer from "multer";
import { z } from "zod";
import { prisma } from "../db";
import { asyncHandler, badRequest, notFound } from "./util";
import { resourceStorageDir, sanitizeFilename, lessonOutputDir } from "../paths";
import {
  INVALIDATION_TRIGGERS,
  invalidateLessonSteps,
  invalidateResourceSteps,
  retryFailedSteps,
  LESSON_STEPS,
} from "../queue/pipeline";

export const lessonsRouter = Router();

const UPLOAD_SIZE_LIMIT = 500 * 1024 * 1024; // 500MB — large enough for a finished lesson video.
const upload = multer({ dest: "/tmp/victory-uploads", limits: { fileSize: UPLOAD_SIZE_LIMIT } });

async function lessonContext(id: string) {
  return prisma.lesson.findUnique({
    where: { id },
    include: { module: { include: { course: true } }, resources: true },
  });
}

lessonsRouter.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const lesson = await lessonContext(req.params.id);
    if (!lesson) return notFound(res, "Lesson not found.");
    const jobSteps = await prisma.jobStep.findMany({ where: { lessonId: lesson.id } });
    res.json({ lesson, jobSteps });
  })
);

const patchSchema = z.object({
  title: z.string().min(1).optional(),
  description: z.string().optional(),
  videoDescription: z.string().optional(),
  scriptText: z.string().optional(),
  knowledgeChecks: z.array(z.string()).optional(),
  productionInstructions: z.string().optional(),
  tags: z.array(z.string()).optional(),
  brandTemplateId: z.string().nullable().optional(),
  voiceId: z.string().nullable().optional(),
  order: z.number().int().optional(),
});

lessonsRouter.patch(
  "/:id",
  asyncHandler(async (req, res) => {
    const existing = await prisma.lesson.findUnique({ where: { id: req.params.id } });
    if (!existing) return notFound(res, "Lesson not found.");
    const parsed = patchSchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);

    const data: Record<string, unknown> = { ...parsed.data };
    if (parsed.data.knowledgeChecks) data.knowledgeChecks = JSON.stringify(parsed.data.knowledgeChecks);
    if (parsed.data.tags) data.tags = JSON.stringify(parsed.data.tags);

    const scriptChanged = parsed.data.scriptText !== undefined && parsed.data.scriptText !== existing.scriptText;
    if (scriptChanged) {
      data.scriptHash = crypto.createHash("sha256").update(parsed.data.scriptText ?? "", "utf-8").digest("hex");
    }
    const brandChanged = parsed.data.brandTemplateId !== undefined && parsed.data.brandTemplateId !== existing.brandTemplateId;
    const voiceChanged = parsed.data.voiceId !== undefined && parsed.data.voiceId !== existing.voiceId;
    const videoDescriptionChanged =
      parsed.data.videoDescription !== undefined && parsed.data.videoDescription !== existing.videoDescription;

    const lesson = await prisma.lesson.update({ where: { id: req.params.id }, data });

    const triggers: Array<keyof typeof INVALIDATION_TRIGGERS> = [];
    if (scriptChanged) triggers.push("scriptChanged");
    if (brandChanged) triggers.push("brandChanged");
    if (voiceChanged) triggers.push("voiceChanged");
    if (videoDescriptionChanged) triggers.push("videoDescriptionChanged");
    if (triggers.length > 0) {
      const roots = triggers.flatMap((t) => INVALIDATION_TRIGGERS[t]);
      await invalidateLessonSteps(lesson.id, roots);
    }

    res.json({ lesson });
  })
);

lessonsRouter.post(
  "/:id/retry",
  asyncHandler(async (req, res) => {
    const lesson = await prisma.lesson.findUnique({ where: { id: req.params.id } });
    if (!lesson) return notFound(res, "Lesson not found.");
    const count = await retryFailedSteps(lesson.id);
    res.json({ ok: true, retried: count });
  })
);

const regenerateSchema = z.object({ step: z.enum(LESSON_STEPS) });

lessonsRouter.post(
  "/:id/regenerate-step",
  asyncHandler(async (req, res) => {
    const lesson = await prisma.lesson.findUnique({ where: { id: req.params.id } });
    if (!lesson) return notFound(res, "Lesson not found.");
    const parsed = regenerateSchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);
    const invalidated = await invalidateLessonSteps(lesson.id, [parsed.data.step]);
    res.json({ ok: true, invalidated });
  })
);

/** Manual override: upload a replacement video for this lesson, skipping render entirely.
 * Downstream upload/publish steps are invalidated so the new file actually gets re-distributed. */
lessonsRouter.post(
  "/:id/video",
  upload.single("video"),
  asyncHandler(async (req, res) => {
    const lesson = await lessonContext(req.params.id);
    if (!lesson) return notFound(res, "Lesson not found.");
    if (!req.file) return badRequest(res, "No video file uploaded.");

    const destDir = lessonOutputDir(lesson.module.course.slug, lesson.module.number, lesson.number);
    const destPath = path.join(destDir, "video.mp4");
    fs.copyFileSync(req.file.path, destPath);
    fs.unlinkSync(req.file.path);

    await prisma.lesson.update({ where: { id: lesson.id }, data: { videoPath: destPath } });
    await prisma.jobStep.upsert({
      where: { lessonId_step_resourceId: { lessonId: lesson.id, step: "video", resourceId: "" } },
      update: { status: "complete", resultJson: JSON.stringify({ videoPath: destPath, manual: true }), error: null },
      create: { lessonId: lesson.id, step: "video", resourceId: "", status: "complete", resultJson: JSON.stringify({ videoPath: destPath, manual: true }) },
    });
    const invalidated = await invalidateLessonSteps(lesson.id, INVALIDATION_TRIGGERS.manualVideoReplacement);
    res.json({ ok: true, videoPath: destPath, invalidated });
  })
);

/** Manual override: paste an already-known Bunny video ID instead of uploading through this
 * app (e.g. the video was uploaded directly in the Bunny dashboard). */
const bunnyIdSchema = z.object({ bunnyVideoId: z.string().min(1) });
lessonsRouter.post(
  "/:id/bunny-id",
  asyncHandler(async (req, res) => {
    const lesson = await prisma.lesson.findUnique({ where: { id: req.params.id } });
    if (!lesson) return notFound(res, "Lesson not found.");
    const parsed = bunnyIdSchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);
    await prisma.lesson.update({ where: { id: lesson.id }, data: { bunnyVideoId: parsed.data.bunnyVideoId } });
    await prisma.jobStep.upsert({
      where: { lessonId_step_resourceId: { lessonId: lesson.id, step: "bunny_upload", resourceId: "" } },
      update: { status: "complete", resultJson: JSON.stringify({ videoId: parsed.data.bunnyVideoId, manual: true }), error: null },
      create: {
        lessonId: lesson.id,
        step: "bunny_upload",
        resourceId: "",
        status: "complete",
        resultJson: JSON.stringify({ videoId: parsed.data.bunnyVideoId, manual: true }),
      },
    });
    const invalidated = await invalidateLessonSteps(lesson.id, ["moodle_publish"]);
    res.json({ ok: true, invalidated });
  })
);

// --- Resources -----------------------------------------------------------------------------

const resourceSchema = z.object({
  title: z.string().min(1),
  description: z.string().optional(),
  instructions: z.string().optional(),
  resourceType: z.enum(["pdf", "doc", "link", "file"]).optional(),
  linkUrl: z.string().url().optional(),
});

lessonsRouter.post(
  "/:id/resources",
  asyncHandler(async (req, res) => {
    const lesson = await prisma.lesson.findUnique({ where: { id: req.params.id } });
    if (!lesson) return notFound(res, "Lesson not found.");
    const parsed = resourceSchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);
    const resource = await prisma.resource.create({
      data: {
        lessonId: lesson.id,
        title: parsed.data.title,
        description: parsed.data.description ?? "",
        instructions: parsed.data.instructions ?? "",
        resourceType: parsed.data.resourceType ?? "file",
        linkUrl: parsed.data.linkUrl,
      },
    });
    res.status(201).json({ resource });
  })
);

const resourcePatchSchema = resourceSchema.partial();

lessonsRouter.patch(
  "/resources/:resourceId",
  asyncHandler(async (req, res) => {
    const existing = await prisma.resource.findUnique({ where: { id: req.params.resourceId } });
    if (!existing) return notFound(res, "Resource not found.");
    const parsed = resourcePatchSchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);
    const resource = await prisma.resource.update({ where: { id: req.params.resourceId }, data: parsed.data });
    res.json({ resource });
  })
);

lessonsRouter.post(
  "/resources/:resourceId/upload",
  upload.single("file"),
  asyncHandler(async (req, res) => {
    const resource = await prisma.resource.findUnique({
      where: { id: req.params.resourceId },
      include: { lesson: { include: { module: { include: { course: true } } } } },
    });
    if (!resource) return notFound(res, "Resource not found.");
    if (!req.file) return badRequest(res, "No file uploaded.");

    const safeName = sanitizeFilename(req.file.originalname);
    const destDir = resourceStorageDir(resource.lesson.module.course.slug, resource.lesson.module.number, resource.lesson.number);
    const destPath = path.join(destDir, safeName);
    fs.copyFileSync(req.file.path, destPath);
    fs.unlinkSync(req.file.path);

    const updated = await prisma.resource.update({
      where: { id: resource.id },
      data: { storagePath: destPath, filename: safeName, status: "not_started" },
    });
    const invalidated = await invalidateResourceSteps(resource.lessonId, resource.id, ["resource_upload"]);
    res.json({ resource: updated, invalidated });
  })
);

lessonsRouter.delete(
  "/resources/:resourceId",
  asyncHandler(async (req, res) => {
    const existing = await prisma.resource.findUnique({ where: { id: req.params.resourceId } });
    if (!existing) return notFound(res, "Resource not found.");
    await prisma.jobStep.deleteMany({ where: { resourceId: existing.id } });
    await prisma.resource.delete({ where: { id: req.params.resourceId } });
    res.json({ ok: true });
  })
);
