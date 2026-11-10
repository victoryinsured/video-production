import path from "node:path";
import type { JobStep } from "@prisma/client";
import { prisma } from "../db";
import { runEngineStep } from "../engine";
import { resolveBrandForLesson, resolveVoiceForLesson, brandTemplateToDict } from "../brandVoice";
import { lessonOutputDir, resourceStorageDir, sanitizeFilename } from "../paths";
import { uploadFile as s3UploadFile, UploadResult } from "../integrations/aws";
import { uploadVideo as bunnyUploadVideo } from "../integrations/bunny";
import { createOrUpdateSection, publishUrlActivity } from "../integrations/moodle";
import { env } from "../env";

async function lessonWithContext(lessonId: string) {
  return prisma.lesson.findUniqueOrThrow({
    where: { id: lessonId },
    include: {
      module: { include: { course: true } },
      resources: true,
    },
  });
}

function lessonToEngineDict(lesson: Awaited<ReturnType<typeof lessonWithContext>>) {
  return {
    number: lesson.number,
    order: lesson.order,
    title: lesson.title,
    lessonType: lesson.lessonType,
    description: lesson.description,
    videoDescription: lesson.videoDescription,
    scriptText: lesson.scriptText,
    knowledgeChecks: JSON.parse(lesson.knowledgeChecks || "[]"),
    productionInstructions: lesson.productionInstructions,
    tags: JSON.parse(lesson.tags || "[]"),
    resources: lesson.resources.map((r) => ({
      title: r.title,
      description: r.description,
      instructions: r.instructions,
      filename: r.filename,
      resourceType: r.resourceType,
    })),
  };
}

export class StepHandlerError extends Error {}

/** Execute a single JobStep. Returns a JSON-serializable result to store on the row. Throws on
 * failure; the caller (worker.ts) is responsible for catching and marking the row failed. */
export async function executeStep(jobStep: JobStep): Promise<Record<string, unknown>> {
  if (jobStep.resourceId) {
    return executeResourceStep(jobStep);
  }
  switch (jobStep.step) {
    case "slides":
      return handleSlides(jobStep.lessonId);
    case "narration":
      return handleNarration(jobStep.lessonId);
    case "video":
      return handleVideo(jobStep.lessonId);
    case "editable_assets":
      return handleEditableAssets(jobStep.lessonId);
    case "aws_upload":
      return handleAwsUpload(jobStep.lessonId);
    case "bunny_upload":
      return handleBunnyUpload(jobStep.lessonId);
    case "moodle_publish":
      return handleMoodlePublish(jobStep.lessonId);
    default:
      throw new StepHandlerError(`Unknown lesson step: ${jobStep.step}`);
  }
}

async function handleSlides(lessonId: string): Promise<Record<string, unknown>> {
  const lesson = await lessonWithContext(lessonId);
  const brand = await resolveBrandForLesson(lessonId);
  const outputDir = path.join(
    lessonOutputDir(lesson.module.course.slug, lesson.module.number, lesson.number),
    "slides"
  );
  const result = await runEngineStep<{ slidePaths: string[]; slideSpecs: unknown[]; slideKinds: string[]; slideTexts: string[] }>({
    step: "render_slides",
    lesson: lessonToEngineDict(lesson),
    moduleTitle: lesson.module.title,
    outputDir,
    brand: brandTemplateToDict(brand),
  });
  return result;
}

async function handleNarration(lessonId: string): Promise<Record<string, unknown>> {
  const lesson = await lessonWithContext(lessonId);
  if (!env.elevenLabsApiKey) {
    throw new StepHandlerError("ELEVENLABS_API_KEY is not configured.");
  }
  const voice = await resolveVoiceForLesson(lessonId);
  if (!voice) {
    throw new StepHandlerError("No voice configured for this lesson, its course, or a default voice.");
  }
  const outputPath = path.join(
    lessonOutputDir(lesson.module.course.slug, lesson.module.number, lesson.number),
    "narration.mp3"
  );
  const result = await runEngineStep<{ audioPath: string; durationSeconds: number }>({
    step: "synthesize_narration",
    scriptText: lesson.scriptText,
    voiceRef: voice.elevenLabsVoiceId,
    apiKey: env.elevenLabsApiKey,
    outputPath,
  });
  await prisma.lesson.update({
    where: { id: lessonId },
    data: { narrationPath: result.audioPath, videoDurationSeconds: result.durationSeconds },
  });
  return result;
}

