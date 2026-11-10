import fs from "node:fs";
import { env } from "../env";

const BUNNY_API_BASE = "https://video.bunnycdn.com/library";

function apiKey(): string {
  if (!env.bunnyApiKey) throw new Error("BUNNY_STREAM_API_KEY is not configured.");
  return env.bunnyApiKey;
}

export interface BunnyVideoUploadResult {
  videoId: string;
  playbackUrl: string;
}

async function createVideo(libraryId: string, title: string): Promise<string> {
  const resp = await fetch(`${BUNNY_API_BASE}/${libraryId}/videos`, {
    method: "POST",
    headers: { AccessKey: apiKey(), "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!resp.ok) throw new Error(`Bunny create-video failed (${resp.status}): ${await resp.text()}`);
  const data = (await resp.json()) as { guid: string };
  return data.guid;
}

export async function uploadVideo(libraryId: string, title: string, localPath: string): Promise<BunnyVideoUploadResult> {
  const videoId = await createVideo(libraryId, title);
  const body = fs.readFileSync(localPath);
  const resp = await fetch(`${BUNNY_API_BASE}/${libraryId}/videos/${videoId}`, {
    method: "PUT",
    headers: { AccessKey: apiKey(), "Content-Type": "application/octet-stream" },
    body,
  });
  if (!resp.ok) throw new Error(`Bunny video upload failed (${resp.status}): ${await resp.text()}`);
  const hostname = env.bunnyCdnHostname ?? `vz-${libraryId}.b-cdn.net`;
  return { videoId, playbackUrl: `https://${hostname}/${videoId}/playlist.m3u8` };
}

/** Diagnostics "Test Connection": fetching library info proves the API key is valid for this
 * specific library (a key valid for a different library in the same account would 401/404 here
 * even though it "works" against Bunny's API in general). */
export async function testBunnyConnection(libraryId: string): Promise<{ ok: boolean; message: string }> {
  try {
    const resp = await fetch(`${BUNNY_API_BASE}/${libraryId}`, { headers: { AccessKey: apiKey() } });
    if (!resp.ok) {
      return { ok: false, message: `Bunny rejected the request (${resp.status}): ${await resp.text()}` };
    }
    const data = (await resp.json()) as { Name?: string };
    return { ok: true, message: `Connected to library "${data.Name ?? libraryId}".` };
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : String(err) };
  }
}
