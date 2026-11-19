import dotenv from "dotenv";

dotenv.config();

/**
 * All runtime configuration in one place. Every credential comes from an environment variable —
 * nothing is ever accepted from a request body or stored unencrypted in the database. See
 * /.env.example at the repo root for the full list with explanations.
 */
function optional(name: string): string | undefined {
  const value = process.env[name];
  return value && value.length > 0 ? value : undefined;
}

function required(name: string, fallback?: string): string {
  const value = optional(name) ?? fallback;
  if (value === undefined) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export const env = {
  nodeEnv: optional("NODE_ENV") ?? "development",
  port: Number(optional("PORT") ?? "4000"),

  storageRoot: required("STORAGE_ROOT", "./data"),
  adminPassword: optional("ADMIN_PASSWORD"),
  sessionSecret: required("SESSION_SECRET", "dev-insecure-session-secret-change-me"),

  pythonBin: optional("PYTHON_BIN") ?? "python3",
  engineDir: required("ENGINE_DIR", "../engine"),

  // Hosts that only run a single process per app (Cloudways' Node.js app type among them) can
  // set this instead of running server/src/queue/worker.ts as a second process — see
  // src/index.ts and DEPLOYMENT.md's "Single-process hosts" section. Off by default so the
  // documented two-process (systemd) setup isn't silently doubled up.
  runWorkerInline: (optional("RUN_WORKER_INLINE") ?? "false").toLowerCase() === "true",

  elevenLabsApiKey: optional("ELEVENLABS_API_KEY"),

  awsAccessKeyId: optional("AWS_ACCESS_KEY_ID"),
  awsSecretAccessKey: optional("AWS_SECRET_ACCESS_KEY"),
  awsRegion: optional("AWS_REGION"),
  awsDefaultBucket: optional("AWS_DEFAULT_BUCKET"),

  bunnyApiKey: optional("BUNNY_STREAM_API_KEY"),
  bunnyLibraryId: optional("BUNNY_STREAM_LIBRARY_ID"),
  bunnyCdnHostname: optional("BUNNY_CDN_HOSTNAME"),

  moodleBaseUrl: optional("MOODLE_BASE_URL"),
  moodleToken: optional("MOODLE_TOKEN"),

  aiProvider: optional("AI_PROVIDER"),
  aiApiKey: optional("AI_API_KEY"),
} as const;

export function isConfigured(keys: Array<keyof typeof env>): boolean {
  return keys.every((key) => env[key] !== undefined && env[key] !== null && env[key] !== "");
}