async function handleVideo(lessonId: string): Promise<Record<string, unknown>> {
  const lesson = await lessonWithContext(lessonId);
  const brand = await resolveBrandForLesson(lessonId);
  const slidesStep = await prisma.jobStep.findUniqueOrThrow({
    where: { lessonId_step_resourceId: { lessonId, step: "slides", resourceId: "" } },
  });
  const narrationStep = await prisma.jobStep.findUniqueOrThrow({
    where: { lessonId_step_resourceId: { lessonId, step: "narration", resourceId: "" } },
  });
  const slides = JSON.parse(slidesStep.resultJson ?? "{}") as { slidePaths: string[]; slideKinds: string[]; slideTexts: string[] };
  const narration = JSON.parse(narrationStep.resultJson ?? "{}") as { audioPath: string };

  const outputPath = path.join(
    lessonOutputDir(lesson.module.course.slug, lesson.module.number, lesson.number),
    "video.mp4"
  );
  const result = await runEngineStep<{ videoPath: string }>({
    step: "assemble_video",
    slidePaths: slides.slidePaths,
    slideTexts: slides.slideTexts,
    slideKinds: slides.slideKinds,
    narrationPath: narration.audioPath,
    outputPath,
    brand: brandTemplateToDict(brand),
  });
  await prisma.lesson.update({ where: { id: lessonId }, data: { videoPath: result.videoPath } });
  return result;
}

async function handleEditableAssets(lessonId: string): Promise<Record<string, unknown>> {
  const lesson = await lessonWithContext(lessonId);
  const brand = await resolveBrandForLesson(lessonId);
  const slidesStep = await prisma.jobStep.findUniqueOrThrow({
    where: { lessonId_step_resourceId: { lessonId, step: "slides", resourceId: "" } },
  });
  const slides = JSON.parse(slidesStep.resultJson ?? "{}") as { slideSpecs: unknown[] };
  const outputPath = path.join(
    lessonOutputDir(lesson.module.course.slug, lesson.module.number, lesson.number),
    `${sanitizeFilename(lesson.title)}.pptx`
  );
  const result = await runEngineStep<{ deckPath: string }>({
    step: "build_editable_deck",
    lessonTitle: lesson.title,
    slideSpecs: slides.slideSpecs,
    outputPath,
    brand: brandTemplateToDict(brand),
  });
  await prisma.lesson.update({ where: { id: lessonId }, data: { editableAssetPath: result.deckPath } });
  return result;
}

async function handleAwsUpload(lessonId: string): Promise<Record<string, unknown>> {
  const lesson = await lessonWithContext(lessonId);
  const bucket = lesson.module.course.awsBucket ?? env.awsDefaultBucket;
  if (!bucket) throw new StepHandlerError("No AWS bucket configured for this course and no AWS_DEFAULT_BUCKET set.");
  if (!lesson.videoPath) throw new StepHandlerError("Video has not been assembled yet.");

  const prefix = lesson.module.course.awsKeyPrefix ?? lesson.module.course.slug;
  const key = `${prefix}/${lesson.module.number}/${lesson.number}/${path.basename(lesson.videoPath)}`;
  const result: UploadResult = await s3UploadFile(bucket, key, lesson.videoPath, "video/mp4", lesson.module.course.awsRegion ?? undefined);
  await prisma.lesson.update({ where: { id: lessonId }, data: { awsVideoKey: result.key } });
  return { ...result };
}

async function handleBunnyUpload(lessonId: string): Promise<Record<string, unknown>> {
  const lesson = await lessonWithContext(lessonId);
  const libraryId = lesson.module.course.bunnyLibraryId ?? env.bunnyLibraryId;
  if (!libraryId) throw new StepHandlerError("No Bunny Stream library configured for this course and no BUNNY_STREAM_LIBRARY_ID set.");
  if (!lesson.videoPath) throw new StepHandlerError("Video has not been assembled yet.");

  const result = await bunnyUploadVideo(libraryId, lesson.title, lesson.videoPath);
  await prisma.lesson.update({ where: { id: lessonId }, data: { bunnyVideoId: result.videoId } });
  return { ...result };
}

