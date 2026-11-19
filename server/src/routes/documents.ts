import fs from "node:fs";
import path from "node:path";
import { Router } from "express";
import multer from "multer";
import { z } from "zod";
import { prisma } from "../db";
import { asyncHandler, badRequest, notFound } from "./util";
import { uploadsDir, sanitizeFilename } from "../paths";
import { runEngineStep } from "../engine";
import { diffCurriculum, type ParsedCourseJson } from "../curriculumDiff";
import { getDefaultBrandTemplate, getDefaultVoice } from "../brandVoice";
import { enqueueLessonPipeline } from "../queue/pipeline";
import { slugify } from "../slug";

export const documentsRouter = Router();

const DOCUMENT_SIZE_LIMIT = 100 * 1024 * 1024; // 100MB — generous for curriculum docs, not videos.
const ALLOWED_EXTENSIONS = new Set([".docx", ".pdf", ".txt", ".md", ".markdown"]);

const upload = multer({
  dest: "/tmp/victory-uploads",
  limits: { fileSize: DOCUMENT_SIZE_LIMIT },
  fileFilter: (_req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    if (!ALLOWED_EXTENSIONS.has(ext)) {
      cb(new Error(`Unsupported file type: ${ext}. Supported: ${[...ALLOWED_EXTENSIONS].join(", ")}`));
      return;
    }
    cb(null, true);
  },
});

documentsRouter.post(
  "/",
  upload.single("document"),
  asyncHandler(async (req, res) => {
    if (!req.file) return badRequest(res, "No document uploaded.");

    const safeName = sanitizeFilename(req.file.originalname);
    const storedPath = path.join(uploadsDir(), `${Date.now()}_${safeName}`);
    fs.copyFileSync(req.file.path, storedPath);
    fs.unlinkSync(req.file.path);

    const document = await prisma.document.create({
      data: { filename: safeName, storedPath, status: "uploaded" },
    });

    try {
      const result = await runEngineStep<{ course: ParsedCourseJson }>({
        step: "parse_document",
        documentPath: storedPath,
        fallbackTitle: safeName.replace(/\.[^.]+$/, ""),
      });
      const courseSlug = slugify(result.course.title);
      const diff = await diffCurriculum(courseSlug, result.course);

      const updated = await prisma.document.update({
        where: { id: document.id },
        data: { status: "parsed", parsedCourseJson: JSON.stringify(result.course), diffJson: JSON.stringify(diff) },
      });
      res.status(201).json({ document: updated, course: result.course, diff });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      await prisma.document.update({ where: { id: document.id }, data: { status: "failed", error: message } });
      res.status(422).json({ error: `Could not parse document: ${message}`, documentId: document.id });
    }
  })
);

documentsRouter.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const document = await prisma.document.findUnique({ where: { id: req.params.id } });
    if (!document) return notFound(res, "Document not found.");
    res.json({
      document,
      course: document.parsedCourseJson ? JSON.parse(document.parsedCourseJson) : null,
      diff: document.diffJson ? JSON.parse(document.diffJson) : null,
    });
  })
);

const approveSchema = z.object({
  startProduction: z.boolean().optional(),
});

/**
 * Approve a parsed document: create or update the Course/Module/Lesson/Resource hierarchy from
 * its parsed JSON. Matches modules/lessons by number (same rule curriculumDiff.ts uses) so a
 * re-upload updates existing records in place rather than creating duplicates. New courses pick
 * up whichever BrandTemplate/Voice is marked isDefault, so production works immediately without
 * the user visiting the Brand Editor or Voice Library first.
 */
