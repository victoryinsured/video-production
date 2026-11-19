import { Router } from "express";
import { z } from "zod";
import { prisma } from "../db";
import { asyncHandler, badRequest, notFound } from "./util";
import { clearOtherDefaultVoices } from "../brandVoice";
import { listVoices as listElevenLabsVoices } from "../integrations/elevenlabs";

export const voicesRouter = Router();

voicesRouter.get(
  "/",
  asyncHandler(async (_req, res) => {
    const voices = await prisma.voice.findMany({ orderBy: { createdAt: "asc" } });
    res.json({ voices });
  })
);

/** List the raw voices available in the configured ElevenLabs account, so the Voice Library UI
 * can offer a picker instead of requiring the user to copy/paste a voice ID by hand. */
voicesRouter.get(
  "/available",
  asyncHandler(async (_req, res) => {
    const voices = await listElevenLabsVoices();
    res.json({ voices });
  })
);

const createSchema = z.object({
  name: z.string().min(1),
  elevenLabsVoiceId: z.string().min(1),
  isDefault: z.boolean().optional(),
});

voicesRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    const parsed = createSchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);
    const voice = await prisma.voice.create({ data: { ...parsed.data, isDefault: Boolean(parsed.data.isDefault) } });
    if (parsed.data.isDefault) await clearOtherDefaultVoices(voice.id);
    res.status(201).json({ voice });
  })
);

const patchSchema = createSchema.partial();

voicesRouter.patch(
  "/:id",
  asyncHandler(async (req, res) => {
    const existing = await prisma.voice.findUnique({ where: { id: req.params.id } });
    if (!existing) return notFound(res, "Voice not found.");
    const parsed = patchSchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);
    const voice = await prisma.voice.update({ where: { id: req.params.id }, data: parsed.data });
    if (parsed.data.isDefault) await clearOtherDefaultVoices(voice.id);
    res.json({ voice });
  })
);

voicesRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const existing = await prisma.voice.findUnique({ where: { id: req.params.id } });
    if (!existing) return notFound(res, "Voice not found.");
    await prisma.voice.delete({ where: { id: req.params.id } });
    res.json({ ok: true });
  })
);
