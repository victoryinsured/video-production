import { Router } from "express";
import { z } from "zod";
import { prisma } from "../db";
import { asyncHandler, badRequest, notFound } from "./util";

export const modulesRouter = Router();

const patchSchema = z.object({
  title: z.string().min(1).optional(),
  description: z.string().optional(),
  order: z.number().int().optional(),
});

modulesRouter.patch(
  "/:id",
  asyncHandler(async (req, res) => {
    const existing = await prisma.module.findUnique({ where: { id: req.params.id } });
    if (!existing) return notFound(res, "Module not found.");
    const parsed = patchSchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);
    const moduleRow = await prisma.module.update({ where: { id: req.params.id }, data: parsed.data });
    res.json({ module: moduleRow });
  })
);

modulesRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const existing = await prisma.module.findUnique({ where: { id: req.params.id } });
    if (!existing) return notFound(res, "Module not found.");
    await prisma.module.delete({ where: { id: req.params.id } });
    res.json({ ok: true });
  })
);
