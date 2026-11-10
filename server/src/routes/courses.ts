import { Router } from "express";
import { z } from "zod";
import { prisma } from "../db";
import { asyncHandler, badRequest, notFound } from "./util";
import { enqueueLessonPipeline, invalidateLessonSteps, INVALIDATION_TRIGGERS } from "../queue/pipeline";

export const coursesRouter = Router();

coursesRouter.get(
  "/",
  asyncHandler(async (_req, res) => {
    const courses = await prisma.course.findMany({
      orderBy: { updatedAt: "desc" },
      include: { modules: { include: { lessons: true } } },
    });
    res.json({ courses });
  })
);

coursesRouter.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const course = await prisma.course.findUnique({
      where: { id: req.params.id },
      include: {
        modules: { orderBy: { order: "asc" }, include: { lessons: { orderBy: { order: "asc" }, include: { resources: true } } } },
        brandTemplate: true,
        voice: true,
      },
    });
    if (!course) return notFound(res, "Course not found.");
    res.json({ course });
  })
);

const courseDefaultsSchema = z.object({
  brandTemplateId: z.string().nullable().optional(),
  voiceId: z.string().nullable().optional(),
  awsBucket: z.string().nullable().optional(),
  awsRegion: z.string().nullable().optional(),
  awsKeyPrefix: z.string().nullable().optional(),
  bunnyLibraryId: z.string().nullable().optional(),
  bunnyCollectionId: z.string().nullable().optional(),
  moodleCourseId: z.number().int().nullable().optional(),
  title: z.string().min(1).optional(),
  description: z.string().optional(),
});

coursesRouter.patch(
  "/:id",
  asyncHandler(async (req, res) => {
    const existing = await prisma.course.findUnique({ where: { id: req.params.id } });
    if (!existing) return notFound(res, "Course not found.");

    const parsed = courseDefaultsSchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);

    const changedMoodleDestination =
      parsed.data.moodleCourseId !== undefined && parsed.data.moodleCourseId !== existing.moodleCourseId;
    const changedBrand =
      parsed.data.brandTemplateId !== undefined && parsed.data.brandTemplateId !== existing.brandTemplateId;
    const changedVoice = parsed.data.voiceId !== undefined && parsed.data.voiceId !== existing.voiceId;

    const course = await prisma.course.update({ where: { id: req.params.id }, data: parsed.data });

    if (changedMoodleDestination || changedBrand || changedVoice) {
      const lessons = await prisma.lesson.findMany({ where: { module: { courseId: course.id } } });
      for (const lesson of lessons) {
        const triggers: Array<keyof typeof INVALIDATION_TRIGGERS> = [];
        if (changedMoodleDestination) triggers.push("moodleDestinationChanged");
        if (changedBrand) triggers.push("brandChanged");
        if (changedVoice) triggers.push("voiceChanged");
        const roots = triggers.flatMap((t) => INVALIDATION_TRIGGERS[t]);
        await invalidateLessonSteps(lesson.id, roots);
      }
    }

    res.json({ course });
  })
);

coursesRouter.post(
  "/:id/generate",
  asyncHandler(async (req, res) => {
    const course = await prisma.course.findUnique({
      where: { id: req.params.id },
      include: { modules: { include: { lessons: true } } },
    });
    if (!course) return notFound(res, "Course not found.");

    let enqueued = 0;
    for (const module of course.modules) {
      for (const lesson of module.lessons) {
        await enqueueLessonPipeline(lesson.id);
        enqueued += 1;
      }
    }
    await prisma.course.update({ where: { id: course.id }, data: { status: "producing" } });
    res.json({ ok: true, lessonsEnqueued: enqueued });
  })
);

coursesRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const existing = await prisma.course.findUnique({ where: { id: req.params.id } });
    if (!existing) return notFound(res, "Course not found.");
    await prisma.course.delete({ where: { id: req.params.id } });
    res.json({ ok: true });
  })
);
