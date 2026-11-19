import { Router } from "express";
import { prisma } from "../db";
import { asyncHandler, notFound } from "./util";

export const dashboardRouter = Router();

dashboardRouter.get(
  "/",
  asyncHandler(async (_req, res) => {
    const courses = await prisma.course.findMany({
      include: { modules: { include: { lessons: true } } },
      orderBy: { updatedAt: "desc" },
    });

    const summaries = courses.map((course) => {
      const lessons = course.modules.flatMap((m) => m.lessons);
      const byStatus = lessons.reduce<Record<string, number>>((acc, lesson) => {
        acc[lesson.status] = (acc[lesson.status] ?? 0) + 1;
        return acc;
      }, {});
      return {
        id: course.id,
        title: course.title,
        slug: course.slug,
        status: course.status,
        moduleCount: course.modules.length,
        lessonCount: lessons.length,
        lessonsByStatus: byStatus,
        updatedAt: course.updatedAt,
      };
    });

    const failedSteps = await prisma.jobStep.count({ where: { status: "failed" } });
    const runningSteps = await prisma.jobStep.count({ where: { status: "running" } });
    const pendingSteps = await prisma.jobStep.count({ where: { status: "pending" } });

    res.json({ courses: summaries, failedSteps, runningSteps, pendingSteps });
  })
);

dashboardRouter.get(
  "/course/:courseId",
  asyncHandler(async (req, res) => {
    const course = await prisma.course.findUnique({
      where: { id: req.params.courseId },
      include: {
        modules: {
          orderBy: { order: "asc" },
          include: { lessons: { orderBy: { order: "asc" }, include: { resources: true, jobSteps: true } } },
        },
      },
    });
    if (!course) return notFound(res, "Course not found.");
    res.json({ course });
  })
);