documentsRouter.post(
  "/:id/approve",
  asyncHandler(async (req, res) => {
    const document = await prisma.document.findUnique({ where: { id: req.params.id } });
    if (!document) return notFound(res, "Document not found.");
    if (!document.parsedCourseJson) return badRequest(res, "Document has not been parsed successfully.");

    const parsed = approveSchema.safeParse(req.body ?? {});
    if (!parsed.success) return badRequest(res, parsed.error.message);

    const parsedCourse = JSON.parse(document.parsedCourseJson) as ParsedCourseJson;
    const courseSlug = slugify(parsedCourse.title);

    let course = await prisma.course.findUnique({ where: { slug: courseSlug } });
    if (!course) {
      const [defaultBrand, defaultVoice] = await Promise.all([getDefaultBrandTemplate(), getDefaultVoice()]);
      course = await prisma.course.create({
        data: {
          title: parsedCourse.title,
          slug: courseSlug,
          description: parsedCourse.description,
          brandTemplateId: defaultBrand?.id,
          voiceId: defaultVoice?.id,
        },
      });
    } else {
      course = await prisma.course.update({
        where: { id: course.id },
        data: { title: parsedCourse.title, description: parsedCourse.description },
      });
    }

    const createdLessonIds: string[] = [];

    for (const [moduleIndex, parsedModule] of parsedCourse.modules.entries()) {
      const moduleRow = await prisma.module.upsert({
        where: { courseId_number: { courseId: course.id, number: parsedModule.number } },
        update: { title: parsedModule.title, description: parsedModule.description, order: moduleIndex },
        create: {
          courseId: course.id,
          number: parsedModule.number,
          title: parsedModule.title,
          description: parsedModule.description,
          order: moduleIndex,
        },
      });

      for (const [lessonIndex, parsedLesson] of parsedModule.lessons.entries()) {
        const existingLesson = await prisma.lesson.findUnique({
          where: { moduleId_number: { moduleId: moduleRow.id, number: parsedLesson.number } },
        });
        const scriptChanged = existingLesson ? existingLesson.scriptHash !== parsedLesson.scriptHash : true;

        const lessonData = {
          title: parsedLesson.title,
          order: parsedLesson.order ?? lessonIndex,
          lessonType: parsedLesson.lessonType,
          description: parsedLesson.description,
          videoDescription: parsedLesson.videoDescription,
          scriptText: parsedLesson.scriptText,
          scriptHash: parsedLesson.scriptHash,
          knowledgeChecks: JSON.stringify(parsedLesson.knowledgeChecks),
          productionInstructions: parsedLesson.productionInstructions,
          tags: JSON.stringify(parsedLesson.tags),
        };

        const lesson = existingLesson
          ? await prisma.lesson.update({ where: { id: existingLesson.id }, data: lessonData })
          : await prisma.lesson.create({
              data: { moduleId: moduleRow.id, number: parsedLesson.number, ...lessonData },
            });

        for (const parsedResource of parsedLesson.resources) {
          const safeFilename = parsedResource.filename ? sanitizeFilename(parsedResource.filename) : "";
          const existingResource = await prisma.resource.findFirst({
            where: { lessonId: lesson.id, title: parsedResource.title },
          });
          const resourceData = {
            description: parsedResource.description,
            instructions: parsedResource.instructions,
            filename: safeFilename,
            resourceType: parsedResource.resourceType,
          };
          if (existingResource) {
            await prisma.resource.update({ where: { id: existingResource.id }, data: resourceData });
          } else {
            await prisma.resource.create({ data: { lessonId: lesson.id, title: parsedResource.title, ...resourceData } });
          }
        }

        if (!existingLesson || scriptChanged) {
          createdLessonIds.push(lesson.id);
        }
      }
    }

    await prisma.document.update({ where: { id: document.id }, data: { status: "approved", courseId: course.id } });

    if (parsed.data.startProduction) {
      const allLessons = await prisma.lesson.findMany({ where: { module: { courseId: course.id } } });
      for (const lesson of allLessons) {
        await enqueueLessonPipeline(lesson.id);
      }
      await prisma.course.update({ where: { id: course.id }, data: { status: "producing" } });
    }

    res.json({ course, newOrChangedLessonIds: createdLessonIds });
  })
);