async function handleMoodlePublish(lessonId: string): Promise<Record<string, unknown>> {
  const lesson = await lessonWithContext(lessonId);
  const courseId = lesson.module.course.moodleCourseId;
  if (!courseId) throw new StepHandlerError("No Moodle course ID configured for this course.");
  if (!lesson.bunnyVideoId) throw new StepHandlerError("Lesson has not been uploaded to Bunny Stream yet.");

  const introResult = await runEngineStep<{ html: string }>({
    step: "moodle_description",
    lesson: lessonToEngineDict(lesson),
  });

  let sectionId = lesson.module.moodleSectionId ?? undefined;
  if (!sectionId) {
    sectionId = await createOrUpdateSection(courseId, lesson.module.title);
    await prisma.module.update({ where: { id: lesson.module.id }, data: { moodleSectionId: sectionId } });
  }

  const cdnHostname = env.bunnyCdnHostname ?? `vz-${lesson.module.course.bunnyLibraryId ?? env.bunnyLibraryId}.b-cdn.net`;
  const playbackUrl = `https://${cdnHostname}/${lesson.bunnyVideoId}/playlist.m3u8`;
  const cmid = await publishUrlActivity(courseId, sectionId, lesson.title, introResult.html, playbackUrl);
  await prisma.lesson.update({ where: { id: lessonId }, data: { moodleActivityId: cmid, status: "complete" } });
  return { cmid, sectionId };
}

async function executeResourceStep(jobStep: JobStep): Promise<Record<string, unknown>> {
  const resource = await prisma.resource.findUniqueOrThrow({
    where: { id: jobStep.resourceId },
    include: { lesson: { include: { module: { include: { course: true } } } } },
  });

  if (jobStep.step === "resource_upload") {
    if (!resource.storagePath) throw new StepHandlerError("Resource has no stored file to upload.");
    const bucket = resource.lesson.module.course.awsBucket ?? env.awsDefaultBucket;
    if (!bucket) throw new StepHandlerError("No AWS bucket configured.");
    const prefix = resource.lesson.module.course.awsKeyPrefix ?? resource.lesson.module.course.slug;
    const key = `${prefix}/${resource.lesson.module.number}/${resource.lesson.number}/resources/${sanitizeFilename(resource.filename || resource.title)}`;
    const result = await s3UploadFile(bucket, key, resource.storagePath, "application/octet-stream", resource.lesson.module.course.awsRegion ?? undefined);
    await prisma.resource.update({ where: { id: resource.id }, data: { awsKey: result.key, status: "complete" } });
    return { ...result };
  }

  if (jobStep.step === "resource_moodle") {
    const courseId = resource.lesson.module.course.moodleCourseId;
    if (!courseId) throw new StepHandlerError("No Moodle course ID configured for this course.");
    if (!resource.awsKey) throw new StepHandlerError("Resource has not been uploaded to AWS yet.");
    let sectionId = resource.lesson.module.moodleSectionId ?? undefined;
    if (!sectionId) {
      sectionId = await createOrUpdateSection(courseId, resource.lesson.module.title);
      await prisma.module.update({ where: { id: resource.lesson.module.id }, data: { moodleSectionId: sectionId } });
    }
    const bucket = resource.lesson.module.course.awsBucket ?? env.awsDefaultBucket;
    const region = resource.lesson.module.course.awsRegion ?? env.awsRegion ?? "us-east-1";
    const url = `https://${bucket}.s3.${region}.amazonaws.com/${resource.awsKey}`;
    const cmid = await publishUrlActivity(courseId, sectionId, resource.title, resource.description, url);
    await prisma.resource.update({ where: { id: resource.id }, data: { moodleActivityId: cmid } });
    return { cmid };
  }

  throw new StepHandlerError(`Unknown resource step: ${jobStep.step}`);
}

export function resourceStorageDirFor(courseSlug: string, moduleNumber: string, lessonNumber: string): string {
  return resourceStorageDir(courseSlug, moduleNumber, lessonNumber);
}
