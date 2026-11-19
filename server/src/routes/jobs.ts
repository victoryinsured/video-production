import { Router } from "express";
import { prisma } from "../db";
import { asyncHandler, notFound } from "./util";

export const jobsRouter = Router();

jobsRouter.get(
  "/course/:courseId",
  asyncHandler(async (req, res) => {
    const course = await prisma.course.findUnique({ where: { id: req.params.courseId } });
    if (!course) return notFound(res, "Course not found.");
    const jobSteps = await prisma.jobStep.findMany({
      where: { lesson: { module: { courseId: course.id } } },
      orderBy: { updatedAt: "desc" },
    });
    res.json({ jobSteps });
  })
);

jobsRouter.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const jobStep = await prisma.jobStep.findUnique({ where: { id: req.params.id } });
    if (!jobStep) return notFound(res, "Job step not found.");
    res.json({ jobStep });
  })
);
