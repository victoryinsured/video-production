import type { BrandTemplate } from "@prisma/client";
import { prisma } from "./db";

/** Convert a stored BrandTemplate row into the plain JSON dict shape victory_engine.brand
 * expects (brand_from_dict on the Python side). Columns that are JSON-encoded strings in SQLite
 * (colors/fonts/cover) are parsed back into objects here, once, at the boundary. */
export function brandTemplateToDict(brand: BrandTemplate | null): Record<string, unknown> | null {
  if (!brand) return null;
  return {
    name: brand.name,
    colors: JSON.parse(brand.colors),
    fonts: JSON.parse(brand.fonts),
    cover: JSON.parse(brand.cover),
    assets: {
      logo_path: brand.logoPath,
      intro_video_path: brand.introVideoPath,
      outro_video_path: brand.outroVideoPath,
    },
    video: { width: brand.width, height: brand.height, fps: brand.fps, audio_bitrate: brand.audioBitrate },
    captions: {
      enabled: brand.captionsEnabled,
      font_size: brand.captionFontSize,
      position: brand.captionPosition,
    },
    text_scale: brand.textScale,
  };
}

/** Unset `isDefault` on every other row before setting it on `id` — isDefault is a mutually
 * exclusive flag, not a multi-select. Call inside the same transaction as the update that sets
 * the new default. */
export async function clearOtherDefaultBrandTemplates(keepId: string): Promise<void> {
  await prisma.brandTemplate.updateMany({
    where: { id: { not: keepId }, isDefault: true },
    data: { isDefault: false },
  });
}

export async function clearOtherDefaultVoices(keepId: string): Promise<void> {
  await prisma.voice.updateMany({
    where: { id: { not: keepId }, isDefault: true },
    data: { isDefault: false },
  });
}

export async function getDefaultBrandTemplate() {
  return prisma.brandTemplate.findFirst({ where: { isDefault: true } });
}

export async function getDefaultVoice() {
  return prisma.voice.findFirst({ where: { isDefault: true } });
}

/** Resolve the brand/voice a lesson should actually render with: lesson override, else the
 * course's saved default, else whichever template/voice is marked isDefault globally. */
export async function resolveBrandForLesson(lessonId: string): Promise<BrandTemplate | null> {
  const lesson = await prisma.lesson.findUniqueOrThrow({
    where: { id: lessonId },
    include: { module: { include: { course: { include: { brandTemplate: true } } } } },
  });
  if (lesson.brandTemplateId) {
    const override = await prisma.brandTemplate.findUnique({ where: { id: lesson.brandTemplateId } });
    if (override) return override;
  }
  if (lesson.module.course.brandTemplate) return lesson.module.course.brandTemplate;
  return getDefaultBrandTemplate();
}

export async function resolveVoiceForLesson(lessonId: string) {
  const lesson = await prisma.lesson.findUniqueOrThrow({
    where: { id: lessonId },
    include: { module: { include: { course: { include: { voice: true } } } } },
  });
  if (lesson.voiceId) {
    const override = await prisma.voice.findUnique({ where: { id: lesson.voiceId } });
    if (override) return override;
  }
  if (lesson.module.course.voice) return lesson.module.course.voice;
  return getDefaultVoice();
}
