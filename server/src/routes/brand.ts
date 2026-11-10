import fs from "node:fs";
import path from "node:path";
import { Router } from "express";
import multer from "multer";
import { z } from "zod";
import { prisma } from "../db";
import { asyncHandler, badRequest, notFound } from "./util";
import { brandAssetsDir, sanitizeFilename } from "../paths";
import { clearOtherDefaultBrandTemplates } from "../brandVoice";

export const brandRouter = Router();

const ASSET_SIZE_LIMIT = 500 * 1024 * 1024; // intro/outro clips can be sizable video files.
const upload = multer({ dest: "/tmp/victory-uploads", limits: { fileSize: ASSET_SIZE_LIMIT } });

brandRouter.get(
  "/",
  asyncHandler(async (_req, res) => {
    const templates = await prisma.brandTemplate.findMany({ orderBy: { createdAt: "asc" } });
    res.json({ templates });
  })
);

const createSchema = z.object({
  name: z.string().min(1),
  colors: z.record(z.any()).default({}),
  fonts: z.record(z.any()).default({}),
  cover: z.object({ kicker: z.string().optional(), bullets: z.array(z.string()).optional() }).default({}),
  width: z.number().int().optional(),
  height: z.number().int().optional(),
  fps: z.number().int().optional(),
  audioBitrate: z.string().optional(),
  captionsEnabled: z.boolean().optional(),
  captionFontSize: z.number().int().optional(),
  captionPosition: z.enum(["top", "bottom"]).optional(),
  textScale: z.number().optional(),
  isDefault: z.boolean().optional(),
});

brandRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    const parsed = createSchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);
    const { colors, fonts, cover, isDefault, ...rest } = parsed.data;

    const template = await prisma.brandTemplate.create({
      data: {
        ...rest,
        colors: JSON.stringify(colors),
        fonts: JSON.stringify(fonts),
        cover: JSON.stringify(cover),
        isDefault: Boolean(isDefault),
      },
    });
    if (isDefault) await clearOtherDefaultBrandTemplates(template.id);
    res.status(201).json({ template });
  })
);

const patchSchema = createSchema.partial();

brandRouter.patch(
  "/:id",
  asyncHandler(async (req, res) => {
    const existing = await prisma.brandTemplate.findUnique({ where: { id: req.params.id } });
    if (!existing) return notFound(res, "Brand template not found.");
    const parsed = patchSchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);
    const { colors, fonts, cover, isDefault, ...rest } = parsed.data;

    const data: Record<string, unknown> = { ...rest };
    if (colors !== undefined) data.colors = JSON.stringify(colors);
    if (fonts !== undefined) data.fonts = JSON.stringify(fonts);
    if (cover !== undefined) data.cover = JSON.stringify(cover);
    if (isDefault !== undefined) data.isDefault = isDefault;

    const template = await prisma.brandTemplate.update({ where: { id: req.params.id }, data });
    if (isDefault) await clearOtherDefaultBrandTemplates(template.id);
    res.json({ template });
  })
);

brandRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const existing = await prisma.brandTemplate.findUnique({ where: { id: req.params.id } });
    if (!existing) return notFound(res, "Brand template not found.");
    await prisma.brandTemplate.delete({ where: { id: req.params.id } });
    res.json({ ok: true });
  })
);

const ASSET_FIELDS = ["logo", "intro", "outro"] as const;
type AssetField = (typeof ASSET_FIELDS)[number];
const ASSET_COLUMN: Record<AssetField, "logoPath" | "introVideoPath" | "outroVideoPath"> = {
  logo: "logoPath",
  intro: "introVideoPath",
  outro: "outroVideoPath",
};

brandRouter.post(
  "/:id/assets/:field",
  upload.single("file"),
  asyncHandler(async (req, res) => {
    const field = req.params.field as AssetField;
    if (!ASSET_FIELDS.includes(field)) return badRequest(res, `Unknown asset field: ${req.params.field}`);
    const existing = await prisma.brandTemplate.findUnique({ where: { id: req.params.id } });
    if (!existing) return notFound(res, "Brand template not found.");
    if (!req.file) return badRequest(res, "No file uploaded.");

    const safeName = sanitizeFilename(`${existing.id}_${field}_${req.file.originalname}`);
    const destPath = path.join(brandAssetsDir(), safeName);
    fs.copyFileSync(req.file.path, destPath);
    fs.unlinkSync(req.file.path);

    const template = await prisma.brandTemplate.update({
      where: { id: req.params.id },
      data: { [ASSET_COLUMN[field]]: destPath },
    });
    res.json({ template });
  })
);
