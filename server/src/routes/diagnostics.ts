import { Router } from "express";
import { z } from "zod";
import { asyncHandler, badRequest } from "./util";
import { testAwsConnection } from "../integrations/aws";
import { testBunnyConnection } from "../integrations/bunny";
import { testMoodleConnection } from "../integrations/moodle";
import { testElevenLabsConnection } from "../integrations/elevenlabs";
import { env } from "../env";

export const diagnosticsRouter = Router();

diagnosticsRouter.get("/config", (_req, res) => {
  res.json({
    elevenLabs: Boolean(env.elevenLabsApiKey),
    aws: Boolean(env.awsAccessKeyId && env.awsSecretAccessKey),
    bunny: Boolean(env.bunnyApiKey),
    moodle: Boolean(env.moodleBaseUrl && env.moodleToken),
  });
});

diagnosticsRouter.post("/test/elevenlabs", asyncHandler(async (_req, res) => {
  res.json(await testElevenLabsConnection());
}));

const awsSchema = z.object({ bucket: z.string().min(1), region: z.string().optional() });
diagnosticsRouter.post(
  "/test/aws",
  asyncHandler(async (req, res) => {
    const parsed = awsSchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);
    res.json(await testAwsConnection(parsed.data.bucket, parsed.data.region));
  })
);

const bunnySchema = z.object({ libraryId: z.string().min(1) });
diagnosticsRouter.post(
  "/test/bunny",
  asyncHandler(async (req, res) => {
    const parsed = bunnySchema.safeParse(req.body);
    if (!parsed.success) return badRequest(res, parsed.error.message);
    res.json(await testBunnyConnection(parsed.data.libraryId));
  })
);

diagnosticsRouter.post("/test/moodle", asyncHandler(async (_req, res) => {
  res.json(await testMoodleConnection());
}));
